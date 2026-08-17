
# app/controllers/search_controller.py
from flask import request, jsonify, current_app
import re
from ..models.eeiot_model import get_frames_collection
from ..models.search_model import (
    create_beit3,
    create_clip,
    create_llm,
    create_faiss_index,
    faiss_search_results,
    topk_fusion,
)
from ..utils.helpers import *
import torch
import threading
from deep_translator import GoogleTranslator


# Module-level lazy init variables
_models_initialized = False
_init_lock = threading.Lock()
_beit3 = None
_beit3_tokenizer = None
_clip = None
_clip_tokenizer = None
_clip_preprocess = None
_llm = None
_index_beit = None
_index_clip = None
_index_metadata = None
# _index_clip_metadata = None
DEVICE_DEFAULT = "cpu"


def _ensure_models(device=DEVICE_DEFAULT):
    global _models_initialized, _beit3, _beit3_tokenizer, _clip, _clip_tokenizer, _clip_preprocess, _llm, _index_beit, _index_clip, _index_metadata
    if _models_initialized:
        return

    with _init_lock:
        if _models_initialized:
            return
        current_app.logger.info("Initializing models and indexes (lazy)...")

        device_choice = device if torch.cuda.is_available() and device == "cuda" else "cpu"

        try:
            _beit3, _beit3_tokenizer = create_beit3()
            _clip, _clip_tokenizer, _clip_preprocess = create_clip()
            _llm = create_llm()
            _index_beit, _index_metadata = create_faiss_index(
                "embedding-info", "metadata", model="beit3", get_metadata=True
            )
            _index_clip, _ = create_faiss_index(
                "embedding-info", "metadata", model="clip", get_metadata=False
            )
        except Exception as e:
            current_app.logger.exception("Failed to initialize models/indexes: %s", e)
            _beit3 = _beit3_tokenizer = _clip = _clip_tokenizer = _clip_preprocess = _llm = None
            _index_beit = _index_clip = None

        _models_initialized = True
        current_app.logger.info("Model/index initialization complete.")


def ensure_models(device=DEVICE_DEFAULT):
    """Đảm bảo model/index đã init (dùng chung singleton với search_collection) và
    trả về bundle cho các controller khác (vd trake_controller) tái sử dụng, tránh
    load model 2 lần."""
    _ensure_models(device=device)
    return {
        "beit3": (_beit3, _beit3_tokenizer),
        "clip": (_clip, _clip_tokenizer, _clip_preprocess),
        "llm": _llm,
        "index_beit": _index_beit,
        "index_clip": _index_clip,
        "metadata": _index_metadata,
    }


def retrieve(query1, index, k, augment=False, query2=None, query3=None, model=None, device='cpu', llm=None):
	sims1, ids1 = faiss_search_results(query1, index, k, augment, model, device, llm)
	topk_ids1, topk_sims1 = topk_fusion(sims1, ids1)
 
 
	if query2 is not None:
		sims2, ids2 = faiss_search_results(query2, index, k, augment, model, device, llm)
		topk_ids2, topk_sims2 = topk_fusion(sims2, ids2)

		topk_ids3, topk_sims3 = [], []
		if query3 is not None:
			sims3, ids3 = faiss_search_results(query3, index, k, augment, model, device, llm)
			topk_ids3, topk_sims3 = topk_fusion(sims3, ids3)

		reranking = []
		map2= dict(zip(topk_ids2, range(k)))
		map3= dict(zip(topk_ids3, range(k)))
		
		set_ids2 = set(topk_ids2)
		set_ids3 = set(topk_ids3)
		
		for i, idx1 in enumerate(topk_ids1):
			max_sim = 0
			for offset in range(10):
				temp_sim1 = topk_sims1[i]
				if idx1 + offset in set_ids2:
					temp_sim1 += (topk_sims2[map2[idx1+offset]]) # 1/(60+map[idx1+offset])

					temp_sim2 = 0
					if query3 is not None:
						for offset2 in range(10):
							if idx1+offset+offset2 in set_ids3:
								temp_sim2 = max(temp_sim2, topk_sims3[map3[idx1+offset+offset2]])
					temp_sim1 += temp_sim2

	 
				max_sim = max(max_sim, temp_sim1)
			reranking.append(max_sim)

		map = list(zip(topk_ids1, reranking))
		zip_sorted= list(sorted(map, key=lambda x: x[1], reverse=True))
  
		topk_ids1, _ = zip(*zip_sorted)

	return topk_ids1


def create_fuzzy_query(detection=None, objects=None, text=None):
    ob_query = []
    if objects:
        ob_query.append(
            {
                "text": {
                    "query": objects,
                    "path": "objects",
                    "fuzzy": {"maxEdits": 1, "prefixLength": 2},
                }
            }
        )

    od_query = []
    if detection:
        for bb in detection:
            od_query.append(
                {
                    "text": {
                        "query": bb,
                        "path": "detection",
                        "fuzzy": {"maxEdits": 1, "prefixLength": 2},
                    }
                }
            )

    text_query = None
    if text:
        text_query = {
            "text": {
                "query": text,
                "path": "text",
                "fuzzy": {"maxEdits": 1, "prefixLength": 2},
            }
        }

    return ob_query, od_query, text_query


def fuzzy_search(collection, detection=None, objects=None, operator="AND", text=None, k=100):
    if collection is None:
        return []

    ob_query, od_query, text_query = create_fuzzy_query(detection, objects, text)
    if ob_query == [] and od_query == [] and text_query is None:
        return []

    if od_query == []:
        od_clause = []
    else:
        od_clause = [{"compound": {"must": od_query}}] if operator == "AND" else [{"compound": {"should": od_query}}]

    clause = [] if ob_query == [] and od_query == [] else [{"compound": {"must": ob_query + od_clause}}]

    pipeline = [
        {"$search": {"index": "default", "compound": {"must": clause}}},
        {"$limit": k},
        {"$project": {"_id": 0, "idx": 1}},
    ]

    if text:
        pipeline[0]["$search"]["compound"]["must"].append(text_query)

    try:
        results = collection.aggregate(pipeline)
        return [res["idx"] for res in results]
    except Exception as e:
        current_app.logger.exception("fuzzy_search aggregation failed: %s", e)
        return []
    

def load_metadata_file(L: str):
    """Xác định và load file metadata dựa theo L (có thể có hậu tố như 26_b)"""
    raw_L = str(L)

    # Tách số đầu tiên ra để biết K hay L
    match = re.match(r"(\d+)", raw_L)
    if not match:
        return None, f"Invalid L value: {raw_L}"

    num = int(match.group(1))

    # Giữ nguyên hậu tố
    if num <= 20:
        filename = f"K{raw_L}.json"  # VD: K01.json hoặc K05_a.json
    else:
        filename = f"L{raw_L}.json"  # VD: L26.json hoặc L26_b.json

    base_dir = os.path.abspath(os.path.join(current_app.root_path, os.pardir))
    folder = os.path.join(base_dir, "metadata")
    filepath = os.path.join(folder, filename)

    if not os.path.exists(filepath):
        return None, f"File {filename} not found"

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data, None
    except Exception as e:
        return None, str(e)


def temporal_frames():
    """API lấy frame theo idx và trả về kèm ±10"""
    try:
        data = request.get_json(force=True, silent=True) or {}
        L = str(data.get("L"))  # Giữ nguyên string, có thể là '26_b'
        V = str(data.get("V"))
        idx = int(data.get("idx"))

        items, err = load_metadata_file(L)
        if err:
            return jsonify({"ok": False, "error": err}), 404

        # Tìm vị trí idx
        target_index = next((i for i, item in enumerate(items) if item.get("idx") == idx), None)
        if target_index is None:
            return jsonify({"ok": False, "error": f"idx {idx} not found"}), 404

        start = max(0, target_index - 10)
        end = min(len(items), target_index + 11)  # +1 để include target
        result = items[start:end]

        return jsonify({"ok": True, "count": len(result), "results": result}), 200

    except Exception as e:
        current_app.logger.exception("temporal_frames failed: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500


def search_logic(
    collection,
    metadata,
    model=None,
    query1=None,
    index=None,
    augment=False,
    k=100,
    query2=None,
    query3=None,
    llm=None,
    detection=None,
    objects=None,
    operator="AND",
    text=None,
    temporal_fuzzy=-1,
    language=False,
    device="cpu",
):
    topk = None
    topk_faiss = []
    topk_fuzzy = []
    
    if language == True:
        language = "Vie"
    else:
         language = "Eng"

    if language != "Eng":
      if query1 is not None:
        query1 = GoogleTranslator(source='vi', target='en').translate(query1)

      if query2 is not None:
        query2 = GoogleTranslator(source='vi', target='en').translate(query2)

      if query3 is not None:
        query3 = GoogleTranslator(source='vi', target='en').translate(query3)

              

    if temporal_fuzzy != -1:
        topk_fuzzy = fuzzy_search(collection, detection, objects, operator, text, k)
        if topk_fuzzy == []:
            return [], []
        if temporal_fuzzy == 1 and query2 != None:
            topk_faiss2 = retrieve(query2, index, k, augment, None, None, model, device, llm)
            topk_faiss3 = retrieve(query3, index, k, augment, None, None, model, device, llm) if query3 != None else []
            topk = RRF_ranking(topk_fuzzy, topk_faiss2, topk_faiss3)
        elif temporal_fuzzy == 2 and query1 != None:
            current_app.logger.info(query1)
            topk_faiss1 = retrieve(query1, index, k, augment, None, None, model, device, llm)
            topk_faiss3 = retrieve(query3, index, k, augment, None, None, model, device, llm) if query3 != None else []
            topk = RRF_ranking(topk_faiss1, topk_fuzzy, topk_faiss3)
        elif temporal_fuzzy == 3 and query2 != None and query1 != None:
            topk_faiss1 = retrieve(query1, index, k, augment, None, None, model, device, llm)
            topk_faiss2 = retrieve(query2, index, k, augment, None, None, model, device, llm)
            topk = RRF_ranking(topk_faiss1, topk_faiss2, topk_fuzzy)

    else:
        if query1 is not None and index is not None and model is not None:
            topk_faiss = retrieve(query1, index, k, augment, query2, query3, model, device, llm)
        else:
            topk_faiss = []

        topk_fuzzy = []# fuzzy_search(collection, detection, objects, operator, text, k)

        if topk_fuzzy == []:
            topk = topk_faiss
        elif topk_faiss == []:
            topk = topk_fuzzy
        else:
            mapping = dict(zip(topk_fuzzy, range(len(topk_fuzzy))))
            current_app.logger.info(len(topk_faiss))
            current_app.logger.info(len(topk_fuzzy))
            idx_set = set(topk_fuzzy)

            reranking = []
            for i, idx in enumerate(topk_faiss):
                if idx in idx_set:
                    reranking.append(1 / (100 + i) + 1 / (100 + mapping[idx]))
                else:
                    reranking.append(1 / (100 + i))

            topk = sorted(zip(topk_faiss, reranking), key=lambda x: x[1], reverse=True)
            topk = [idx for idx, _ in topk]
    # current_app.logger.info(topk)
    current_app.logger.info(len(metadata)) 
    if not topk:
        topk = []

    
    return topk


def temporal_search(metadata, frame_idx=-1):
    frame_paths = []
    start = max(0, frame_idx - 10)
    end = min(len(metadata), frame_idx + 10)
    for idx in range(start, end):
        frame_paths.append(metadata[idx].get("idx") if isinstance(metadata[idx], dict) else metadata[idx])
    return frame_paths

def RRF_ranking(topk1, topk2, topk3, wd=10):
	map2 = dict(zip(topk2, range(len(topk2))))
	map3 = dict(zip(topk3, range(len(topk3))))
	
	set_idx2 = set(topk2)
	set_idx3 = set(topk3)
	
	reranking = []
	for i, idx1 in enumerate(topk1):
		reranking.append(1/(100+i))
		for offset1 in range(wd):
			if idx1+offset1 in set_idx2:
				reranking[-1]+=1/(100.0+map2[idx1+offset1])
				for offset2 in range(wd):
					if idx1+offset1+offset2 in set_idx3:
						reranking[-1]+=1/(100.0+map3[idx1+offset1+offset2])
	
	map = list(zip(topk1, reranking))
	zip_sorted= list(sorted(map, key=lambda x: x[1], reverse=True))

	topk1, _ = zip(*zip_sorted)
	current_app.logger.info(topk1)
	return topk1


def search_collection():
    try:
        data = request.get_json(force=True, silent=True) or {}
        current_app.logger.info("Received request data: %s", data)

        query1 = data.get("query1")
        query2 = data.get("query2")
        query3 = data.get("query3")
        language = data.get("language")
        temporal_fuzzy = data.get("temporal_fuzzy")
        model_name = (data.get("model") or "beit3").lower()
        k = int(data.get("k", 100))
        if k <= 0:
            k = 100
        k = min(k, 5000)

        augment = bool(data.get("augment", False))
        detection = data.get("detection")

        if isinstance(detection, str):
            detection = [x.strip() for x in detection.split(",") if x.strip()]

        current_app.logger.info("Parsed detection groups: %s", detection)

        objects = data.get("objects")
        operator = (data.get("operator") or "AND").upper()
        if operator not in ("AND", "OR"):
            operator = "AND"
        text = data.get("text")
        device = data.get("device", "cpu") 
        use_llm = data.get("use_llm", augment)

        collection = get_frames_collection()
        current_app.logger.info("Frames collection: %s", collection)

        if collection is None:
            return jsonify({"ok": False, "error": "frames collection not available"}), 500

        _ensure_models(device=device)

        model = None
        index = None
        metadata = None
        if model_name == "beit3":
            model = (_beit3, _beit3_tokenizer)
            index = _index_beit
            metadata = _index_metadata
        else:
            model = (_clip, _clip_tokenizer, _clip_preprocess)
            index = _index_clip
            metadata = _index_metadata

        if model[0] is None and (query1 or query2 or query3):
            current_app.logger.warning("Model or index not available, falling back to fuzzy-only search.")
            query1 = None
            query2 = None
            query3 = None
            index = None

        topk = search_logic(
            collection=collection,
            metadata=metadata,
            model=model,
            query1=query1,
            index=index,
            augment=augment,
            k=k,
            query2=query2,
            query3=query3,
            llm=_llm if use_llm else None,
            detection=detection,
            objects=objects,
            operator=operator,
            temporal_fuzzy=temporal_fuzzy,
            text=text,
            device=device,
            language=language
            
        )

       
        docs = []
        if topk:
            cursor = collection.find(
                {"idx": {"$in": topk}},
                {
                    "_id": 0,
                    "idx": 1,
                    "path": 1,
                    "video_url": 1,
                    "L": 1,
                    "V": 1,
                    "frame_id": 1,
                    "fps": 1,
                    "frame_stamp": 1,
                    "objects": 1,
                    "detection": 1,
                    "text": 1,
                },
            )
            doc_map = {doc["idx"]: doc for doc in cursor}

            for idx in topk:
                docs.append(
                    doc_map.get(
                        idx,
                        {
                            "idx": idx,
                            "path": "",
                            "video_url": "",
                            "L": "",
                            "V": "",
                            "frame_id": None,
                            "fps": None,
                            "frame_stamp": None,
                            "objects": "",
                            "detection": "",
                            "text": [],
                        },
                    )
                )

        return jsonify({"ok": True, "count": len(docs), "results": docs}), 200

    except Exception as e:
        current_app.logger.exception("search_collection failed: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500
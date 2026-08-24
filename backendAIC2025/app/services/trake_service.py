# app/services/trake_service.py
"""TRAKE trên hạ tầng CHUNG (Qdrant của teammate) — KHÔNG dùng FAISS.

Dữ liệu: collection Qdrant theo model (beit3/jina/pe), point id = idx, payload có sẵn
video_id, L, V, frame_id, fps, video_url, video_path, path... (§3 spec).

Luồng:
  Tầng 1 — chọn video: mỗi event query top-M toàn collection, gom theo video_id, DP đơn điệu
    theo frame_id (ép thứ tự thời gian) -> chọn video khớp nhất.
  Tầng 2 — định vị từng event trong video đã chọn: query_points có filter video_id + frame_id>prev.
  Tầng 3 — (tùy chọn, cần VIDEO_ROOT) decode frame gốc ±R, encode bằng ĐÚNG model của collection,
    rerank thuật toán (peak) + Qwen khi tie.
  Sinh tổ hợp Cartesian (§10.3.1) để nộp tối đa 100 combo.

Không có video (Case 2) -> dừng ở keyframe. Rerank Qwen chỉ chạy khi bật + có tie.
"""
import logging
import os
import threading
from itertools import product
from math import prod

import numpy as np
from PIL import Image

from ..config import Config

logger = logging.getLogger(__name__)

NEG_INF = float("-inf")

_qwen_model = None
_qwen_processor = None
_qwen_lock = threading.Lock()
_qwen_load_failed = False

# §10.3.1: ngân sách ứng viên/mỗi event sao cho tích Descartes không vượt 100 tổ hợp.
_CANDIDATE_BUDGET = {2: 10, 3: 4, 4: 3, 5: 3, 6: 2}


def candidate_budget(n_events: int) -> int:
    return _CANDIDATE_BUDGET.get(n_events, 2 if n_events <= 10 else 1)


def _cand_pairs(cands):
    """[(frame_id, score)] từ list dict/tuple ứng viên."""
    out = []
    for c in cands:
        if isinstance(c, dict):
            fid = c.get("frame_id")
            if fid is None:
                fid = c.get("idx")
            out.append((fid, float(c.get("score", 0.0))))
        else:
            out.append((c[0], float(c[1])))
    return out


def softmax_probs(scores):
    scores = np.array(scores, dtype=np.float64)
    scores = scores - scores.max()
    exp = np.exp(scores)
    return exp / exp.sum()


# ---------------------------------------------------------------------------
# Encode event + query Qdrant qua SearchEngine của teammate.
# ---------------------------------------------------------------------------

def encode_events(events_text, engine, model):
    """Encode mỗi event -> vector (np.float32, L2-normalize). Event rỗng (chỉ OCR/ASR) -> None."""
    out = []
    for t in events_text:
        if t and str(t).strip():
            out.append(np.asarray(engine.registry.encode_text(t, model), dtype=np.float32))
        else:
            out.append(None)
    return out


def _qdrant_query(engine, model, vector, limit, video_id=None, frame_gt=None):
    """query_points 1 collection (theo model), tùy chọn filter video_id + frame_id>frame_gt.
    Trả list hit đã format (mỗi hit có idx, score, video_id, L, V, frame_id, fps, video_url...)."""
    from qdrant_client.http.models import FieldCondition, Filter, MatchValue, Range

    from search_engine.utils import format_qdrant_hits

    must = []
    if video_id is not None:
        must.append(FieldCondition(key="video_id", match=MatchValue(value=video_id)))
    if frame_gt is not None:
        must.append(FieldCondition(key="frame_id", range=Range(gt=frame_gt)))
    qfilter = Filter(must=must) if must else None

    collection = engine.collection_name(model)
    resp = engine.client.query_points(
        collection_name=collection,
        query=vector.tolist(),
        limit=limit,
        with_payload=True,
        with_vectors=False,
        query_filter=qfilter,
    )
    return format_qdrant_hits(resp)


# ---------------------------------------------------------------------------
# Tầng 1 — chọn video bằng DP đơn điệu (trên top-M ứng viên toàn kho của mỗi event).
# ---------------------------------------------------------------------------

def _dp_align(events_sorted):
    """events_sorted[j] = list[(key, score)] đã sort theo key tăng dần (key = frame_id).
    Chọn key_1 < key_2 < ... < key_N cực đại tổng score. Trả (best_cum, [key theo event])."""
    n = len(events_sorted)
    layers = [[(k, s, None) for k, s in events_sorted[0]]]
    for j in range(1, n):
        prev_sorted = sorted(layers[j - 1], key=lambda x: x[0])
        cur = []
        for k, s in events_sorted[j]:
            best_prev_cum, best_prev_key = NEG_INF, None
            for pk, pc, _ in prev_sorted:
                if pk >= k:
                    break
                if pc > best_prev_cum:
                    best_prev_cum, best_prev_key = pc, pk
            if best_prev_key is None:
                continue
            cur.append((k, s + best_prev_cum, best_prev_key))
        layers.append(cur)
        if not cur:
            return NEG_INF, []
    key_last, best_cum, _ = max(layers[-1], key=lambda x: x[1])
    path = [key_last]
    cur_key = key_last
    for j in range(n - 1, 0, -1):
        entry = next(e for e in layers[j] if e[0] == cur_key)
        cur_key = entry[2]
        path.append(cur_key)
    path.reverse()
    return best_cum, path


def select_video_dp(event_vecs, engine, model, top_m=150, top_videos=2):
    """Tầng 1: DP trên các event CÓ vector hình ảnh (bỏ event chỉ OCR/ASR = vector None).
    Không event hình ảnh nào -> trả rỗng (để ocr_asr_candidate_videos lo tầng 1)."""
    visual_js = [j for j, v in enumerate(event_vecs) if v is not None]
    if not visual_js:
        return []
    per_event_hits = {j: _qdrant_query(engine, model, event_vecs[j], top_m) for j in visual_js}

    per_video = {}
    for j in visual_js:
        for h in per_event_hits[j]:
            vid = h.get("video_id")
            fid = h.get("frame_id")
            if vid is None or fid is None:
                continue
            entry = per_video.setdefault(vid, {"events": {}, "meta": h})
            entry["events"].setdefault(j, []).append((int(fid), float(h["score"])))

    results = []
    for vid, data in per_video.items():
        evs = data["events"]
        if len(evs) < len(visual_js):  # thiếu event hình ảnh nào -> loại
            continue
        events_sorted = [sorted(evs[j], key=lambda t: t[0]) for j in visual_js]
        best, _path = _dp_align(events_sorted)
        if best == NEG_INF:
            continue
        m = data["meta"]
        results.append(
            {
                "video_id": vid,
                "L": m.get("L"),
                "V": m.get("V"),
                "fps": m.get("fps"),
                "video_url": m.get("video_url"),
                "video_path": m.get("video_path"),
                "score": best,
            }
        )
    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:top_videos]


def allocate_video_slots(video_candidates, total_slots=100, confidence_threshold=0.8):
    """§10.3.1 bẫy 3: không dồn hết slot cho 1 video khi chưa chắc.
    Hỗ trợ N video. Nếu có video được OCR/ASR bảo chứng -> luôn dành slot (sàn), không dồn hết top-1."""
    if not video_candidates:
        return []
    if len(video_candidates) == 1:
        return [(video_candidates[0], total_slots)]

    has_oa = any(v.get("from_ocr_asr") for v in video_candidates)
    probs = softmax_probs([v["score"] for v in video_candidates])

    # Chắc chắn (top-1 vượt ngưỡng) VÀ không có bảo chứng OCR/ASR VÀ chỉ có <=2 video ứng viên
    # -> dồn hết cho top-1 (hành vi mặc định). Khi user xin nhiều video hơn (khám phá) -> luôn chia đều.
    if probs[0] >= confidence_threshold and not has_oa and len(video_candidates) <= 2:
        return [(video_candidates[0], total_slots)]

    # Ngược lại: chia theo prob nhưng mỗi video có sàn để không biến mất.
    n = len(video_candidates)
    floor = max(1, total_slots // (n * 3))
    slots = [floor] * n
    remaining = total_slots - floor * n
    if remaining > 0:
        alloc = [int(remaining * p) for p in probs]
        for i in range(remaining - sum(alloc)):  # bù phần lẻ vào các video điểm cao
            slots_idx = sorted(range(n), key=lambda k: -probs[k])[i % n]
            alloc[slots_idx] += 1
        slots = [s + a for s, a in zip(slots, alloc)]
    return list(zip(video_candidates, slots))


def _video_meta_from_qdrant(engine, model, video_id):
    """Lấy metadata 1 video (L, V, fps, video_url, video_path) từ 1 point Qdrant."""
    from qdrant_client.http.models import FieldCondition, Filter, MatchValue

    try:
        points, _ = engine.client.scroll(
            collection_name=engine.collection_name(model),
            scroll_filter=Filter(must=[FieldCondition(key="video_id", match=MatchValue(value=video_id))]),
            limit=1,
            with_payload=True,
            with_vectors=False,
        )
    except Exception:
        return None
    if not points:
        return None
    p = points[0].payload or {}
    return {
        "video_id": video_id,
        "L": p.get("L"),
        "V": p.get("V"),
        "fps": p.get("fps"),
        "video_url": p.get("video_url"),
        "video_path": p.get("video_path"),
        "score": None,
    }


def ocr_asr_candidate_videos(events_ocr, events_asr, engine, model, max_videos=4):
    """Tầng 1 nhận thêm ứng viên video từ OCR/ASR: video nào có OCR (chữ) / ASR (lời nói) khớp
    bất kỳ event nào -> đưa vào danh sách để tầng 1 hình ảnh không bỏ sót. Trả list video dict."""
    if not events_ocr and not events_asr:
        return []
    try:
        from .mongo_search import search_ocr, search_asr
    except Exception:
        return []

    votes = {}  # video_id -> số lần khớp (OCR/ASR, mọi event)

    def _collect(texts, fn):
        for t in (texts or []):
            if not t or not str(t).strip():
                continue
            try:
                for h in fn(str(t).strip(), limit=15):
                    v = h.get("video_id")
                    if v:
                        votes[v] = votes.get(v, 0) + 1
            except Exception:
                continue

    _collect(events_ocr, search_ocr)
    _collect(events_asr, search_asr)
    if not votes:
        return []

    # Ưu tiên video khớp nhiều nhất, lấy tối đa max_videos.
    ranked = sorted(votes.items(), key=lambda kv: -kv[1])[:max_videos]
    out = []
    for vid, cnt in ranked:
        meta = _video_meta_from_qdrant(engine, model, vid)
        if meta:
            meta["from_ocr_asr"] = True
            meta["ocr_asr_votes"] = cnt
            out.append(meta)
    return out


# ---------------------------------------------------------------------------
# Tầng 2 — định vị từng event trong video đã chọn (Qdrant filter video_id + frame_id>prev).
# ---------------------------------------------------------------------------

def _ocr_asr_frames_for_event(ocr_text, asr_text, video_id, frame_gt, topk):
    """Ứng viên [(frame_id, score, path)] cho event CHỈ có OCR/ASR (không mô tả hình).
    OCR: keyframe khớp chữ (điểm theo thứ hạng). ASR: keyframe trong khoảng lời nói. Ép frame_id>frame_gt."""
    try:
        from .mongo_search import ocr_frame_ids_in_video, asr_ranges_in_video, keyframes_in_range
    except Exception:
        return []
    scored = {}  # frame_id -> [score, path]
    if ocr_text and ocr_text.strip():
        try:
            for rank, (fid, path) in enumerate(ocr_frame_ids_in_video(ocr_text.strip(), video_id, limit=30)):
                fid = int(fid)
                s = 1.0 - rank * 0.02
                if fid not in scored or s > scored[fid][0]:
                    scored[fid] = [s, path]
        except Exception:
            pass
    if asr_text and asr_text.strip():
        try:
            for s0, e0 in asr_ranges_in_video(asr_text.strip(), video_id, limit=10):
                for fid, path in keyframes_in_range(video_id, s0, e0, limit=30):
                    fid = int(fid)
                    scored.setdefault(fid, [0.9, path])
        except Exception:
            pass
    items = [(fid, sc, path) for fid, (sc, path) in scored.items() if frame_gt is None or fid > frame_gt]
    if not items:  # rỗng sau ràng buộc -> nới
        items = [(fid, sc, path) for fid, (sc, path) in scored.items()]
    items.sort(key=lambda t: -t[1])
    return items[:topk]


def locate_events_exact(event_vecs, engine, model, video_id, topk=3, events_ocr=None, events_asr=None):
    """Trả (results, path_map). Event có vector hình ảnh -> query Qdrant; event chỉ OCR/ASR -> ứng viên từ Mongo.
    path_map: {frame_id: path keyframe} để Case 2 render ảnh."""
    results = []
    path_map = {}
    prev = None
    for j, v in enumerate(event_vecs):
        cands = []
        if v is not None:
            hits = _qdrant_query(engine, model, v, topk, video_id=video_id, frame_gt=prev)
            if not hits:  # hết frame sau prev -> nới ràng buộc để không rỗng
                hits = _qdrant_query(engine, model, v, topk, video_id=video_id)
            for h in hits:
                if h.get("frame_id") is None:
                    continue
                fid = int(h["frame_id"])
                cands.append((fid, float(h["score"])))
                if h.get("path"):
                    path_map[fid] = h["path"]
        else:  # event chỉ OCR/ASR
            oc = events_ocr[j] if events_ocr and j < len(events_ocr) else ""
            ar = events_asr[j] if events_asr and j < len(events_asr) else ""
            for fid, sc, path in _ocr_asr_frames_for_event(oc, ar, video_id, prev, topk):
                cands.append((int(fid), float(sc)))
                if path:
                    path_map[int(fid)] = path
        if not cands:
            results.append({"center_frame_id": None, "cands": []})
            continue
        results.append({"center_frame_id": cands[0][0], "cands": cands})
        prev = cands[0][0]
    return results, path_map


# ---------------------------------------------------------------------------
# Rerank thuật toán (peak) + Qwen — dùng cho tầng 3.
# ---------------------------------------------------------------------------

def _rank_by_peak(scores, topk):
    scores = np.asarray(scores, dtype=np.float64)
    if len(scores) >= 3:
        try:
            from scipy.signal import find_peaks

            peaks, props = find_peaks(scores, prominence=0)
            if len(peaks) > 0:
                ranked = sorted(
                    zip(peaks.tolist(), props["prominences"].tolist()),
                    key=lambda p: (-p[1], -scores[p[0]]),
                )
                ranked_idx = [p[0] for p in ranked]
                remaining = [i for i in np.argsort(-scores).tolist() if i not in ranked_idx]
                return (ranked_idx + remaining)[:topk]
        except ImportError:
            pass
    return np.argsort(-scores)[:topk].tolist()


def pick_semantic_frame_algorithmic(frame_ids, scores, topk):
    scores = np.asarray(scores, dtype=np.float64)
    order = _rank_by_peak(scores, topk)
    return [(int(frame_ids[i]), float(scores[i])) for i in order]


def qwen_rerank_ready():
    if not Config.TRAKE_QWEN_RERANK_ENABLED:
        return False, "TRAKE_QWEN_RERANK_ENABLED=false -> algorithm only (peak detection)"
    if _qwen_load_failed:
        return False, "Qwen local load failed earlier -> algorithm only"
    try:
        import transformers  # noqa: F401
    except ImportError:
        return False, "transformers not installed -> algorithm only"
    return True, "Qwen2.5-VL (local) ready"


def _load_qwen():
    global _qwen_model, _qwen_processor, _qwen_load_failed
    if not Config.TRAKE_QWEN_RERANK_ENABLED or _qwen_load_failed:
        return None, None
    if _qwen_model is not None:
        return _qwen_model, _qwen_processor
    with _qwen_lock:
        if _qwen_model is not None:
            return _qwen_model, _qwen_processor
        if _qwen_load_failed:
            return None, None
        try:
            import torch
            from transformers import AutoProcessor

            # Class generic đổi tên theo version: transformers 5.x = AutoModelForImageTextToText,
            # 4.x = AutoModelForVision2Seq. Fallback về class Qwen cụ thể nếu thiếu.
            _AutoVLM = None
            for _cls in ("AutoModelForImageTextToText", "AutoModelForVision2Seq"):
                try:
                    _AutoVLM = getattr(__import__("transformers", fromlist=[_cls]), _cls)
                    break
                except Exception:
                    continue

            quant = (Config.QWEN_QUANTIZATION or "none").lower()
            kwargs = {"torch_dtype": "auto", "device_map": Config.QWEN_DEVICE_MAP}
            if quant in ("4bit", "8bit"):
                # bitsandbytes CHỈ chạy trên CUDA. Máy CPU-only -> để QWEN_QUANTIZATION=none.
                from transformers import BitsAndBytesConfig

                if quant == "4bit":
                    # GPU cũ (Turing/GTX 16xx) KHÔNG có bf16 -> tự chọn fp16, tránh lỗi/chậm.
                    compute_dtype = (
                        torch.bfloat16
                        if (torch.cuda.is_available() and torch.cuda.is_bf16_supported())
                        else torch.float16
                    )
                    kwargs["quantization_config"] = BitsAndBytesConfig(
                        load_in_4bit=True, bnb_4bit_quant_type="nf4",
                        bnb_4bit_compute_dtype=compute_dtype, bnb_4bit_use_double_quant=True,
                    )
                else:
                    kwargs["quantization_config"] = BitsAndBytesConfig(load_in_8bit=True)
            logger.info("Loading Qwen-VL local: %s (quant=%s)...", Config.QWEN_MODEL_PATH, quant)
            if _AutoVLM is not None:
                # Auto class tự chọn đúng (Qwen2-VL-2B, Qwen2.5-VL-3B/7B...).
                _qwen_model = _AutoVLM.from_pretrained(Config.QWEN_MODEL_PATH, **kwargs)
            else:
                # Fallback: chọn class theo tên model.
                mp = (Config.QWEN_MODEL_PATH or "").lower()
                if "qwen2.5-vl" in mp or "qwen2_5_vl" in mp:
                    from transformers import Qwen2_5_VLForConditionalGeneration as _C
                else:
                    from transformers import Qwen2VLForConditionalGeneration as _C
                _qwen_model = _C.from_pretrained(Config.QWEN_MODEL_PATH, **kwargs)
            _qwen_model.eval()
            _qwen_processor = AutoProcessor.from_pretrained(Config.QWEN_MODEL_PATH)
        except Exception as e:
            logger.warning("Không load được Qwen2.5-VL local (%s) -> dùng thuật toán", e)
            _qwen_load_failed = True
            _qwen_model = _qwen_processor = None
    return _qwen_model, _qwen_processor


def qwen_rerank_candidates(frame_ids, frames_pil, event_text):
    model, processor = _load_qwen()
    if model is None or processor is None:
        return None
    try:
        import torch

        content = []
        for i in range(len(frames_pil)):
            content.append({"type": "image", "image": frames_pil[i]})
            content.append({"type": "text", "text": f"(image {i + 1})"})
        content.append(
            {
                "type": "text",
                "text": (
                    f'The images above are in chronological order. Which image is exactly the moment: '
                    f'"{event_text}"? Return only one image number (1..{len(frames_pil)}), no explanation.'
                ),
            }
        )
        text = processor.apply_chat_template([{"role": "user", "content": content}], tokenize=False, add_generation_prompt=True)
        inputs = processor(text=[text], images=list(frames_pil), padding=True, return_tensors="pt").to(model.device)
        with torch.inference_mode():
            gen = model.generate(**inputs, max_new_tokens=Config.QWEN_MAX_NEW_TOKENS, do_sample=False)
        out = processor.batch_decode(gen[:, inputs.input_ids.shape[1]:], skip_special_tokens=True)[0]
        digits = "".join(ch for ch in out if ch.isdigit())
        if digits:
            picked = int(digits[:2])
            if 1 <= picked <= len(frame_ids):
                return frame_ids[picked - 1]
    except Exception as e:
        logger.warning("Qwen rerank lỗi (%s) -> fallback thuật toán", e)
    return None


def _keyframe_disk_path(payload_path, keyframes_root):
    """'Keyframes/L21_V001/000000.webp' -> <keyframes_root>/L21_V001/000000.webp (đĩa lưu theo video_id)."""
    if not payload_path:
        return None
    p = str(payload_path).replace("\\", "/").lstrip("/")
    for pref in ("Keyframes/", "keyframes/"):
        if p.startswith(pref):
            p = p[len(pref):]
            break
    return os.path.join(keyframes_root, p)


def qwen_rerank_tier2(candidates_per_event, path_map, events_text, keyframes_root, tie_margin, max_imgs=3):
    """Tầng 2 (Case 2, KHÔNG cần video): khi top-2 ứng viên của 1 event gần tie -> đưa ảnh keyframe
    cho Qwen chọn frame khớp mô tả nhất. Thuật toán (visual sort) lo thứ tự, Qwen phân xử ties.
    Trả (candidates_per_event mới, số event đã dùng Qwen)."""
    used = 0
    out = []
    for cands, ev_text in zip(candidates_per_event, events_text):
        if len(cands) < 2 or not ev_text or abs(cands[0][1] - cands[1][1]) >= tie_margin:
            out.append(cands)
            continue
        tie = cands[:max_imgs]
        imgs, ids = [], []
        for fid, _ in tie:
            disk = _keyframe_disk_path(path_map.get(int(fid)) or path_map.get(fid), keyframes_root)
            if disk and os.path.isfile(disk):
                try:
                    imgs.append(Image.open(disk).convert("RGB"))
                    ids.append(int(fid))
                except Exception:
                    continue
        if len(imgs) < 2:
            out.append(cands)
            continue
        picked = qwen_rerank_candidates(ids, imgs, ev_text)
        if picked is not None:
            out.append([(picked, cands[0][1])] + [c for c in cands if c[0] != picked])
            used += 1
        else:
            out.append(cands)
    return out, used


# ---------------------------------------------------------------------------
# Tầng 3 — tinh chỉnh frame gốc (chỉ khi có VIDEO_ROOT + video). Encode bằng ĐÚNG model collection.
# ---------------------------------------------------------------------------

def tier3_globally_ready():
    if not Config.TRAKE_TIER3_ENABLED:
        return False, "TRAKE_TIER3_ENABLED=false -> case 2 (no refinement)"
    if not Config.VIDEO_ROOT or not os.path.isdir(Config.VIDEO_ROOT):
        return False, f"VIDEO_ROOT not found: {Config.VIDEO_ROOT!r}"
    try:
        import cv2  # noqa: F401
    except ImportError:
        return False, "opencv-python (cv2) is not installed"
    return True, "tier 3 ready"


def resolve_video_path(video_path_payload, video_id):
    """Ghép VIDEO_ROOT với video_path trong payload Qdrant (vd 'Videos/L30_V079.mp4')."""
    root = Config.VIDEO_ROOT
    if not root or not os.path.isdir(root):
        return None
    candidates = []
    if video_path_payload and not str(video_path_payload).startswith(("http://", "https://")):
        candidates.append(os.path.join(root, video_path_payload))
        candidates.append(os.path.join(root, os.path.basename(video_path_payload)))
    candidates.append(os.path.join(root, f"{video_id}.mp4"))
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


def refine_event_fine(video_path, ev_vec, event_text, engine, model, coarse_frame_id, prev_fine, radius, stride, topk):
    """Trả (candidates [(frame_id,score)], used_qwen). candidates=None nếu không đọc được video."""
    import cv2

    if coarse_frame_id is None:
        return None, False
    lo = coarse_frame_id - radius
    if prev_fine is not None:
        lo = max(lo, prev_fine + 1)
    lo = max(lo, 0)
    hi = coarse_frame_id + radius
    if lo > hi:
        lo = hi

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return None, False
    cap.set(cv2.CAP_PROP_POS_FRAMES, lo)
    frames, frame_ids = [], []
    cur = lo
    while cur <= hi:
        ok, frame = cap.read()
        if not ok:
            break
        if (cur - lo) % stride == 0:
            frames.append(Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)))
            frame_ids.append(cur)
        cur += 1
    cap.release()
    if not frames:
        return None, False

    embs = np.stack([np.asarray(engine.registry.encode_image(f, model), dtype=np.float32) for f in frames])
    scores = embs @ ev_vec
    ranked = pick_semantic_frame_algorithmic(frame_ids, scores, topk)

    used_qwen = False
    if len(ranked) >= 2 and abs(ranked[0][1] - ranked[1][1]) < Config.TRAKE_RERANK_TIE_MARGIN:
        ready, _ = qwen_rerank_ready()
        if ready and event_text:
            tie = ranked[: min(len(ranked), 3)]
            tie_ids = [fid for fid, _ in tie]
            tie_frames = [frames[frame_ids.index(fid)] for fid in tie_ids]
            picked = qwen_rerank_candidates(tie_ids, tie_frames, event_text)
            if picked is not None:
                ranked = [(picked, ranked[0][1])] + [c for c in ranked if c[0] != picked]
                used_qwen = True
    return ranked, used_qwen


# ---------------------------------------------------------------------------
# §10.3.1 — Cartesian + NMS thời gian + ràng buộc thứ tự tăng.
# ---------------------------------------------------------------------------

def nms_candidates(candidates, min_gap=15):
    kept = []
    for fid, sc in candidates:
        if all(abs(fid - kid) >= min_gap for kid, _ in kept):
            kept.append((fid, sc))
    return kept


def build_cartesian_submissions(candidates_per_event, max_combos=100, min_gap=15):
    cleaned = []
    for cands in candidates_per_event:
        cands_sorted = nms_candidates(sorted(cands, key=lambda c: -c[1]), min_gap=min_gap)
        if not cands_sorted:
            return []
        probs = softmax_probs([c[1] for c in cands_sorted])
        cleaned.append(list(zip([c[0] for c in cands_sorted], probs)))

    weighted = []
    for combo in product(*cleaned):
        fids = [c[0] for c in combo]
        if all(fids[i] < fids[i + 1] for i in range(len(fids) - 1)):
            weighted.append((fids, prod(p for _, p in combo)))
    weighted.sort(key=lambda x: -x[1])
    return [c[0] for c in weighted[:max_combos]]


# ---------------------------------------------------------------------------
# Ghép OCR/ASR theo từng event (boost mềm) — map event -> frame khớp trong video đã chọn.
# ---------------------------------------------------------------------------

def _event_ocr_asr_targets(events_ocr, events_asr, video_id, n_events):
    """Per-event (ocr_frame_ids:set, asr_ranges:list[(s,e)], ocr_paths:dict{fid:path}) trong video_id."""
    targets = [(set(), [], {}) for _ in range(n_events)]
    if not events_ocr and not events_asr:
        return targets
    try:
        from .mongo_search import ocr_frame_ids_in_video, asr_ranges_in_video
    except Exception:
        return targets
    for j in range(n_events):
        oc = (events_ocr[j] if events_ocr and j < len(events_ocr) else "") or ""
        ar = (events_asr[j] if events_asr and j < len(events_asr) else "") or ""
        ofs, ars, opaths = set(), [], {}
        if oc.strip():
            try:
                for fid, path in ocr_frame_ids_in_video(oc.strip(), video_id, limit=10):
                    ofs.add(int(fid))
                    if path:
                        opaths[int(fid)] = path
            except Exception:
                ofs, opaths = set(), {}
        if ar.strip():
            try:
                ars = asr_ranges_in_video(ar.strip(), video_id)
            except Exception:
                ars = []
        targets[j] = (ofs, ars, opaths)
    return targets


def _apply_ocr_asr_boost(cands, ocr_fids, asr_ranges, boost, window, path_map=None):
    """Nhân điểm ứng viên khớp OCR (±window frame) hoặc trong khoảng ASR lên (1+boost).
    Đồng thời INJECT frame OCR khớp mà chưa có trong cands (để frame OCR chắc chắn được xét),
    điểm = max điểm hiện có * (1+boost). Nếu có path_map: cập nhật path cho frame inject (UI hiện ảnh)."""
    if not ocr_fids and not asr_ranges:
        return cands, 0
    existing = [fid for fid, _ in cands]
    base = max((sc for _, sc in cands), default=1.0)
    out, n_hit = [], 0
    for fid, sc in cands:
        hit = (ocr_fids and any(abs(fid - o) <= window for o in ocr_fids)) or (
            asr_ranges and any(s <= fid <= e for s, e in asr_ranges)
        )
        if hit:
            n_hit += 1
        out.append((fid, sc * (1.0 + boost) if hit else sc))
    # Inject frame OCR khớp chưa nằm gần ứng viên nào (giới hạn vài frame để không nổ tổ hợp).
    injected = 0
    for o in sorted(ocr_fids):
        if injected >= 3:
            break
        if not any(abs(o - e) <= window for e in existing):
            out.append((int(o), base * (1.0 + boost)))
            existing.append(int(o))
            injected += 1
            n_hit += 1
    return out, n_hit


# ---------------------------------------------------------------------------
# Orchestrator.
# ---------------------------------------------------------------------------

def run_trake(events_text, engine, model, top_m=None, top_videos=None, max_combos=None,
              events_ocr=None, events_asr=None):
    top_videos = top_videos or Config.TRAKE_TOP_VIDEOS
    # top_m (số ứng viên tầng 1) tự nới theo số video muốn xem -> nhiều video đủ 3 event để DP hơn.
    top_m = max(top_m or Config.TRAKE_TOP_M, top_videos * 100)
    max_combos = min(max_combos or Config.TRAKE_MAX_COMBOS, Config.TRAKE_MAX_COMBOS_HARD)
    radius = Config.TRAKE_TIER3_RADIUS
    stride = Config.TRAKE_TIER3_STRIDE
    conf_thr = Config.TRAKE_VIDEO_CONFIDENCE_THRESHOLD
    tier3_topk = candidate_budget(len(events_text))

    event_vecs = encode_events(events_text, engine, model)

    video_candidates, attempt_m = [], top_m
    for _ in range(3):
        video_candidates = select_video_dp(event_vecs, engine, model, top_m=attempt_m, top_videos=top_videos)
        if video_candidates:
            break
        attempt_m *= 3

    # Tầng 1 + OCR/ASR: thêm video được OCR/ASR bảo chứng (khớp chữ/lời nói) để hình ảnh không bỏ sót.
    oa_videos = ocr_asr_candidate_videos(events_ocr, events_asr, engine, model)
    if oa_videos:
        existing = {v["video_id"] for v in video_candidates}
        top_vis = video_candidates[0]["score"] if video_candidates else None
        for ov in oa_videos:
            if ov["video_id"] in existing:
                continue
            # Điểm cho video OCR/ASR-only = ngang top visual (OCR/ASR là tín hiệu mạnh) -> được chia slot.
            ov["score"] = top_vis if top_vis is not None else 1.0
            video_candidates.append(ov)
        video_candidates.sort(
            key=lambda r: (r["score"] if r.get("score") is not None else -1e9), reverse=True
        )
        video_candidates = video_candidates[: max(top_videos, 2) + len(oa_videos)]

    if not video_candidates:
        return {
            "ok": False,
            "error": f"No video matched all events within top-M (tried up to top_m={attempt_m}). "
            "Increase top_m or revise the event descriptions.",
        }

    slots = allocate_video_slots(video_candidates, total_slots=max_combos, confidence_threshold=conf_thr)
    ready, reason = tier3_globally_ready()
    qwen_ready, qwen_reason = qwen_rerank_ready()

    per_video = []
    any_tier3 = False
    qwen_used_total = 0
    ocr_asr_boost_total = 0

    for video, slot_count in slots:
        if slot_count <= 0:
            continue
        vid = video["video_id"]
        coarse, coarse_path_map = locate_events_exact(
            event_vecs, engine, model, vid, topk=tier3_topk,
            events_ocr=events_ocr, events_asr=events_asr,
        )
        if not coarse or all(not c["cands"] for c in coarse):
            continue

        video_path = resolve_video_path(video.get("video_path"), vid) if ready else None
        use_tier3 = ready and video_path is not None

        candidates_per_event = []
        qwen_used = 0
        if use_tier3:
            prev_fine = None
            for ev_vec, ev_text, ev_res in zip(event_vecs, events_text, coarse):
                if ev_vec is None:  # event chỉ OCR/ASR: không tinh chỉnh bằng video, giữ ứng viên coarse
                    fine, uq = None, False
                else:
                    fine, uq = refine_event_fine(
                        video_path, ev_vec, ev_text, engine, model, ev_res["center_frame_id"],
                        prev_fine, radius, stride, tier3_topk,
                    )
                if fine is None:
                    fine = _cand_pairs(ev_res["cands"])
                if uq:
                    qwen_used += 1
                candidates_per_event.append(fine)
                if fine:
                    prev_fine = fine[0][0]
            use_tier3 = bool(candidates_per_event) and all(candidates_per_event)
        else:
            for ev_res in coarse:
                candidates_per_event.append(_cand_pairs(ev_res["cands"]))

        any_tier3 = any_tier3 or use_tier3

        # Boost mềm + inject theo event: frame khớp OCR/ASR (trong video này) được nhân điểm / thêm vào.
        oa_targets = _event_ocr_asr_targets(events_ocr, events_asr, vid, len(events_text))
        oa_hits = 0
        if any(ofs or ars for ofs, ars, _ in oa_targets):
            boosted = []
            for j, cands in enumerate(candidates_per_event):
                new_cands, n_hit = _apply_ocr_asr_boost(
                    cands, oa_targets[j][0], oa_targets[j][1],
                    Config.TRAKE_OCRASR_BOOST, Config.TRAKE_OCRASR_WINDOW,
                )
                boosted.append(new_cands)
                oa_hits += n_hit
            candidates_per_event = boosted
            ocr_asr_boost_total += oa_hits
            # Nạp path keyframe cho frame OCR (kể cả frame inject) -> Case 2 hiện được ảnh.
            for _ofs, _ars, opaths in oa_targets:
                for fid, path in opaths.items():
                    coarse_path_map.setdefault(fid, path)

        # Tầng 2 + Qwen (Case 2, không cần video): phân xử ties bằng ảnh keyframe.
        if not use_tier3 and qwen_ready:
            candidates_per_event, qn2 = qwen_rerank_tier2(
                candidates_per_event, coarse_path_map, events_text,
                Config.KEYFRAMES_PATH, Config.TRAKE_RERANK_TIE_MARGIN,
            )
            qwen_used += qn2

        qwen_used_total += qwen_used

        combos = build_cartesian_submissions(candidates_per_event, max_combos=slot_count)
        per_video.append(
            {
                "video_id": vid,
                "L": video.get("L"),
                "V": video.get("V"),
                "fps": video.get("fps"),
                "video_url": video.get("video_url"),
                "video_score": video["score"],
                "tier3_used": use_tier3,
                "qwen_rerank_used_events": qwen_used,
                "ocr_asr_boosted_frames": oa_hits,
                "combos": combos,
                # Case 2: {frame_id: path keyframe} để UI hiện ảnh; Case 1 frame tinh chỉnh không có -> UI decode video.
                "frame_paths": {} if use_tier3 else {str(k): v for k, v in coarse_path_map.items()},
            }
        )

    submissions = []
    for r in per_video:
        for combo in r["combos"]:
            submissions.append({"video_id": r["video_id"], "frame_ids": combo})
    submissions = submissions[:max_combos]

    return {
        "ok": True,
        "mode": "case1_full" if any_tier3 else "case2_coarse",
        "tier": 3 if any_tier3 else 2,
        "rerank_method": "qwen" if qwen_used_total > 0 else "algorithm",
        "backend": f"qdrant:{model}",
        "tier3_globally_ready": ready,
        "tier3_reason": reason,
        "qwen_rerank_globally_ready": qwen_ready,
        "qwen_rerank_reason": qwen_reason,
        "qwen_rerank_used_events": qwen_used_total,
        "ocr_asr_applied": bool(events_ocr or events_asr),
        "ocr_asr_boosted_frames": ocr_asr_boost_total,
        "video_candidates": [
            {"video_id": v["video_id"], "L": v.get("L"), "V": v.get("V"), "score": v["score"]}
            for v in video_candidates
        ],
        "per_video": per_video,
        "submissions": submissions,
    }

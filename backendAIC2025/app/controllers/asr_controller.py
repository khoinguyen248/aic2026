# app/controllers/asr_controller.py
"""ASR search — cách search + UI theo code của bạn, đọc data từ MongoDB của teammate
(collection `asr_metadata`, field `text`, Atlas Search index `asr_search`).

Giữ "cách search của bạn": Atlas $search (fuzzy) -> fallback regex; trả đoạn ASR + enrich video_url
(lấy từ ocr_metadata) để UI dựng link YouTube + ảnh frame.
"""
import re

from flask import request, jsonify, current_app

from ..services.mongo_search import get_database

_ASR_PROJECT = {
    "_id": 0,
    "video_id": 1,
    "t_start": 1,
    "t_end": 1,
    "frame_start": 1,
    "frame_end": 1,
    "text": 1,
}


def _parse_video_id(video_id):
    """'L30_V068' -> (L='30', V='068'). Không khớp -> (None, None)."""
    m = re.match(r"L(.+?)_V(.+)", str(video_id))
    if m:
        return m.group(1), m.group(2)
    return None, None


def asr_lookup(query, k=50):
    """Cách search của bạn: Atlas $search (index asr_search) -> fallback regex trên text."""
    query = (query or "").strip()
    if not query:
        return []
    collection = get_database()["asr_metadata"]

    try:
        pipeline = [
            {
                "$search": {
                    "index": "asr_search",
                    "text": {"query": query, "path": "text", "fuzzy": {"maxEdits": 1, "prefixLength": 1}},
                }
            },
            {"$limit": int(k)},
            {"$project": {**_ASR_PROJECT, "score": {"$meta": "searchScore"}}},
        ]
        results = list(collection.aggregate(pipeline))
        if results:
            return results
    except Exception as e:
        current_app.logger.info("ASR $search không dùng được (%s) -> fallback regex", e)

    cur = collection.find(
        {"text": {"$regex": re.escape(query), "$options": "i"}}, _ASR_PROJECT
    ).limit(int(k))
    return [{**doc, "score": 1.0} for doc in cur]


def asr_search():
    """Độc lập: POST /search/asr {query, k} -> đoạn ASR khớp (đọc Mongo teammate)."""
    try:
        data = request.get_json(force=True, silent=True) or {}
        query = data.get("query")
        k = int(data.get("k", 50)) or 50

        segments = asr_lookup(query, k)

        # enrich video_url từ ocr_metadata (1 query/video) để UI dựng link YouTube
        ocr = get_database()["ocr_metadata"]
        meta = {}
        for vid in {s.get("video_id") for s in segments if s.get("video_id")}:
            meta[vid] = ocr.find_one({"video_id": vid}, {"_id": 0, "video_url": 1}) or {}

        results = []
        for s in segments:
            vid = s.get("video_id")
            L, V = _parse_video_id(vid)
            results.append(
                {
                    "video_id": vid,
                    "L": L,
                    "V": V,
                    "t_start": s.get("t_start"),
                    "t_end": s.get("t_end"),
                    "frame_start": s.get("frame_start"),
                    "frame_end": s.get("frame_end"),
                    "text": s.get("text"),
                    "score": s.get("score"),
                    "video_url": meta.get(vid, {}).get("video_url"),
                }
            )

        return jsonify({"ok": True, "count": len(results), "results": results}), 200

    except RuntimeError as e:
        return jsonify({"ok": False, "error": str(e)}), 503
    except Exception as e:
        current_app.logger.exception("asr_search failed: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500


def asr_boost_idxset(query, k=50):
    """(Merge mode) SET idx frame nằm trong đoạn ASR khớp — map qua ocr_metadata. Giữ để tương thích;
    main search giờ là Qdrant nên merge mode chưa dùng tới."""
    try:
        db = get_database()
        ocr = db["ocr_metadata"]
        boost = set()
        for s in asr_lookup(query, k):
            vid, fs, fe = s.get("video_id"), s.get("frame_start"), s.get("frame_end")
            if vid is None or fs is None or fe is None:
                continue
            for d in ocr.find({"video_id": vid, "frame_id": {"$gte": fs, "$lte": fe}}, {"_id": 0, "idx": 1}):
                if d.get("idx") is not None:
                    boost.add(d["idx"])
        return boost
    except Exception:
        return set()

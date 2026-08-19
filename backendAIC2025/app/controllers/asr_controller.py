# app/controllers/asr_controller.py
"""ASR search — tìm theo NỘI DUNG LỜI NÓI trong transcript (collection asr_segments).

2 cách dùng (UI có toggle):
  1. Độc lập (asr_search): gõ nội dung -> trả về các đoạn ASR khớp + frame range + video_url.
  2. Gộp vào search chính: search_controller gọi asr_boost_idxset() để đẩy các frame nằm trong
     đoạn ASR khớp lên đầu (leg ASR, §9 + §15 spec).

⚠️ RECONCILE với backend Mongo/Qdrant của teammate: tên collection (asr_segments), tên field
(text/frame_start/frame_end/video_id), và index Atlas Search có thể khác -> chỉnh cho khớp.
"""
import re

from flask import request, jsonify, current_app

from ..models.eeiot_model import get_asr_collection, get_frames_collection

_ASR_PROJECT = {
    "_id": 0,
    "video_id": 1,
    "t_start": 1,
    "t_end": 1,
    "frame_start": 1,
    "frame_end": 1,
    "text": 1,
}


def asr_lookup(collection, query, k=50):
    """Trả list segment khớp query. Ưu tiên Atlas $search (fuzzy); lỗi/không có index -> regex."""
    query = (query or "").strip()
    if not query or collection is None:
        return []

    # 1) Atlas Search full-text (cần Atlas Search index trên field 'text')
    try:
        pipeline = [
            {
                "$search": {
                    "index": "default",
                    "text": {"query": query, "path": "text", "fuzzy": {"maxEdits": 1, "prefixLength": 2}},
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

    # 2) Fallback: regex không phân biệt hoa thường (không cần Atlas Search index)
    cur = collection.find(
        {"text": {"$regex": re.escape(query), "$options": "i"}}, _ASR_PROJECT
    ).limit(int(k))
    return [{**doc, "score": 1.0} for doc in cur]


def _parse_video_id(video_id):
    """'L30_V068' -> (L='30', V='068'). Không khớp -> (None, None)."""
    m = re.match(r"L(.+?)_V(.+)", str(video_id))
    if m:
        return m.group(1), m.group(2)
    return None, None


def asr_search():
    """Độc lập: POST /search/asr {query, k} -> đoạn ASR khớp, kèm video_url/fps để UI dựng link + ảnh."""
    try:
        data = request.get_json(force=True, silent=True) or {}
        query = data.get("query")
        k = int(data.get("k", 50)) or 50

        asr_coll = get_asr_collection()
        if asr_coll is None:
            return jsonify({"ok": False, "error": "asr collection not available"}), 500

        segments = asr_lookup(asr_coll, query, k)

        # enrich: 1 query/video để lấy video_url + fps (dựng link YouTube + tính frame)
        frames = get_frames_collection()
        meta = {}
        if frames is not None:
            for vid in {s.get("video_id") for s in segments if s.get("video_id")}:
                sample = frames.find_one({"video_id": vid}, {"_id": 0, "video_url": 1, "fps": 1}) or {}
                meta[vid] = sample

        results = []
        for s in segments:
            vid = s.get("video_id")
            L, V = _parse_video_id(vid)
            m = meta.get(vid, {})
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
                    "video_url": m.get("video_url"),
                    "fps": m.get("fps"),
                }
            )

        return jsonify({"ok": True, "count": len(results), "results": results}), 200

    except Exception as e:
        current_app.logger.exception("asr_search failed: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500


def asr_boost_idxset(query, k=50):
    """Merge mode: trả SET các `idx` keyframe nằm trong đoạn ASR khớp query -> để search chính
    đẩy các frame đó lên (leg ASR). Rỗng nếu không có match / thiếu collection."""
    asr_coll = get_asr_collection()
    frames = get_frames_collection()
    if asr_coll is None or frames is None:
        return set()

    segments = asr_lookup(asr_coll, query, k)
    boost = set()
    for s in segments:
        vid = s.get("video_id")
        fs, fe = s.get("frame_start"), s.get("frame_end")
        if vid is None or fs is None or fe is None:
            continue
        # keyframe của video này có frame_id trong [frame_start, frame_end] -> chiếu ASR về frame
        cur = frames.find(
            {"video_id": vid, "frame_id": {"$gte": fs, "$lte": fe}}, {"_id": 0, "idx": 1}
        )
        for d in cur:
            if "idx" in d:
                boost.add(d["idx"])
    return boost

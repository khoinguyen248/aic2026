# app/controllers/ocr_controller.py
"""OCR search — tìm theo CHỮ TRÊN MÀN HÌNH (field ocr_text trong collection frames, §8 spec).

Khác ASR: OCR là per-frame (ngay trong doc keyframe) -> match ra FRAME trực tiếp, không cần
chiếu frame_start/end. 2 cách dùng (UI có toggle):
  1. Độc lập (ocr_search): gõ chuỗi/tên/tỉ số -> trả về frame khớp (cùng shape kết quả search
     thường -> UI tái dùng bảng frame).
  2. Gộp vào search chính: search_controller gọi ocr_boost_idxset() để đẩy frame có ocr_text khớp
     lên đầu (leg OCR, §8 + §15 spec).

⚠️ RECONCILE với backend của teammate: field ocr_text + Atlas Search index có thể khác -> chỉnh khớp.
"""
import re

from flask import request, jsonify, current_app

from ..models.eeiot_model import get_frames_collection

_FRAME_PROJECT = {
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
    "ocr_text": 1,
}


def ocr_lookup(collection, query, k=100):
    """Trả list frame doc có ocr_text khớp query. Ưu tiên Atlas $search (fuzzy); lỗi -> regex."""
    query = (query or "").strip()
    if not query or collection is None:
        return []

    # 1) Atlas Search full-text trên ocr_text
    try:
        pipeline = [
            {
                "$search": {
                    "index": "default",
                    "text": {"query": query, "path": "ocr_text", "fuzzy": {"maxEdits": 1, "prefixLength": 2}},
                }
            },
            {"$limit": int(k)},
            {"$project": {**_FRAME_PROJECT, "score": {"$meta": "searchScore"}}},
        ]
        results = list(collection.aggregate(pipeline))
        if results:
            return results
    except Exception as e:
        current_app.logger.info("OCR $search không dùng được (%s) -> fallback regex", e)

    # 2) Fallback: regex không phân biệt hoa thường
    cur = collection.find(
        {"ocr_text": {"$regex": re.escape(query), "$options": "i"}}, _FRAME_PROJECT
    ).limit(int(k))
    return [{**doc, "score": 1.0} for doc in cur]


def ocr_search():
    """Độc lập: POST /search/ocr {query, k} -> frame khớp ocr_text (shape như /search/collection)."""
    try:
        data = request.get_json(force=True, silent=True) or {}
        query = data.get("query")
        k = int(data.get("k", 100)) or 100

        frames = get_frames_collection()
        if frames is None:
            return jsonify({"ok": False, "error": "frames collection not available"}), 500

        results = ocr_lookup(frames, query, k)
        return jsonify({"ok": True, "count": len(results), "results": results}), 200

    except Exception as e:
        current_app.logger.exception("ocr_search failed: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500


def ocr_boost_idxset(query, k=100):
    """Merge mode: SET các `idx` frame có ocr_text khớp query -> search chính đẩy lên đầu."""
    frames = get_frames_collection()
    if frames is None:
        return set()
    return {d["idx"] for d in ocr_lookup(frames, query, k) if "idx" in d}

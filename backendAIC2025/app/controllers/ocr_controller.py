# app/controllers/ocr_controller.py
"""OCR search — cách search + UI theo code của bạn, NHƯNG đọc data từ MongoDB của teammate
(collection `ocr_metadata`, field `ocr_text`, Atlas Search index `ocr_search`).

Giữ "cách search của bạn": ưu tiên Atlas $search (fuzzy) -> lỗi/không có index thì fallback regex.
Trả frame doc (shape hợp với bảng frame ở UI).
"""
import re

from flask import request, jsonify, current_app

from ..services.mongo_search import get_database

# Field có trong ocr_metadata của teammate
_OCR_PROJECT = {
    "_id": 0,
    "idx": 1,
    "video_id": 1,
    "frame_id": 1,
    "keyframe_order": 1,
    "frame_stamp": 1,
    "fps": 1,
    "ocr_text": 1,
    "path": 1,
    "video_path": 1,
    "video_url": 1,
}


def _ocr_collection():
    """Collection OCR trong Mongo của teammate. Ném lỗi nếu MONGO_SEARCH_URI chưa cấu hình."""
    return get_database()["ocr_metadata"]


def ocr_lookup(query, k=100):
    """Cách search của bạn: Atlas $search (index ocr_search) -> fallback regex trên ocr_text."""
    query = (query or "").strip()
    if not query:
        return []
    collection = _ocr_collection()

    # 1) Atlas Search full-text trên ocr_text (index 'ocr_search' của teammate)
    try:
        pipeline = [
            {
                "$search": {
                    "index": "ocr_search",
                    "text": {"query": query, "path": "ocr_text", "fuzzy": {"maxEdits": 1, "prefixLength": 1}},
                }
            },
            {"$limit": int(k)},
            {"$project": {**_OCR_PROJECT, "score": {"$meta": "searchScore"}}},
        ]
        results = list(collection.aggregate(pipeline))
        if results:
            return results
    except Exception as e:
        current_app.logger.info("OCR $search không dùng được (%s) -> fallback regex", e)

    # 2) Fallback: regex không phân biệt hoa thường
    cur = collection.find(
        {"ocr_text": {"$regex": re.escape(query), "$options": "i"}}, _OCR_PROJECT
    ).limit(int(k))
    return [{**doc, "score": 1.0} for doc in cur]


def ocr_search():
    """Độc lập: POST /search/ocr {query, k} -> frame khớp ocr_text (đọc Mongo teammate)."""
    try:
        data = request.get_json(force=True, silent=True) or {}
        query = data.get("query")
        k = int(data.get("k", 100)) or 100

        results = ocr_lookup(query, k)
        return jsonify({"ok": True, "count": len(results), "results": results}), 200

    except RuntimeError as e:
        # MONGO_SEARCH_URI chưa cấu hình
        return jsonify({"ok": False, "error": str(e)}), 503
    except Exception as e:
        current_app.logger.exception("ocr_search failed: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500


def ocr_boost_idxset(query, k=100):
    """(Merge mode) SET idx frame có ocr_text khớp. Lưu ý: main search giờ là Qdrant nên merge
    mode chỉ dùng được nếu Qdrant /collection có nhận tham số boost — hiện chưa. Giữ để tương thích."""
    try:
        return {d["idx"] for d in ocr_lookup(query, k) if d.get("idx") is not None}
    except Exception:
        return set()

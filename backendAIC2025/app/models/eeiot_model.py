from ..extensions import mongo2


def _search_db():
    """DB Mongo của teammate (nơi đã nạp data). Dùng chung client với mongo_search service
    (kết nối bằng MONGO_SEARCH_URI / MONGO_SEARCH_DB)."""
    from ..services.mongo_search import get_database

    return get_database()


def get_frames_collection():
    """Keyframe + OCR text — đọc từ Mongo teammate: collection `ocr_metadata`.
    (Field `ocr_text` khớp với ocr_controller của bạn; dùng cho OCR + enrich ASR + TRAKE.)"""
    return _search_db()["ocr_metadata"]


def get_asr_collection():
    """ASR segments — đọc từ Mongo teammate: collection `asr_metadata` (field `text`,
    `frame_start`, `frame_end`, `video_id`)."""
    return _search_db()["asr_metadata"]

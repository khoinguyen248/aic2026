import logging

from flask import Blueprint

# ASR/OCR (code của bạn) đọc Mongo teammate — import NHẸ (chỉ pymongo), luôn đăng ký được.
from ..controllers.asr_controller import asr_search
from ..controllers.caption_controller import caption_search
from ..controllers.ocr_controller import ocr_search

# TRAKE giờ chạy trên Qdrant (SearchEngine của teammate), KHÔNG kéo theo FAISS/beit3 -> import nhẹ.
from ..controllers.trake_controller import trake_search, trake_frame

# NOTE: /search/collection (main search) + /search/image do Qdrant của teammate đảm nhiệm.
search_bp = Blueprint("search", __name__)

search_bp.add_url_rule("/asr", view_func=asr_search, methods=["POST"])
search_bp.add_url_rule("/caption", view_func=caption_search, methods=["POST"])
search_bp.add_url_rule("/ocr", view_func=ocr_search, methods=["POST"])
search_bp.add_url_rule("/trake", view_func=trake_search, methods=["POST"])
search_bp.add_url_rule("/frame", view_func=trake_frame, methods=["GET"])

# /infoframes: ±10 frame quanh 1 keyframe, đọc trực tiếp từ Qdrant (import nhẹ, không faiss/beit3).
try:
    from ..controllers.infoframes_controller import frames_in_range, temporal_frames

    search_bp.add_url_rule("/infoframes", view_func=temporal_frames, methods=["POST"])
    search_bp.add_url_rule("/framerange", view_func=frames_in_range, methods=["POST"])
except Exception as _exc:  # noqa: BLE001
    logging.getLogger(__name__).warning("/search/infoframes disabled: %s", _exc)

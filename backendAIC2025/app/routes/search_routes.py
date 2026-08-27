from flask import Blueprint

# TRAKE giờ chạy trên Qdrant (SearchEngine của teammate), KHÔNG kéo theo FAISS/beit3 -> import nhẹ.
from ..controllers.trake_controller import trake_search, trake_frame

# NOTE: /search/collection (main search) + /search/image do Qdrant của teammate đảm nhiệm.
search_bp = Blueprint("search", __name__)

search_bp.add_url_rule("/trake", view_func=trake_search, methods=["POST"])
search_bp.add_url_rule("/frame", view_func=trake_frame, methods=["GET"])

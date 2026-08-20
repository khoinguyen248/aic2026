from flask import Blueprint

from ..controllers.qdrant_controller import (
    qdrant_health,
    qdrant_image_search,
    qdrant_text_search,
)


qdrant_bp = Blueprint("qdrant_search", __name__)


qdrant_bp.add_url_rule("/health", view_func=qdrant_health, methods=["GET"])
qdrant_bp.add_url_rule("/collection", view_func=qdrant_text_search, methods=["POST"])
qdrant_bp.add_url_rule("/image", view_func=qdrant_image_search, methods=["POST"])

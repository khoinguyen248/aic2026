from flask import Blueprint

from ..controllers.temporal_controller import temporal_frames


temporal_bp = Blueprint("temporal", __name__)
temporal_bp.add_url_rule("/infoframes", view_func=temporal_frames, methods=["POST"])
from flask import Blueprint

from ..controllers.mongo_search_controller import mongo_asr_search, mongo_ocr_search


mongo_search_bp = Blueprint("mongo_search", __name__)


mongo_search_bp.add_url_rule("/ocr", view_func=mongo_ocr_search, methods=["POST"])
# mongo_search_bp.add_url_rule("/asr", view_func=mongo_asr_search, methods=["POST"])

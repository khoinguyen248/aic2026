from flask import Blueprint
from ..controllers.search_controller import search_collection, temporal_frames
from ..controllers.trake_controller import trake_search

search_bp = Blueprint("search", __name__)

# POST vì chúng ta truyền nhiều tham số trong body
@search_bp.route("/collection", methods=["POST"])
def search_collection_route():
    return search_collection()

@search_bp.route("/infoframes", methods=["POST"])
def search_info_route():
    return temporal_frames()

@search_bp.route("/trake", methods=["POST"])
def trake_search_route():
    return trake_search()
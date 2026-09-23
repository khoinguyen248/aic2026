# app/controllers/caption_controller.py
"""Caption search over keyframe metadata in MongoDB."""

import os
import re
from difflib import SequenceMatcher

from flask import current_app, jsonify, request

from ..services.mongo_search import get_database


_CAPTION_PROJECT = {
    "_id": 0,
    "idx": 1,
    "video_id": 1,
    "L": 1,
    "V": 1,
    "frame_id": 1,
    "fps": 1,
    "keyframe_order": 1,
    "frame_stamp": 1,
    "caption": 1,
    "ocr_text": 1,
    "path": 1,
    "video_path": 1,
    "video_url": 1,
}


def _metadata_collection():
    return get_database()["ocr_metadata"]


def _has_caption_match():
    return {
        "$and": [
            {"caption": {"$exists": True}},
            {"caption": {"$type": "string"}},
            {"caption": {"$regex": r"\S"}},
        ]
    }


def _dedupe_key(doc):
    if doc.get("idx") is not None:
        return ("idx", doc["idx"])
    return ("frame", doc.get("video_id"), doc.get("frame_id"))


def _query_tokens(query: str) -> list[str]:
    return [token.lower() for token in re.findall(r"[\wÀ-ỹ]+", query) if len(token) >= 2]


def _caption_fallback(collection, query: str, k: int):
    tokens = _query_tokens(query)
    if not tokens:
        return []

    token_filters = [{"caption": {"$regex": re.escape(token), "$options": "i"}} for token in tokens]
    candidate_filter = {
        "$and": [
            {"caption": {"$exists": True}},
            {"caption": {"$type": "string"}},
            {"caption": {"$regex": r"\S"}},
            {"$or": token_filters},
        ]
    }

    candidate_limit = max(k * 20, 500)
    cursor = collection.find(candidate_filter, _CAPTION_PROJECT).limit(candidate_limit)
    ranked = []
    for doc in cursor:
        caption = str(doc.get("caption") or "")
        caption_lower = caption.lower()
        token_hits = sum(1 for token in tokens if token in caption_lower)
        similarity = SequenceMatcher(None, query.lower(), caption_lower).ratio()
        score = token_hits + similarity
        doc["score"] = score
        doc["match_type"] = "token_fallback"
        ranked.append(doc)

    min_hits = max(1, len(tokens) - 1)
    ranked = [doc for doc in ranked if doc["score"] >= min_hits]
    ranked.sort(key=lambda doc: doc["score"], reverse=True)
    return ranked[:k]


def caption_lookup(
    query: str,
    k: int = 10000,
    fuzzy_max_edits: int = 1,
    fuzzy_prefix_length: int = 1,
    fuzzy_max_expansions: int = 10000,
):
    query = (query or "").strip()
    if not query:
        return []

    collection = _metadata_collection()
    k = max(1, int(k))
    search_index = os.getenv("MONGO_CAPTION_SEARCH_INDEX", "caption_search")

    exact_results = []
    try:
        exact_pipeline = [
            {
                "$search": {
                    "index": search_index,
                    "text": {
                        "query": query,
                        "path": "caption",
                        "matchCriteria": "all",
                    },
                }
            },
            {"$match": _has_caption_match()},
            {"$limit": k},
            {"$project": {**_CAPTION_PROJECT, "score": {"$meta": "searchScore"}}},
        ]
        exact_results = list(collection.aggregate(exact_pipeline))
    except Exception as exc:
        current_app.logger.info("Caption exact $search failed: %s", exc)

    if len(exact_results) >= k:
        for doc in exact_results:
            doc["match_type"] = "exact"
        return exact_results[:k]

    fuzzy_results = []
    remaining = k - len(exact_results)
    try:
        fuzzy_pipeline = [
            {
                "$search": {
                    "index": search_index,
                    "text": {
                        "query": query,
                        "path": "caption",
                        # "matchCriteria": "all",
                        "fuzzy": {
                            "maxEdits": fuzzy_max_edits,
                            "prefixLength": fuzzy_prefix_length,
                            # "maxExpansions": fuzzy_max_expansions,
                        },
                    },
                }
            },
            {"$match": _has_caption_match()},
            {"$limit": max(remaining * 3, 100)},
            {"$project": {**_CAPTION_PROJECT, "score": {"$meta": "searchScore"}}},
        ]
        fuzzy_results = list(collection.aggregate(fuzzy_pipeline))
    except Exception as exc:
        current_app.logger.info("Caption fuzzy $search failed: %s", exc)

    exact_keys = {_dedupe_key(doc) for doc in exact_results}
    fuzzy_only = []
    for doc in fuzzy_results:
        if _dedupe_key(doc) in exact_keys:
            continue
        doc["match_type"] = "fuzzy"
        fuzzy_only.append(doc)

    for doc in exact_results:
        doc["match_type"] = "exact"

    results = exact_results + fuzzy_only[:remaining]
    if results:
        return results[:k]

    return _caption_fallback(collection, query, k)


def caption_search():
    """POST /search/caption {query, k} -> keyframes matched by caption."""
    try:
        data = request.get_json(force=True, silent=True) or {}
        query = data.get("query")
        k = int(data.get("k", data.get("limit", 10000))) or 10000

        results = caption_lookup(query, k)
        return jsonify({"ok": True, "count": len(results), "results": results}), 200
    except RuntimeError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 503
    except Exception as exc:
        current_app.logger.exception("caption_search failed: %s", exc)
        return jsonify({"ok": False, "error": str(exc)}), 500

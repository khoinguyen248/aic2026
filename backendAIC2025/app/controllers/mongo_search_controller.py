from __future__ import annotations

from flask import current_app, jsonify, request

from ..services.mongo_search import search_asr, search_ocr


def _integer_option(
    data: dict,
    name: str,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    try:
        value = int(data.get(name, default))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer") from exc

    return max(minimum, min(value, maximum))


def _fuzzy_options(data: dict):
    if "fuzzy_level" not in data:
        return (
            _integer_option(data, "max_edits", 1, 1, 2),
            _integer_option(data, "prefix_length", 1, 0, 10),
        )

    try:
        level = int(data["fuzzy_level"])
    except (TypeError, ValueError) as exc:
        raise ValueError("fuzzy_level must be one of: -1, 1, 2, 3") from exc

    levels = {
        -1: (None, 0),
        1: (1, 1),
        2: (2, 1),
        3: (2, 0),
    }
    if level not in levels:
        raise ValueError("fuzzy_level must be one of: -1, 1, 2, 3")

    return levels[level]


def _search_metadata(kind: str):
    if not current_app.config.get("MONGO_SEARCH_ENABLED", False):
        return jsonify(
            {
                "ok": False,
                "enabled": False,
                "error": "Mongo OCR/ASR search is disabled",
            }
        ), 503

    data = request.get_json(silent=True) or {}
    query = str(data.get("query") or data.get("text") or "").strip()
    if not query:
        return jsonify({"ok": False, "error": "query is required"}), 400

    try:
        limit = _integer_option(data, "limit", 20, 1, 1000)
        max_edits, prefix_length = _fuzzy_options(data)

        search_function = search_ocr if kind == "ocr" else search_asr
        results = search_function(
            query=query,
            limit=limit,
            max_edits=max_edits,
            prefix_length=prefix_length,
        )
        return jsonify(
            {
                "ok": True,
                "source": kind,
                "count": len(results),
                "results": results,
            }
        ), 200
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception as exc:
        current_app.logger.exception("Mongo %s search failed", kind.upper())
        return jsonify({"ok": False, "error": str(exc)}), 500


def mongo_ocr_search():
    return _search_metadata("ocr")


def mongo_asr_search():
    return _search_metadata("asr")

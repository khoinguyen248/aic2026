from __future__ import annotations

import threading

from flask import current_app, jsonify, request


_engine = None
_engine_lock = threading.Lock()
_allowed_models = {"beit3", "jina", "pe"}


def _get_engine():
    global _engine

    if _engine is not None:
        return _engine

    with _engine_lock:
        if _engine is None:
            from search_engine import SearchEngine

            _engine = SearchEngine()

    return _engine


def _model_from_request(value: object) -> str:
    model = str(value or "beit3").strip().lower()
    if model == "clip":
        model = "pe"
    if model not in _allowed_models:
        raise ValueError("model must be one of: beit3, jina, pe")
    return model


def _top_k_from_request(data: dict) -> int:
    try:
        top_k = int(data.get("top_k", data.get("k", 100)))
    except (TypeError, ValueError) as exc:
        raise ValueError("top_k must be an integer") from exc
    return max(1, min(top_k, 1000))


def qdrant_health():
    try:
        response = _get_engine().client.get_collections()
        names = sorted(collection.name for collection in response.collections)
        return jsonify({"ok": True, "collections": names}), 200
    except Exception as exc:
        current_app.logger.exception("Qdrant health check failed")
        return jsonify({"ok": False, "error": str(exc)}), 503


def qdrant_text_search():
    data = request.get_json(silent=True) or {}
    query = next(
        (
            str(value).strip()
            for value in (
                data.get("query"),
                data.get("query1"),
                data.get("text"),
            )
            if value and str(value).strip()
        ),
        "",
    )
    if not query:
        return jsonify({"ok": False, "error": "query is required"}), 400

    try:
        model = _model_from_request(data.get("model"))
        top_k = _top_k_from_request(data)
        results = _get_engine().text_search(query, model=model, top_k=top_k)
        return jsonify(
            {
                "ok": True,
                "model": model,
                "count": len(results),
                "results": results,
            }
        ), 200
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception as exc:
        current_app.logger.exception("Qdrant text search failed")
        return jsonify({"ok": False, "error": str(exc)}), 500


def qdrant_image_search():
    image_file = request.files.get("image")
    if image_file is None:
        return jsonify({"ok": False, "error": "image file is required"}), 400

    try:
        from PIL import Image

        model = _model_from_request(request.form.get("model"))
        top_k = _top_k_from_request(request.form)
        image = Image.open(image_file.stream).convert("RGB")
        results = _get_engine().image_search(image, model=model, top_k=top_k)
        return jsonify(
            {
                "ok": True,
                "model": model,
                "count": len(results),
                "results": results,
            }
        ), 200
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception as exc:
        current_app.logger.exception("Qdrant image search failed")
        return jsonify({"ok": False, "error": str(exc)}), 500

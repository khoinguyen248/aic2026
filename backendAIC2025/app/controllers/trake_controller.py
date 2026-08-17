# app/controllers/trake_controller.py
from flask import request, jsonify, current_app

from .search_controller import ensure_models
from ..models.eeiot_model import get_frames_collection
from ..services import trake_service


def trake_search():
    try:
        data = request.get_json(force=True, silent=True) or {}

        events = data.get("events")
        if not isinstance(events, list) or len(events) < 2 or not all(
            isinstance(e, str) and e.strip() for e in events
        ):
            return jsonify(
                {"ok": False, "error": "events phải là danh sách >= 2 chuỗi mô tả (theo thứ tự thời gian)"}
            ), 400

        language = bool(data.get("language", False))  # True = query nhập bằng tiếng Việt
        device = data.get("device", "cpu")
        top_m = data.get("top_m")
        top_videos = data.get("top_videos")
        max_combos = data.get("max_combos")

        events_text = events
        if language:
            from deep_translator import GoogleTranslator

            events_text = [GoogleTranslator(source="vi", target="en").translate(e) for e in events]

        collection = get_frames_collection()
        if collection is None:
            return jsonify({"ok": False, "error": "frames collection not available"}), 500

        models = ensure_models(device=device)
        clip_bundle = models["clip"]
        if clip_bundle[0] is None or models["index_clip"] is None:
            return jsonify({"ok": False, "error": "CLIP model/index chưa sẵn sàng (kiểm tra log khởi tạo)"}), 503

        result = trake_service.run_trake(
            events_text=events_text,
            clip_bundle=clip_bundle,
            device=device,
            faiss_index=models["index_clip"],
            mongo_collection=collection,
            top_m=int(top_m) if top_m else None,
            top_videos=int(top_videos) if top_videos else None,
            max_combos=int(max_combos) if max_combos else None,
        )

        status = 200 if result.get("ok") else 404
        return jsonify(result), status

    except Exception as e:
        current_app.logger.exception("trake_search failed: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500

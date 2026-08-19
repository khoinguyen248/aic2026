# app/controllers/trake_controller.py
import io

from flask import request, jsonify, current_app, send_file

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
                {"ok": False, "error": "events must be a list of >= 2 description strings (in chronological order)"}
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
            return jsonify({"ok": False, "error": "CLIP model/index not ready (check init logs)"}), 503

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


def trake_frame():
    """Verify tay: decode đúng 1 frame gốc từ video để hiện ảnh (kể cả frame tier-3 không phải
    keyframe). Cần có video (Case 1). Không có video -> 404 để UI tự fallback (link YouTube + ±10).

    GET /search/frame?L=<L>&V=<V>&frame_id=<int>
    """
    try:
        L = request.args.get("L")
        V = request.args.get("V")
        frame_id = request.args.get("frame_id", type=int)
        if L is None or V is None or frame_id is None:
            return jsonify({"ok": False, "error": "missing L / V / frame_id"}), 400

        collection = get_frames_collection()
        if collection is None:
            return jsonify({"ok": False, "error": "frames collection not available"}), 500

        video_path = trake_service.resolve_video_path(L, V, collection)
        if not video_path:
            return jsonify(
                {"ok": False, "error": f"Source video not found for {L}_{V} (no video on this machine / Case 2)"}
            ), 404

        try:
            import cv2
        except ImportError:
            return jsonify({"ok": False, "error": "opencv (cv2) not installed"}), 503

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return jsonify({"ok": False, "error": f"Cannot open video: {video_path}"}), 500
        cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, frame_id))
        ok, frame = cap.read()
        cap.release()
        if not ok:
            return jsonify({"ok": False, "error": f"Cannot read frame {frame_id}"}), 404

        ok2, buf = cv2.imencode(".jpg", frame)
        if not ok2:
            return jsonify({"ok": False, "error": "JPEG encoding failed"}), 500

        return send_file(io.BytesIO(buf.tobytes()), mimetype="image/jpeg")

    except Exception as e:
        current_app.logger.exception("trake_frame failed: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500

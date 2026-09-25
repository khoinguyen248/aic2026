# app/controllers/trake_controller.py
"""TRAKE trên hạ tầng CHUNG — dùng SearchEngine (Qdrant) của teammate, KHÔNG FAISS."""
import io

from flask import request, jsonify, current_app, send_file

from ..services import trake_service

_ALLOWED_MODELS = {"beit3", "jina", "pe"}


def _get_engine():
    """Dùng chung singleton SearchEngine với qdrant_controller."""
    from .qdrant_controller import _get_engine as _qe

    return _qe()


def _model_from_request(value):
    model = str(value or "beit3").strip().lower()
    if model == "clip":
        model = "pe"
    if model not in _ALLOWED_MODELS:
        raise ValueError("model must be one of: beit3, jina, pe")
    return model


def trake_search():
    try:
        data = request.get_json(force=True, silent=True) or {}

        events = data.get("events")
        if not isinstance(events, list) or len(events) < 2:
            return jsonify(
                {"ok": False, "error": "events must be a list of >= 2 items (in chronological order)"}
            ), 400
        events = [(str(e) if e is not None else "") for e in events]

        model = _model_from_request(data.get("model"))
        language = bool(data.get("language", False))  # True = query nhập bằng tiếng Việt
        top_m = data.get("top_m")
        top_videos = data.get("top_videos")
        max_combos = data.get("max_combos")
        max_event_gap_s = data.get("max_event_gap_s")  # None/0/"" -> không giới hạn khoảng cách event

        # OCR/ASR theo TỪNG event (tùy chọn): mảng song song với events, "" = không dùng.
        # KHÔNG dịch (OCR/ASR khớp dữ liệu tiếng Việt trong Mongo).
        def _parse_side(key):
            arr = data.get(key)
            if arr is None:
                return None
            if not isinstance(arr, list):
                raise ValueError(f"{key} must be a list of strings aligned with events")
            arr = [(str(x) if x is not None else "") for x in arr]
            if any(s.strip() for s in arr):
                return arr
            return None

        events_ocr = _parse_side("events_ocr")
        events_asr = _parse_side("events_asr")

        # Mỗi event phải có ÍT NHẤT 1 trong: mô tả hình / OCR / ASR (không bắt buộc mô tả hình).
        def _side_has(arr, i):
            return bool(arr and i < len(arr) and str(arr[i]).strip())

        for i, e in enumerate(events):
            if not (e.strip() or _side_has(events_ocr, i) or _side_has(events_asr, i)):
                return jsonify(
                    {"ok": False, "error": f"event {i + 1} rỗng: cần mô tả hình HOẶC OCR HOẶC ASR"}
                ), 400

        events_text = events
        if language:
            try:
                from deep_translator import GoogleTranslator

                # Chỉ dịch event có mô tả hình; event rỗng (chỉ OCR/ASR) giữ nguyên "".
                events_text = [
                    GoogleTranslator(source="vi", target="en").translate(e) if e.strip() else e
                    for e in events
                ]
            except Exception as e:  # thiếu package / mạng lỗi -> dùng nguyên văn, không làm hỏng search
                current_app.logger.warning("TRAKE translate thất bại, dùng text gốc: %s", e)
                events_text = events

        try:
            engine = _get_engine()
        except Exception as e:
            return jsonify({"ok": False, "error": f"Qdrant engine not available: {e}"}), 503

        result = trake_service.run_trake(
            events_text=events_text,
            engine=engine,
            model=model,
            top_m=int(top_m) if top_m else None,
            top_videos=int(top_videos) if top_videos else None,
            max_combos=int(max_combos) if max_combos else None,
            events_ocr=events_ocr,
            events_asr=events_asr,
            max_event_gap_s=float(max_event_gap_s) if max_event_gap_s else None,
        )

        return jsonify(result), (200 if result.get("ok") else 404)

    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except Exception as e:
        current_app.logger.exception("trake_search failed: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500


def _video_path_for(engine, model, video_id):
    """Lấy video_path từ payload Qdrant (1 point bất kỳ của video), rồi ghép VIDEO_ROOT."""
    from qdrant_client.http.models import FieldCondition, Filter, MatchValue

    points, _ = engine.client.scroll(
        collection_name=engine.collection_name(model),
        scroll_filter=Filter(must=[FieldCondition(key="video_id", match=MatchValue(value=video_id))]),
        limit=1,
        with_payload=True,
        with_vectors=False,
    )
    if not points:
        return None
    payload = points[0].payload or {}
    return trake_service.resolve_video_path(payload.get("video_path"), video_id)


def trake_frame():
    """Verify tay: decode đúng 1 frame gốc từ video (kể cả frame tier-3 không phải keyframe).
    Cần VIDEO_ROOT + video (Case 1). Không có -> 404 để UI fallback (link YouTube + ±10).

    GET /search/frame?L=<L>&V=<V>&frame_id=<int>&model=<beit3|jina|pe>
    """
    try:
        L = request.args.get("L")
        V = request.args.get("V")
        frame_id = request.args.get("frame_id", type=int)
        if L is None or V is None or frame_id is None:
            return jsonify({"ok": False, "error": "missing L / V / frame_id"}), 400

        model = _model_from_request(request.args.get("model"))
        video_id = f"L{L}_V{V}"

        try:
            engine = _get_engine()
        except Exception as e:
            return jsonify({"ok": False, "error": f"Qdrant engine not available: {e}"}), 503

        video_path = _video_path_for(engine, model, video_id)
        if not video_path:
            return jsonify(
                {"ok": False, "error": f"Source video not found for {video_id} (no video on this machine / Case 2)"}
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

    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except Exception as e:
        current_app.logger.exception("trake_frame failed: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500

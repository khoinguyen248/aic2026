from __future__ import annotations

import re

from flask import current_app, jsonify, request

# Dùng lại engine Qdrant singleton của main search (import NHẸ, không kéo faiss/beit3).
from .qdrant_controller import _get_engine, _model_from_request
from ..services.mongo_search import get_database

# Số frame lấy mỗi bên của frame gốc.
NEIGHBORS = 10

# Trần số keyframe trả về cho 1 khoảng ASR (tránh payload quá lớn với đoạn dài).
RANGE_LIMIT = 120


def _video_id_from(L: str, V: str) -> str:
    """Ghép video_id từ L + V, ví dụ ('21','001') -> 'L21_V001'.

    Prefix theo quy ước dữ liệu: số <= 20 là 'K', còn lại là 'L'.
    """
    prefix = "L"
    m = re.match(r"(\d+)", L or "")
    if m and int(m.group(1)) <= 20:
        prefix = "K"
    return f"{prefix}{L}_V{V}"


def _to_int(val, default=0):
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def _scroll_video_points(engine, collection: str, video_id: str):
    """Lấy toàn bộ keyframe của 1 video từ Qdrant (payload, không vector)."""
    from qdrant_client.http.models import FieldCondition, Filter, MatchValue

    flt = Filter(must=[FieldCondition(key="video_id", match=MatchValue(value=video_id))])
    payloads = []
    offset = None
    while True:
        batch, offset = engine.client.scroll(
            collection_name=collection,
            scroll_filter=flt,
            limit=1000,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        payloads.extend(dict(p.payload or {}) for p in batch)
        if offset is None:
            break
    return payloads


def _scroll_video_from_mongo(video_id):
    """Fallback khi Qdrant chưa có video: đọc keyframe từ ocr_metadata, dựng lại path
    'Keyframes/<video_id>/<frame 6 số>.webp' cho khớp frame-server (route /Keyframes)."""
    proj = {"_id": 0, "idx": 1, "video_id": 1, "L": 1, "V": 1, "frame_id": 1,
            "keyframe_order": 1, "frame_stamp": 1, "video_url": 1}
    out = []
    for d in get_database()["ocr_metadata"].find({"video_id": video_id}, proj):
        d["path"] = f"Keyframes/{video_id}/{_to_int(d.get('frame_id')):06d}.webp"
        out.append(d)
    return out


def temporal_frames():
    """Trả về frame gốc kèm ±10 keyframe cùng video (đọc từ Qdrant).

    Nhận vào (JSON):
      - ``video_id`` (ưu tiên) hoặc ``L`` + ``V`` để xác định video.
      - ``idx`` (main search) HOẶC ``frame_id`` (TRAKE, không có idx) để xác định frame gốc.
      - ``model`` (tùy chọn, mặc định beit3).
    Trả về ``results`` đã sort theo keyframe_order, kèm ``target_idx`` để FE tô viền đỏ.
    """
    try:
        data = request.get_json(force=True, silent=True) or {}
        print("-----------temporal_frames-------")
        print("data: ", data)
        L = str(data.get("L") or "").strip()
        V = str(data.get("V") or "").strip()
        video_id = str(data.get("video_id") or "").strip()
        idx_raw = data.get("idx")
        frame_id_raw = data.get("frame_id")

        if not video_id:
            if not (L and V):
                return jsonify({"ok": False, "error": "missing video_id or L+V"}), 400
            video_id = _video_id_from(L, V)

        try:
            model = _model_from_request(data.get("model"))
        except ValueError:
            model = "beit3"

        # Ưu tiên Qdrant; lỗi/không có video (N/M/S chưa nạp embedding, hoặc Qdrant đang load) -> fallback Mongo.
        items = []
        try:
            engine = _get_engine()
            collection = engine.collection_name(model)
            items = _scroll_video_points(engine, collection, video_id)
        except Exception as exc:  # noqa: BLE001
            current_app.logger.info("infoframes Qdrant lỗi (%s) -> fallback ocr_metadata", exc)
        if not items:
            items = _scroll_video_from_mongo(video_id)
        if not items:
            return jsonify({"ok": False, "error": f"video {video_id} not found"}), 404

        # Sắp theo thứ tự keyframe trong video (fallback frame_id nếu thiếu).
        items.sort(key=lambda d: (_to_int(d.get("keyframe_order"), _to_int(d.get("frame_id")))))

        # Xác định frame gốc: ưu tiên idx, nếu không thì frame_id gần nhất.
        target_pos = None
        if idx_raw is not None and str(idx_raw) != "":
            idx = _to_int(idx_raw, None)
            target_pos = next((i for i, d in enumerate(items) if _to_int(d.get("idx")) == idx), None)
        # idx không khớp (idx Qdrant ≠ idx Mongo cho video N/M/S) -> tra theo frame_id (bền hơn).
        if target_pos is None and frame_id_raw is not None and str(frame_id_raw) != "":
            frame_id = _to_int(frame_id_raw)
            target_pos = min(
                range(len(items)),
                key=lambda i: abs(_to_int(items[i].get("frame_id")) - frame_id),
            )
        if target_pos is None:
            return jsonify({"ok": False, "error": f"frame not found in {video_id}"}), 404

        target_idx = items[target_pos].get("idx")

        # full=true (hoặc window<=0) -> trả TOÀN BỘ keyframe của video; ngược lại ±window (mặc định 10).
        full = bool(data.get("full"))
        win = _to_int(data.get("window"), NEIGHBORS)
        if full or win <= 0:
            window = items
        else:
            start = max(0, target_pos - win)
            end = min(len(items), target_pos + win + 1)  # +1 để include frame gốc
            window = items[start:end]

        return jsonify(
            {"ok": True, "count": len(window), "total": len(items), "results": window, "target_idx": target_idx}
        ), 200

    except Exception as e:
        current_app.logger.exception("temporal_frames failed: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500


def frames_in_range():
    """Trả về các keyframe của 1 video có frame_id nằm trong [frame_start, frame_end].

    Dùng cho kết quả ASR: mỗi đoạn lời nói có khoảng frame -> hiện luôn keyframe
    trong khoảng đó (ảnh keyframe giống OCR/main search, đọc từ Qdrant).

    Nhận vào (JSON):
      - ``video_id`` (ưu tiên) hoặc ``L`` + ``V``.
      - ``frame_start`` + ``frame_end`` (int).
      - ``model`` (tùy chọn, mặc định beit3).
    """
    try:
        from qdrant_client.http.models import FieldCondition, Filter, MatchValue, Range

        print("-------in frame_range func----------")
        data = request.get_json(force=True, silent=True) or {}
        L = str(data.get("L") or "").strip()
        V = str(data.get("V") or "").strip()
        video_id = str(data.get("video_id") or "").strip()
        fs = _to_int(data.get("frame_start"), None)
        fe = _to_int(data.get("frame_end"), None)
        print("L:", L)
        print("V:", V)
        print("video_id:", video_id)
        print("fs:", fs)
        print("fe:", fe)
        print("data", data)

        if not video_id:
            if not (L and V):
                return jsonify({"ok": False, "error": "missing video_id or L+V"}), 400
            video_id = _video_id_from(L, V)
        if fs is None or fe is None:
            return jsonify({"ok": False, "error": "missing frame_start/frame_end"}), 400
        if fs > fe:
            fs, fe = fe, fs

        try:
            model = _model_from_request(data.get("model"))
        except ValueError:
            model = "beit3"

        items = []
        try:
            engine = _get_engine()
            collection = engine.collection_name(model)
            flt = Filter(
                must=[
                    FieldCondition(key="video_id", match=MatchValue(value=video_id)),
                    FieldCondition(key="frame_id", range=Range(gte=fs, lte=fe)),
                ]
            )
            offset = None
            while len(items) < RANGE_LIMIT + 1:
                batch, offset = engine.client.scroll(
                    collection_name=collection,
                    scroll_filter=flt,
                    limit=1000,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False,
                )
                items.extend(dict(p.payload or {}) for p in batch)
                if offset is None:
                    break
        except Exception as exc:  # noqa: BLE001
            current_app.logger.info("framerange Qdrant lỗi (%s) -> fallback Mongo", exc)

        # Batch2 (S/M/N) chỉ nằm ở collection jina -> beit3 rỗng; hoặc video chưa vào Qdrant.
        # Fallback ocr_metadata (Mongo) — không phụ thuộc model.
        if not items:
            proj = {"_id": 0, "idx": 1, "video_id": 1, "L": 1, "V": 1,
                    "frame_id": 1, "frame_stamp": 1, "video_url": 1}
            for d in get_database()["ocr_metadata"].find(
                {"video_id": video_id, "frame_id": {"$gte": fs, "$lte": fe}}, proj
            ).sort("frame_id", 1).limit(RANGE_LIMIT + 1):
                d["path"] = f"Keyframes/{video_id}/{_to_int(d.get('frame_id')):06d}.webp"
                items.append(d)

        items.sort(key=lambda d: _to_int(d.get("frame_id")))
        total = len(items)
        truncated = total > RANGE_LIMIT
        window = items[:RANGE_LIMIT]

        return jsonify(
            {"ok": True, "count": len(window), "total": total, "truncated": truncated, "results": window}
        ), 200

    except Exception as e:
        current_app.logger.exception("frames_in_range failed: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500

"""Endpoint nhẹ để lấy keyframe lân cận, không phụ thuộc FAISS hay model search."""

from __future__ import annotations

import json
from pathlib import Path

from flask import current_app, jsonify, request


def _number(value: object, prefix: str, width: int | None = None) -> str:
    raw = str(value or "").strip().upper()
    print("="*10, raw)
    if raw.startswith(prefix):
        raw = raw[len(prefix) :]
    if not raw.isdigit():
        raise ValueError(f"{prefix} must be numeric")
    number = int(raw)
    return f"{number:0{width}d}" if width else str(number)


def _load_video_metadata(l_value: object, v_value: object) -> list[dict]:
    l_number = _number(l_value, "L")
    v_number = _number(v_value, "V", width=3)
    metadata_root = Path(current_app.config["METADATA_ROOT"])
    path = metadata_root / "ocr" / f"L{l_number}_V{v_number}.json"

    if not path.is_file():
        raise FileNotFoundError(f"Metadata file not found: {path.name}")

    with path.open("r", encoding="utf-8") as source:
        items = json.load(source)
    if not isinstance(items, list):
        raise ValueError(f"Metadata file is not an array: {path.name}")

    # keyframe_order là thứ tự thực tế trong cùng video; idx là global id, không dùng để
    # cộng/trừ vì các video liên tiếp không có idx liên tục.
    return sorted(items, key=lambda item: int(item.get("keyframe_order", 0)))


def temporal_frames():
    """POST /search/infoframes: trả target và tối đa 10 keyframe mỗi phía.

    Ưu tiên bản Qdrant (nhận cả idx LẪN frame_id, có path keyframe -> dùng cho TRAKE).
    Chỉ fallback sang metadata JSON local khi có idx mà bản Qdrant lỗi.
    """
    data = request.get_json(silent=True) or {}
    print("data", data)

    # TRAKE gửi frame_id (không có idx) -> ủy quyền sang bản Qdrant xử lý cả 2 trường hợp.
    try:
        from .infoframes_controller import temporal_frames as qdrant_temporal_frames
        return qdrant_temporal_frames()
    except Exception as exc:  # noqa: BLE001
        current_app.logger.info("infoframes(Qdrant) lỗi (%s) -> thử metadata JSON local", exc)

    try:
        if "idx" not in data or str(data.get("idx")) == "":
            raise ValueError("idx is required")

        target_idx = int(data["idx"])
        print("target_idx", target_idx)
        window = max(1, min(int(data.get("window", 10)), 100))
        items = _load_video_metadata(data.get("L"), data.get("V"))
        target_position = next(
            (position for position, item in enumerate(items) if int(item.get("idx", -1)) == target_idx),
            None,
        )
        if target_position is None:
            return jsonify({"ok": False, "error": f"idx {target_idx} not found in this video"}), 404

        start = max(0, target_position - window)
        end = min(len(items), target_position + window + 1)
        result = items[start:end]
        return jsonify({"ok": True, "count": len(result), "results": result}), 200
    except (TypeError, ValueError) as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except FileNotFoundError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 404
    except Exception as exc:  # noqa: BLE001
        current_app.logger.exception("temporal_frames failed")
        return jsonify({"ok": False, "error": str(exc)}), 500

# app/controllers/traffic_controller.py
"""Traffic search — lọc frame video giao thông (N) theo detection/segmentation.

Lọc object ĐỘNG: `objects=[{name, min}]` -> query counts.<name> >= min (tên COCO: car, truck,
bus, person, motorcycle, "traffic light"...). Thêm min_vehicle (tổng xe) + density (seg_vehicle_ratio).

- Standalone: query detseg_metadata -> frame.
- Hybrid: nhận `frames` (list {video_id, frame_id} semantic) -> chỉ giữ frame khớp, giữ thứ tự semantic.

Ảnh: path `<video_id>/<frame_id:06d>.webp` khớp runtime-data/keyframes. Join ocr_metadata lấy idx/video_url/fps.
"""
from flask import request, jsonify, current_app

from ..services.mongo_search import get_database

_OCR_DISPLAY = {
    "_id": 0, "idx": 1, "video_id": 1, "L": 1, "V": 1, "frame_id": 1,
    "fps": 1, "frame_stamp": 1, "video_url": 1,
}


def _int(v, default=None):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _num(v, default=None):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _keyframe_path(video_id, frame_id):
    # frame-server serve ở route /Keyframes -> path phải có prefix "Keyframes/" (video_id phẳng).
    try:
        return f"Keyframes/{video_id}/{int(frame_id):06d}.webp"
    except (TypeError, ValueError):
        return None


def _parse_relations(data):
    """[{a, rel, b, c?}] rel ∈ left/right/above/below/between. Toạ độ ảnh: x phải+, y xuống+."""
    out = []
    for r in (data.get("relations") or []):
        if not isinstance(r, dict):
            continue
        a = str(r.get("a") or "").strip().lower()
        b = str(r.get("b") or "").strip().lower()
        rel = str(r.get("rel") or "").strip().lower()
        c = str(r.get("c") or "").strip().lower()
        if a and b and rel in ("left", "right", "above", "below", "between"):
            if rel == "between" and not c:
                continue
            out.append({"a": a, "b": b, "rel": rel, "c": c})
    return out


def _passes_relations(dets, relations):
    """dets [{c,x,y}] có thoả TẤT CẢ quan hệ (AND) không."""
    if not relations:
        return True
    by = {}
    for d in dets or []:
        by.setdefault(d.get("c"), []).append(d)
    for r in relations:
        A, B = by.get(r["a"]), by.get(r["b"])
        rel = r["rel"]
        if rel == "between":
            C = by.get(r["c"])
            if not (A and B and C):
                return False
            ok = any((bb["x"] < aa["x"] < cc["x"]) or (cc["x"] < aa["x"] < bb["x"])
                     for aa in A for bb in B for cc in C)
        else:
            if not (A and B):
                return False
            if rel == "left":
                ok = any(aa["x"] < bb["x"] for aa in A for bb in B)
            elif rel == "right":
                ok = any(aa["x"] > bb["x"] for aa in A for bb in B)
            elif rel == "above":
                ok = any(aa["y"] < bb["y"] for aa in A for bb in B)
            else:  # below
                ok = any(aa["y"] > bb["y"] for aa in A for bb in B)
        if not ok:
            return False
    return True


def _build_query(data):
    query = {"frame_id": {"$gte": 0}}  # bỏ row rác frame_id=-1

    # Lọc object động: [{name, min}] -> counts.<name> >= min.
    for o in (data.get("objects") or []):
        if not isinstance(o, dict):
            continue
        name = str(o.get("name") or "").strip().lower()
        n = _int(o.get("min"))
        if name and n and n > 0:
            query[f"counts.{name}"] = {"$gte": n}

    mv = _int(data.get("min_vehicle"))
    if mv and mv > 0:
        query["vehicle_count"] = {"$gte": mv}

    dmin, dmax = _num(data.get("density_min")), _num(data.get("density_max"))
    if dmin is not None or dmax is not None:
        rng = {}
        if dmin is not None:
            rng["$gte"] = dmin
        if dmax is not None:
            rng["$lte"] = dmax
        query["seg_vehicle_ratio"] = rng

    # Quan hệ toạ độ: class liên quan phải xuất hiện (thu hẹp cursor trước khi lọc không gian).
    for r in _parse_relations(data):
        for cls in (r["a"], r["b"], r.get("c")):
            if cls:
                query.setdefault(f"counts.{cls}", {"$gte": 1})

    vid = str(data.get("video_id") or "").strip()
    if vid:
        query["video_id"] = vid
    return query


def _decorate(rows, db):
    disp = {}
    if rows:
        or_clause = [{"video_id": r["video_id"], "frame_id": r["frame_id"]} for r in rows]
        for d in db["ocr_metadata"].find({"$or": or_clause}, _OCR_DISPLAY):
            disp[(d.get("video_id"), d.get("frame_id"))] = d
    out = []
    for r in rows:
        d = disp.get((r["video_id"], r["frame_id"]), {})
        counts = r.get("counts") or {}
        top = sorted(counts.items(), key=lambda x: -x[1])[:6]
        out.append({
            "idx": d.get("idx"),
            "video_id": r["video_id"],
            "L": d.get("L"),
            "V": d.get("V"),
            "frame_id": r["frame_id"],
            "fps": d.get("fps"),
            "frame_stamp": d.get("frame_stamp"),
            "path": _keyframe_path(r["video_id"], r["frame_id"]),
            "video_url": d.get("video_url"),
            "vehicle_count": r.get("vehicle_count"),
            "seg_vehicle_ratio": r.get("seg_vehicle_ratio"),
            "counts": counts,
            "text": " · ".join(f"{k} {v}" for k, v in top),
        })
    return out


def traffic_search():
    """POST /search/traffic — standalone hoặc hybrid (kèm `frames`)."""
    try:
        data = request.get_json(force=True, silent=True) or {}
        k = max(1, min(_int(data.get("k"), 100) or 100, 500))
        query = _build_query(data)
        relations = _parse_relations(data)
        db = get_database()
        det = db["detseg_metadata"]

        frames = data.get("frames")
        if isinstance(frames, list) and frames:
            pairs = []
            for f in frames:
                v, fid = str(f.get("video_id") or ""), _int(f.get("frame_id"))
                if v and fid is not None:
                    pairs.append((v, fid))
            det_map = {}
            if pairs:
                q = dict(query)
                q["$or"] = [{"video_id": v, "frame_id": fid} for (v, fid) in pairs]
                for d in det.find(q, {"_id": 0}):
                    det_map[(d["video_id"], d["frame_id"])] = d
            rows = [det_map[p] for p in pairs
                    if p in det_map and _passes_relations(det_map[p].get("dets"), relations)][:k]
        else:
            sort_field = "seg_vehicle_ratio" if data.get("sort") == "congestion" else "vehicle_count"
            cursor = det.find(query, {"_id": 0}).sort(sort_field, -1)
            rows, scanned = [], 0
            for d in cursor:
                scanned += 1
                if _passes_relations(d.get("dets"), relations):
                    rows.append(d)
                    if len(rows) >= k:
                        break
                if scanned >= 8000:  # trần quét để không treo khi lọc quan hệ
                    break

        return jsonify({"ok": True, "count": len(rows), "results": _decorate(rows, db)}), 200

    except RuntimeError as e:
        return jsonify({"ok": False, "error": str(e)}), 503
    except Exception as e:
        current_app.logger.exception("traffic_search failed: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500

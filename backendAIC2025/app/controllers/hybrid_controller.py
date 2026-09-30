# app/controllers/hybrid_controller.py
"""Hybrid filter — lọc lại tập frame (đã có từ semantic Top-K) theo OCR / ASR.

Pipeline: semantic search -> Top-K frames -> POST danh sách frame + query -> giữ frame khớp.
Giữ NGUYÊN thứ tự semantic (chỉ lọc, không rerank).
"""
from flask import request, jsonify, current_app

from ..services.mongo_search import get_database


def _int(v, default=None):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _pairs(data):
    out = []
    for f in (data.get("frames") or []):
        v = str(f.get("video_id") or "")
        fid = _int(f.get("frame_id"))
        if v and fid is not None:
            out.append((v, fid))
    return out


def ocr_filter():
    """POST /search/ocr_filter {frames:[{video_id,frame_id}], query} -> frame có OCR khớp query.

    Dùng CHÍNH Atlas fuzzy search (ocr_frame_ids_in_video) theo từng video như OCR standalone,
    rồi GIAO với tập ứng viên. Đảm bảo tiêu chí lọc == tiêu chí search (không dùng regex nguyên cụm
    quá chặt). Giữ nguyên thứ tự semantic đầu vào.
    """
    try:
        from ..services.mongo_search import ocr_frame_ids_in_video

        data = request.get_json(force=True, silent=True) or {}
        q = (data.get("query") or "").strip()
        pairs = _pairs(data)
        if not q or not pairs:
            return jsonify({"ok": True, "count": 0, "results": []}), 200

        # Với mỗi video trong tập ứng viên: lấy các frame_id khớp OCR (Atlas fuzzy, scoped theo video).
        vids = {v for (v, _) in pairs}
        matched_fids = {}
        for vid in vids:
            try:
                got = ocr_frame_ids_in_video(q, vid, limit=200)
            except Exception:
                got = []
            matched_fids[vid] = {int(fid) for fid, _path in got if fid is not None}

        results = [{"video_id": v, "frame_id": fid} for (v, fid) in pairs
                   if fid in matched_fids.get(v, set())]
        return jsonify({"ok": True, "count": len(results), "results": results}), 200
    except Exception as e:
        current_app.logger.exception("ocr_filter failed: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500


def frame_detail():
    """POST /search/frame_detail {video_id, frame_id} -> gộp metadata caption/OCR/ASR/objects của 1 frame.

    Kết quả semantic (Qdrant) chỉ có score/path; caption/OCR/ASR/counts nằm ở Mongo nên phải tra thêm
    để panel "Chi tiết frame" hiển thị đầy đủ.
    """
    try:
        data = request.get_json(force=True, silent=True) or {}
        vid = str(data.get("video_id") or "")
        fid = _int(data.get("frame_id"))
        if not vid or fid is None:
            return jsonify({"ok": False, "error": "thiếu video_id / frame_id"}), 400

        db = get_database()
        out = {"video_id": vid, "frame_id": fid}

        ocr = db["ocr_metadata"].find_one(
            {"video_id": vid, "frame_id": fid},
            {"_id": 0, "caption": 1, "ocr_text": 1, "fps": 1, "frame_stamp": 1,
             "video_url": 1, "path": 1, "L": 1, "V": 1},
        )
        if ocr:
            for k, v in ocr.items():
                if v not in (None, ""):
                    out[k] = v

        det = db["detseg_metadata"].find_one(
            {"video_id": vid, "frame_id": fid},
            {"_id": 0, "counts": 1, "vehicle_count": 1, "seg_vehicle_ratio": 1,
             "traffic_density_proxy": 1, "timestamp_s": 1},
        )
        if det:
            if det.get("counts"):
                out["counts"] = det["counts"]
            for k in ("vehicle_count", "seg_vehicle_ratio", "traffic_density_proxy", "timestamp_s"):
                if det.get(k) is not None:
                    out[k] = det[k]

        asr = db["asr_metadata"].find_one(
            {"video_id": vid, "frame_start": {"$lte": fid}, "frame_end": {"$gte": fid}},
            {"_id": 0, "text": 1},
        )
        if asr and asr.get("text"):
            out["asr_text"] = asr["text"]

        return jsonify({"ok": True, "detail": out}), 200
    except Exception as e:
        current_app.logger.exception("frame_detail failed: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500


def asr_filter():
    """POST /search/asr_filter {frames, query} -> frame nằm trong đoạn ASR có lời nói khớp query."""
    try:
        from ..services.mongo_search import asr_ranges_in_video

        data = request.get_json(force=True, silent=True) or {}
        q = (data.get("query") or "").strip()
        pairs = _pairs(data)
        if not q or not pairs:
            return jsonify({"ok": True, "count": 0, "results": []}), 200

        # Với mỗi video: lấy các khoảng (frame_start,frame_end) khớp ASR (Atlas fuzzy, scoped) như ASR standalone.
        vids = {v for (v, _) in pairs}
        ranges = {}
        for vid in vids:
            try:
                rs = asr_ranges_in_video(q, vid, limit=50)
            except Exception:
                rs = []
            ranges[vid] = [(min(a, b), max(a, b)) for (a, b) in rs]

        results = [{"video_id": v, "frame_id": fid} for (v, fid) in pairs
                   if any(a <= fid <= b for (a, b) in ranges.get(v, []))]
        return jsonify({"ok": True, "count": len(results), "results": results}), 200
    except Exception as e:
        current_app.logger.exception("asr_filter failed: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500

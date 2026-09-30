"""Import detection/segmentation parquet -> Mongo `detseg_metadata` (1 doc / frame).

Chạy TỪ HOST (Mongo trong Docker ở localhost:27017). Cần MONGO_SEARCH_URI + pyarrow.

Ví dụ (PowerShell, từ thư mục repo aic2026):
    $env:MONGO_SEARCH_URI="mongodb://aicadmin:PASSWORD@localhost:27017/?authSource=admin&directConnection=true"
    $env:MONGO_SEARCH_DB="aic2026"
    python backendAIC2025/scripts/import_detseg.py detseg

Khoá join với keyframe/OCR: (video_id, frame_id) — trong parquet frame_id = cột `frame_idx`.
Idempotent: xoá sạch collection rồi nạp lại.
"""
import glob
import json
import os
import sys

import pyarrow.parquet as pq
from pymongo import MongoClient

BATCH = 5000

# Cột giữ lại. `object_counts_json` -> dict `counts`; `detections_json` -> list `dets` (class + center) cho toạ độ.
_KEEP = [
    "video_id", "frame_idx", "timestamp_s",
    "vehicle_count", "seg_road", "seg_vehicle_ratio", "traffic_density_proxy",
    "object_counts_json", "detections_json",
]
_FLOAT_FIELDS = ["timestamp_s", "seg_road", "seg_vehicle_ratio", "traffic_density_proxy"]


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _i(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def _counts(raw):
    """object_counts_json (str/dict) -> {class: count} chỉ giữ count > 0 (tiết kiệm, count thiếu = 0)."""
    if not raw:
        return {}
    try:
        obj = raw if isinstance(raw, dict) else json.loads(raw)
    except (TypeError, ValueError):
        return {}
    out = {}
    for name, val in obj.items():
        n = _i(val)
        if n > 0:
            out[str(name).strip().lower()] = n
    return out


def _dets(raw):
    """detections_json (str/list) -> [{c: class, x: center_x, y: center_y}] cho truy vấn toạ độ tương đối."""
    if not raw:
        return []
    try:
        arr = raw if isinstance(raw, list) else json.loads(raw)
    except (TypeError, ValueError):
        return []
    out = []
    for d in arr:
        if not isinstance(d, dict):
            continue
        cls = str(d.get("class") or "").strip().lower()
        x, y = _f(d.get("center_x")), _f(d.get("center_y"))
        if cls and x is not None and y is not None:
            out.append({"c": cls, "x": round(x, 1), "y": round(y, 1)})
    return out


def docs_from_parquet(path):
    pf = pq.ParquetFile(path)
    have = set(pf.schema.names)
    cols = [c for c in _KEEP if c in have]
    for rg in range(pf.num_row_groups):
        table = pf.read_row_group(rg, columns=cols)
        for row in table.to_pylist():
            vid = row.get("video_id")
            if not vid:
                continue
            doc = {"video_id": vid, "frame_id": _i(row.get("frame_idx")),
                   "vehicle_count": _i(row.get("vehicle_count")),
                   "counts": _counts(row.get("object_counts_json")),
                   "dets": _dets(row.get("detections_json"))}
            for k in _FLOAT_FIELDS:
                doc[k] = _f(row.get(k))
            yield doc


def main():
    detseg_dir = sys.argv[1] if len(sys.argv) > 1 else "detseg"

    uri = os.getenv("MONGO_SEARCH_URI")
    if not uri:
        sys.exit("Thiếu MONGO_SEARCH_URI (env).")
    dbname = os.getenv("MONGO_SEARCH_DB", "aic2026")

    client = MongoClient(uri, serverSelectionTimeoutMS=8000)
    client.admin.command("ping")
    db = client[dbname]
    coll = db["detseg_metadata"]
    print(f"Ket noi OK -> {dbname}.detseg_metadata")

    files = sorted(glob.glob(os.path.join(detseg_dir, "**", "*.parquet"), recursive=True))
    if not files:
        sys.exit(f"Khong tim thay parquet trong {detseg_dir}")
    print(f"parquet files: {len(files)}")

    coll.delete_many({})
    buf, total = [], 0
    for fp in files:
        print(f"  reading {os.path.basename(fp)}")
        for doc in docs_from_parquet(fp):
            buf.append(doc)
            if len(buf) >= BATCH:
                coll.insert_many(buf, ordered=False)
                total += len(buf)
                buf = []
    if buf:
        coll.insert_many(buf, ordered=False)
        total += len(buf)
    print(f"imported {total} docs")

    coll.create_index([("video_id", 1), ("frame_id", 1)])
    coll.create_index("vehicle_count")
    coll.create_index("seg_vehicle_ratio")
    # Wildcard: index mọi counts.<class> -> lọc object bất kỳ (counts.car, counts.truck...) nhanh.
    coll.create_index([("counts.$**", 1)])

    print("XONG. detseg_metadata:", coll.count_documents({}))


if __name__ == "__main__":
    main()

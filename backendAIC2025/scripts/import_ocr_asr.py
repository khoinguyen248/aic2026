"""Import OCR + ASR JSON vào MongoDB (collection ocr_metadata / asr_metadata) + tạo Atlas Search index.

Chạy TỪ HOST (Mongo chạy trong Docker ở localhost:27017). Cần MONGO_SEARCH_URI trỏ tới Mongo.

Ví dụ (PowerShell):
    $env:MONGO_SEARCH_URI="mongodb://aicadmin:PASSWORD@localhost:27017/?authSource=admin&directConnection=true"
    $env:MONGO_SEARCH_DB="aic2026"
    python backendAIC2025/scripts/import_ocr_asr.py "C:\\Users\\...\\aic2026-main\\ocr" "C:\\Users\\...\\aic2026-main\\asr"

- OCR/*.json  -> ocr_metadata  (mỗi file là list keyframe doc: idx, video_id, frame_id, ocr_text, path, ...)
- ASR/*.json  -> asr_metadata  (mỗi file là list segment: video_id, t_start, t_end, frame_start, frame_end, text)
- Idempotent: xoá sạch collection rồi nạp lại (chạy lại an toàn khi tải thêm data).
"""
import json
import os
import sys

from pymongo import MongoClient

BATCH = 5000


def load_dir(directory):
    for fname in sorted(os.listdir(directory)):
        if not fname.endswith(".json"):
            continue
        with open(os.path.join(directory, fname), encoding="utf-8") as f:
            data = json.load(f)
        for doc in (data if isinstance(data, list) else [data]):
            yield doc


def import_collection(coll, directory, label):
    coll.delete_many({})
    buf, total = [], 0
    for doc in load_dir(directory):
        buf.append(doc)
        if len(buf) >= BATCH:
            coll.insert_many(buf, ordered=False)
            total += len(buf)
            buf = []
    if buf:
        coll.insert_many(buf, ordered=False)
        total += len(buf)
    print(f"[{label}] imported {total} docs into {coll.name}")
    return total


def ensure_search_index(coll, field, index_name):
    """Atlas Search index (mongodb-atlas-local). Không tạo được -> code tự fallback regex."""
    try:
        existing = {i["name"] for i in coll.list_search_indexes()}
        if index_name in existing:
            print(f"[search-index] {index_name} đã tồn tại")
            return
        coll.create_search_index(
            {
                "name": index_name,
                "definition": {
                    "mappings": {"dynamic": False, "fields": {field: {"type": "string"}}}
                },
            }
        )
        print(f"[search-index] tạo {index_name} trên {coll.name}.{field} (chờ vài giây để build)")
    except Exception as exc:
        print(f"[search-index] KHÔNG tạo được {index_name}: {exc}")
        print("            -> ASR/OCR sẽ tự fallback regex, vẫn chạy (chậm hơn).")


def main():
    ocr_dir = sys.argv[1] if len(sys.argv) > 1 else "ocr"
    asr_dir = sys.argv[2] if len(sys.argv) > 2 else "asr"

    uri = os.getenv("MONGO_SEARCH_URI")
    if not uri:
        sys.exit("Thiếu MONGO_SEARCH_URI (env).")
    dbname = os.getenv("MONGO_SEARCH_DB", "aic2026")

    client = MongoClient(uri, serverSelectionTimeoutMS=8000)
    client.admin.command("ping")
    db = client[dbname]
    print(f"Kết nối OK -> DB '{dbname}'")

    import_collection(db["ocr_metadata"], ocr_dir, "OCR")
    db["ocr_metadata"].create_index("video_id")
    db["ocr_metadata"].create_index("frame_id")
    db["ocr_metadata"].create_index("idx")

    import_collection(db["asr_metadata"], asr_dir, "ASR")
    db["asr_metadata"].create_index("video_id")

    ensure_search_index(db["ocr_metadata"], "ocr_text", "ocr_search")
    ensure_search_index(db["ocr_metadata"], "caption", "caption_search")
    ensure_search_index(db["asr_metadata"], "text", "asr_search")

    print("XONG. Kiểm tra:")
    print("  ocr_metadata:", db["ocr_metadata"].count_documents({}))
    print("  asr_metadata:", db["asr_metadata"].count_documents({}))


if __name__ == "__main__":
    main()

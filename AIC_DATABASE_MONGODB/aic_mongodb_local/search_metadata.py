import argparse
from pprint import pprint

from src.mongo_connection import ocr_collection, asr_collection


def search_ocr(query: str, limit: int = 1000, max_edits: int = 1, prefix_length: int = 1):
    pipeline = [
        {
            "$search": {
                "index": "ocr_search",
                "text": {
                    "query": query,
                    "path": "ocr_text",
                    "fuzzy": {
                        "maxEdits": max_edits,
                        "prefixLength": prefix_length,
                    },
                },
            }
        },
        {"$limit": limit},
        {
            "$project": {
                "_id": 0,
                "idx": 1,
                "video_id": 1,
                "frame_id": 1,
                "keyframe_order": 1,
                "frame_stamp": 1,
                "ocr_text": 1,
                "path": 1,
                "video_path": 1,
                "video_url": 1,
                "score": {"$meta": "searchScore"},
            }
        },
    ]
    return list(ocr_collection.aggregate(pipeline))


def search_asr(query: str, limit: int = 1000, max_edits: int = 1, prefix_length: int = 1):
    pipeline = [
        {
            "$search": {
                "index": "asr_search",
                "text": {
                    "query": query,
                    "path": "text",
                    "fuzzy": {
                        "maxEdits": max_edits,
                        "prefixLength": prefix_length,
                    },
                },
            }
        },
        {"$limit": limit},
        {
            "$project": {
                "_id": 0,
                "id": 1,
                "video_id": 1,
                "t_start": 1,
                "t_end": 1,
                "frame_start": 1,
                "frame_end": 1,
                "frame_mid": 1,
                "text": 1,
                "score": {"$meta": "searchScore"},
            }
        },
    ]
    return list(asr_collection.aggregate(pipeline))


def main():
    parser = argparse.ArgumentParser(description="Fuzzy search OCR / ASR metadata using MongoDB Search.")
    parser.add_argument("query", nargs="?", help="Text query. If omitted, you will be prompted.")
    parser.add_argument("--mode", choices=["ocr", "asr", "both"], default="both")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--max-edits", type=int, choices=[1, 2], default=1)
    parser.add_argument("--prefix-length", type=int, default=1)
    args = parser.parse_args()

    query = args.query or input("Query: ").strip()
    if not query:
        raise SystemExit("Query cannot be empty.")

    if args.mode in ("ocr", "both"):
        print("\n===== OCR =====")
        hits = search_ocr(query, args.limit, args.max_edits, args.prefix_length)
        if not hits:
            print("No OCR hits.")
        for i, hit in enumerate(hits, 1):
            print(f"\n#{i}")
            pprint(hit, sort_dicts=False)

    if args.mode in ("asr", "both"):
        print("\n===== ASR =====")
        hits = search_asr(query, args.limit, args.max_edits, args.prefix_length)
        if not hits:
            print("No ASR hits.")
        for i, hit in enumerate(hits, 1):
            print(f"\n#{i}")
            pprint(hit, sort_dicts=False)


if __name__ == "__main__":
    main()

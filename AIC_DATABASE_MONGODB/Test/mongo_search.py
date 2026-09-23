from pymongo import MongoClient


# ============================================================
# MongoDB Connection
# ============================================================

MONGO_URI = (
    "mongodb://aicadmin:aic2026_local_password"
    "@localhost:27017/"
    "?authSource=admin&directConnection=true"
)

client = MongoClient(
    MONGO_URI,
    serverSelectionTimeoutMS=5000,
)

db = client["aic2026"]

ocr_collection = db["ocr_metadata"]
asr_collection = db["asr_metadata"]


# ============================================================
# OCR Search
# ============================================================

def search_ocr(
    query: str,
    limit: int = 10,
    max_edits: int = 1,
    prefix_length: int = 1,
):
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
        {
            "$limit": limit
        },
        {
            "$project": {
                "_id": 1,
                "idx": 1,
                "video_id": 1,
                "frame_id": 1,
                "keyframe_order": 1,
                "frame_stamp": 1,
                "ocr_text": 1,
                "path": 1,
                "video_path": 1,
                "video_url": 1,
                "score": {
                    "$meta": "searchScore"
                },
            }
        },
    ]

    return list(
        ocr_collection.aggregate(pipeline)
    )


# ============================================================
# ASR Search + Map ASR segment -> OCR keyframes
# ============================================================

def search_asr(
    query: str,
    limit: int = 10,
    max_edits: int = 1,
    prefix_length: int = 1,
):
    # 1. Search ASR để lấy các khoảng frame phù hợp
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
        {
            "$limit": limit
        },
        {
            "$project": {
                "_id": 0,
                "video_id": 1,
                "frame_start": 1,
                "frame_end": 1,
            }
        },
    ]

    asr_results = list(
        asr_collection.aggregate(pipeline)
    )

    # 2. Map từng ASR segment sang các keyframe trong OCR metadata
    frame_results = []
    seen_ids = set()

    for asr_hit in asr_results:
        video_id = asr_hit["video_id"]
        frame_start = asr_hit["frame_start"]
        frame_end = asr_hit["frame_end"]

        cursor = (
            ocr_collection.find(
                {
                    "video_id": video_id,
                    "frame_id": {
                        "$gte": frame_start,
                        "$lte": frame_end,
                    },
                }
            )
            .sort("frame_id", 1)
        )

        for frame in cursor:
            doc_id = frame["_id"]

            if doc_id in seen_ids:
                continue

            seen_ids.add(doc_id)
            frame_results.append(frame)

    # QUAN TRỌNG:
    # trả trực tiếp OCR documents
    return frame_results

import os
from functools import lru_cache
from typing import Optional

from pymongo import MongoClient


@lru_cache(maxsize=1)
def get_database():
    uri = os.getenv("MONGO_SEARCH_URI")
    database_name = os.getenv("MONGO_SEARCH_DB", "aic2026")

    if not uri:
        raise RuntimeError("MONGO_SEARCH_URI chưa được cấu hình")

    client = MongoClient(
        uri,
        serverSelectionTimeoutMS=5000,
    )

    client.admin.command("ping")
    return client[database_name]


def search_ocr(
    query: str,
    limit: int = 20,
    max_edits: Optional[int] = 1,
    prefix_length: int = 1,
):
    collection = get_database()["ocr_metadata"]

    text_operator = {
        "query": query,
        "path": "ocr_text",
    }
    if max_edits is not None:
        text_operator["fuzzy"] = {
            "maxEdits": max_edits,
            "prefixLength": prefix_length,
        }

    pipeline = [
        {
            "$search": {
                "index": "ocr_search",
                "text": text_operator,
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

    return list(collection.aggregate(pipeline))


def search_asr(
    query: str,
    limit: int = 20,
    max_edits: Optional[int] = 1,
    prefix_length: int = 1,
):
    database = get_database()
    asr_collection = database["asr_metadata"]
    ocr_collection = database["ocr_metadata"]

    text_operator = {
        "query": query,
        "path": "text",
    }
    if max_edits is not None:
        text_operator["fuzzy"] = {
            "maxEdits": max_edits,
            "prefixLength": prefix_length,
        }

    pipeline = [
        {
            "$search": {
                "index": "asr_search",
                "text": text_operator,
            }
        },
        {"$limit": limit},
        {
            "$project": {
                "_id": 0,
                "video_id": 1,
                "frame_start": 1,
                "frame_end": 1,
            }
        },
    ]

    asr_results = list(asr_collection.aggregate(pipeline))

    # ASR describes a time range rather than one displayable keyframe. Map each
    # matched range to the OCR keyframes belonging to the same video and range.
    frame_results = []
    seen_ids = set()

    for asr_hit in asr_results:
        video_id = asr_hit.get("video_id")
        frame_start = asr_hit.get("frame_start")
        frame_end = asr_hit.get("frame_end")
        if video_id is None or frame_start is None or frame_end is None:
            continue

        cursor = ocr_collection.find(
            {
                "video_id": video_id,
                "frame_id": {
                    "$gte": frame_start,
                    "$lte": frame_end,
                },
            },
            {
                "idx": 1,
                "video_id": 1,
                "frame_id": 1,
                "keyframe_order": 1,
                "frame_stamp": 1,
                "ocr_text": 1,
                "path": 1,
                "video_path": 1,
                "video_url": 1,
            },
        ).sort("frame_id", 1)

        for frame in cursor:
            document_id = frame.pop("_id", None)
            dedupe_key = document_id or (frame.get("video_id"), frame.get("frame_id"))
            if dedupe_key in seen_ids:
                continue

            seen_ids.add(dedupe_key)
            frame_results.append(frame)

    return frame_results


# ---------------------------------------------------------------------------
# Video-scoped helpers cho TRAKE: lấy frame/khoảng khớp OCR/ASR TRONG 1 video.
# Dùng để boost theo từng event (map event -> OCR/ASR -> frame của event đó).
# ---------------------------------------------------------------------------

# $search chạy trước $match nên lấy top-K theo relevance rồi mới lọc video_id.
_SCOPED_PRELIMIT = 300


def ocr_frame_ids_in_video(
    query: str,
    video_id,
    limit: int = 50,
    max_edits: Optional[int] = 1,
    prefix_length: int = 1,
):
    """frame_id các keyframe khớp OCR text, giới hạn trong 1 video."""
    collection = get_database()["ocr_metadata"]

    text_operator = {"query": query, "path": "ocr_text"}
    if max_edits is not None:
        text_operator["fuzzy"] = {"maxEdits": max_edits, "prefixLength": prefix_length}

    pipeline = [
        {"$search": {"index": "ocr_search", "text": text_operator}},
        {"$limit": _SCOPED_PRELIMIT},
        {"$match": {"video_id": video_id}},
        {"$limit": limit},
        {"$project": {"_id": 0, "frame_id": 1, "path": 1}},
    ]
    # Trả (frame_id, path) — path để UI hiện ảnh keyframe khi frame OCR được inject làm ứng viên.
    return [
        (d["frame_id"], d.get("path"))
        for d in collection.aggregate(pipeline)
        if d.get("frame_id") is not None
    ]


def asr_ranges_in_video(
    query: str,
    video_id,
    limit: int = 50,
    max_edits: Optional[int] = 1,
    prefix_length: int = 1,
):
    """Các khoảng (frame_start, frame_end) khớp ASR text, giới hạn trong 1 video."""
    collection = get_database()["asr_metadata"]

    text_operator = {"query": query, "path": "text"}
    if max_edits is not None:
        text_operator["fuzzy"] = {"maxEdits": max_edits, "prefixLength": prefix_length}

    pipeline = [
        {"$search": {"index": "asr_search", "text": text_operator}},
        {"$limit": _SCOPED_PRELIMIT},
        {"$match": {"video_id": video_id}},
        {"$limit": limit},
        {"$project": {"_id": 0, "frame_start": 1, "frame_end": 1}},
    ]
    ranges = []
    for d in collection.aggregate(pipeline):
        s, e = d.get("frame_start"), d.get("frame_end")
        if s is not None and e is not None:
            ranges.append((int(s), int(e)))
    return ranges

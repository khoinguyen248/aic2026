import os
import re
from functools import lru_cache
from typing import Optional

from pymongo import MongoClient


_VIDEO_ID_RE = re.compile(r"^[A-Za-z]+(.+?)[_-]V(.+)$")


def _parse_video_id(video_id):
    """'L30_V068' -> ('30','068'); 'N078-V002' -> ('078','002'). Chấp nhận mọi chữ cái nhóm
    (K/L/M/N/S...) và cả 2 kiểu dấu phân cách '_'/'-' đang có trong dataset. Không khớp -> (None, None)."""
    m = _VIDEO_ID_RE.match(str(video_id))
    if m:
        return m.group(1), m.group(2)
    return None, None


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
                "L": 1,
                "V": 1,
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
                "t_start": 1,
                "t_end": 1,
                "frame_start": 1,
                "frame_end": 1,
                "text": 1,
                "score": {"$meta": "searchScore"},
            }
        },
    ]

    asr_results = list(asr_collection.aggregate(pipeline))

    # ASR mô tả 1 khoảng thời gian, không phải 1 keyframe cụ thể -> lấy keyframe
    # có sẵn gần nhất trong khoảng đó để hiển thị ảnh (thay vì decode từ video gốc,
    # vốn đòi hỏi file .mp4 mà máy chạy search có thể không có).
    results = []
    for asr_hit in asr_results:
        video_id = asr_hit.get("video_id")
        frame_start = asr_hit.get("frame_start")
        frame_end = asr_hit.get("frame_end")
        L, V = _parse_video_id(video_id)

        frame_doc = None
        if video_id is not None and frame_start is not None and frame_end is not None:
            frame_doc = ocr_collection.find_one(
                {
                    "video_id": video_id,
                    "frame_id": {"$gte": frame_start, "$lte": frame_end},
                },
                {"_id": 0, "frame_id": 1, "path": 1, "video_url": 1, "fps": 1},
                sort=[("frame_id", 1)],
            ) or {}

        results.append(
            {
                **asr_hit,
                "L": L,
                "V": V,
                "frame_id": frame_doc.get("frame_id", frame_start) if frame_doc else frame_start,
                "path": frame_doc.get("path") if frame_doc else None,
                "video_url": frame_doc.get("video_url") if frame_doc else None,
                "fps": frame_doc.get("fps") if frame_doc else None,
            }
        )

    return results


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

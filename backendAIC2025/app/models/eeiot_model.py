from ..extensions import mongo2

def get_frames_collection():
    return mongo2.db.frames


# ASR segments (§9 spec): 1 doc / đoạn lời nói {video_id, t_start, t_end, frame_start, frame_end, text}.
# ⚠️ RECONCILE: nếu teammate nạp ASR vào collection tên khác, đổi "asr_segments" cho khớp.
def get_asr_collection():
    return mongo2.db.asr_segments

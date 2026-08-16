from ..extensions import mongo2

def get_frames_collection():
    return mongo2.db.frames

from ..extensions import mongo

def get_teacher_positions_collection():
    return mongo.db.teacherpositions

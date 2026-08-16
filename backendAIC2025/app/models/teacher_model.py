from ..extensions import mongo

def get_teachers_collection():
    return mongo.db.teachers

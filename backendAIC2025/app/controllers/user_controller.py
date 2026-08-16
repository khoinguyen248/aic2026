# app/controllers/user_controller.py
from flask import request, jsonify
from bson import ObjectId
from datetime import datetime

from ..models.user_models import get_users_collection
from ..models.teacher_model import get_teachers_collection
from ..models.teacher_position_model import get_teacher_positions_collection
from ..utils.helpers import serialize_doc

from ..utils.helpers import generate_random_number_string


# Helper: convert ObjectId to str
def to_str_id(data):
    if not data:
        return None
    data["_id"] = str(data["_id"])
    return data


# ========== CONTROLLERS ==========
def convert_objectid(obj):
    if isinstance(obj, ObjectId):
        return str(obj)
    if isinstance(obj, list):
        return [convert_objectid(i) for i in obj]
    if isinstance(obj, dict):
        return {k: convert_objectid(v) for k, v in obj.items()}
    return obj

def get_jobs():
    teacher_positions_collection = get_teacher_positions_collection()
    all_jobs = list(teacher_positions_collection.find())
    return jsonify({"data": [serialize_doc(job) for job in all_jobs]}), 200
def get_teachers():
    try:
        teachers_collection = get_teachers_collection()   # <-- gọi hàm
        teachers = list(teachers_collection.find({}))     # <-- bây giờ mới find
        teachers = [convert_objectid(t) for t in teachers]
        return jsonify(teachers), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
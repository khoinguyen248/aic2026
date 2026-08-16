# app/routes/user_routes.py
from flask import Blueprint
from ..controllers import user_controller

user_bp = Blueprint("user", __name__)

# GET /user/teachers
user_bp.route("/teachers", methods=["GET"])(user_controller.get_teachers)

# GET /user/teacher-positions
user_bp.route("/teacher-positions", methods=["GET"])(user_controller.get_jobs)



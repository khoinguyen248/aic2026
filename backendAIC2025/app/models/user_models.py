# app/models/user_model.py
from ..extensions import mongo

def get_users_collection():
    return mongo.db.users

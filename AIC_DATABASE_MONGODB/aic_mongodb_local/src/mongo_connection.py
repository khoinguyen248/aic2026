import os
from urllib.parse import quote_plus

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

USER = os.getenv("MONGO_ROOT_USER", "aicadmin")
PASSWORD = os.getenv("MONGO_ROOT_PASSWORD", "aic2026_local_password")
HOST = os.getenv("MONGO_HOST", "localhost")
PORT = os.getenv("MONGO_PORT", "27017")
DB_NAME = os.getenv("MONGO_DB", "aic2026")
OCR_COLLECTION = os.getenv("MONGO_OCR_COLLECTION", "ocr_metadata")
ASR_COLLECTION = os.getenv("MONGO_ASR_COLLECTION", "asr_metadata")

MONGO_URI = (
    f"mongodb://{quote_plus(USER)}:{quote_plus(PASSWORD)}"
    f"@{HOST}:{PORT}/?authSource=admin&directConnection=true"
)

client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
db = client[DB_NAME]
ocr_collection = db[OCR_COLLECTION]
asr_collection = db[ASR_COLLECTION]

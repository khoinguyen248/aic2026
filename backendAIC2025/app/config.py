import os
from dotenv import load_dotenv

load_dotenv()


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)

    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "on"}


class Config:
    APP_ENV = os.getenv("APP_ENV", "development")
    DEBUG = env_bool("DEBUG", False)

    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", "5000"))

    SECRET_KEY = os.getenv("SECRET_KEY", "development-only-key")

    MONGO_ENABLED = env_bool("MONGO_ENABLED", False)
    MONGO_URI = os.getenv("MONGO_URI")
    MONGO_URI2 = os.getenv("MONGO_URI2")

    SEARCH_ENABLED = env_bool("SEARCH_ENABLED", False)
    USER_ROUTES_ENABLED = env_bool("USER_ROUTES_ENABLED", False)

    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    BEIT3_CHECKPOINT_PATH = os.getenv(
        "BEIT3_CHECKPOINT_PATH",
        "/models/beit3_large_patch16_224.pth",
    )

    EMBEDDING_ROOT = os.getenv("EMBEDDING_ROOT", "/data/embeddings")
    METADATA_ROOT = os.getenv("METADATA_ROOT", "/data/metadata")
    KEYFRAMES_PATH = os.getenv("KEYFRAMES_PATH", "/data/keyframes")

    QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")

    # TRAKE tầng 3 (tinh chỉnh trên frame gốc) cần đọc video thật.
    # Máy có USB/ổ chứa video: TRAKE_TIER3_ENABLED=true + VIDEO_ROOT trỏ tới thư mục video.
    # Máy không có: để mặc định (false) -> tự động chạy case 2 (2 tầng, không tinh chỉnh).
    TRAKE_TIER3_ENABLED = env_bool("TRAKE_TIER3_ENABLED", False)
    VIDEO_ROOT = os.getenv("VIDEO_ROOT", "")

    TRAKE_TOP_M = int(os.getenv("TRAKE_TOP_M", "150"))
    TRAKE_TOP_VIDEOS = int(os.getenv("TRAKE_TOP_VIDEOS", "2"))
    TRAKE_MAX_COMBOS = int(os.getenv("TRAKE_MAX_COMBOS", "100"))
    TRAKE_TIER3_RADIUS = int(os.getenv("TRAKE_TIER3_RADIUS", "15"))
    TRAKE_TIER3_STRIDE = int(os.getenv("TRAKE_TIER3_STRIDE", "1"))
    TRAKE_VIDEO_CONFIDENCE_THRESHOLD = float(
        os.getenv("TRAKE_VIDEO_CONFIDENCE_THRESHOLD", "0.8")
    )
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
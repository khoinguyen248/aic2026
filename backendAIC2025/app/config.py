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

    MONGO_SEARCH_ENABLED = env_bool("MONGO_SEARCH_ENABLED", False)
    MONGO_SEARCH_URI = os.getenv("MONGO_SEARCH_URI")
    MONGO_SEARCH_DB = os.getenv("MONGO_SEARCH_DB", "aic2026")

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

    # Rerank tầng 3 khi 2+ frame liền kề gần như tie (CLIP không phân biệt được).
    # Mặc định dùng thuật toán (peak/prominence trên đường cong điểm số) - miễn phí, luôn chạy.
    # Bật thêm Qwen2.5-VL để phân xử khi thuật toán cũng không chắc -> chỉ gọi khi thật sự cần,
    # có fallback an toàn về thuật toán nếu load/inference lỗi.
    TRAKE_RERANK_TIE_MARGIN = float(os.getenv("TRAKE_RERANK_TIE_MARGIN", "0.03"))

    # Qwen2.5-VL chạy LOCAL: load qua transformers, giữ ấm trên GPU (spec mục 13) - KHÔNG dùng API.
    # Model 7B/72B rất nặng -> quantize (4bit/8bit qua bitsandbytes) để giảm VRAM/RAM.
    # QWEN_MODEL_PATH: HF id hoặc thư mục local; có thể trỏ thẳng bản đã prequant AWQ/GPTQ rồi để
    # QWEN_QUANTIZATION=none.
    TRAKE_QWEN_RERANK_ENABLED = env_bool("TRAKE_QWEN_RERANK_ENABLED", False)
    QWEN_MODEL_PATH = os.getenv("QWEN_MODEL_PATH", "Qwen/Qwen2.5-VL-7B-Instruct")
    QWEN_QUANTIZATION = os.getenv("QWEN_QUANTIZATION", "4bit")  # 4bit | 8bit | none
    QWEN_DEVICE_MAP = os.getenv("QWEN_DEVICE_MAP", "auto")      # auto | cuda | cpu
    QWEN_MAX_NEW_TOKENS = int(os.getenv("QWEN_MAX_NEW_TOKENS", "10"))
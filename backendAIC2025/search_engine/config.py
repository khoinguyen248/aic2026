from dataclasses import dataclass, field
import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class ModelConfig:
    name: str
    collection: str
    vector_size: int
    embedding_dir: Path


@dataclass(frozen=True)
class SearchConfig:
    base_dir: Path = BASE_DIR
    embedding_root: Path = Path(
        os.getenv("EMBEDDING_ROOT", str(BASE_DIR / "embedding-26"))
    )
    metadata_root: Path = Path(
        os.getenv("METADATA_ROOT", str(BASE_DIR / "metadata"))
    )
    qdrant_host: str = os.getenv("QDRANT_HOST", "localhost")
    qdrant_port: int = int(os.getenv("QDRANT_PORT", "6333"))
    qdrant_url: str | None = os.getenv("QDRANT_URL")
    qdrant_api_key: str | None = os.getenv("QDRANT_API_KEY")
    device: str = os.getenv("SEARCH_DEVICE", "cpu")
    model_cache_size: int = max(1, int(os.getenv("SEARCH_MODEL_CACHE_SIZE", "1")))
    batch_size: int = int(os.getenv("QDRANT_BATCH_SIZE", "512"))
    recreate_collections: bool = os.getenv("QDRANT_RECREATE", "0") == "1"
    beit3_checkpoint: Path = Path(
        os.getenv(
            "BEIT3_CHECKPOINT_PATH",
            str(BASE_DIR / "beit3" / "checkpoints" / "beit3_large_patch16_224.pth"),
        )
    )
    beit3_spm: Path = Path(
        os.getenv("BEIT3_SPM_PATH", str(BASE_DIR / "beit3" / "beit3.spm"))
    )
    jina_model_name: str = os.getenv("JINA_MODEL_NAME", "jinaai/jina-embeddings-v5-omni-small")
    pe_model_name: str = os.getenv("PE_MODEL_NAME", "hf-hub:timm/PE-Core-bigG-14-448")
    models: dict[str, ModelConfig] = field(default_factory=dict)

    def __post_init__(self):
        if self.models:
            return
        object.__setattr__(
            self,
            "models",
            {
                "beit3": ModelConfig(
                    name="beit3",
                    collection=os.getenv("QDRANT_COLLECTION_BEIT3", "beit3"),
                    vector_size=1024,
                    embedding_dir=self.embedding_root / "beit3",
                ),
                "jina": ModelConfig(
                    name="jina",
                    collection=os.getenv("QDRANT_COLLECTION_JINA", "jina"),
                    vector_size=1024,
                    embedding_dir=self.embedding_root / "jina",
                ),
                "pe": ModelConfig(
                    name="pe",
                    collection=os.getenv("QDRANT_COLLECTION_PE", "pe"),
                    vector_size=1280,
                    embedding_dir=self.embedding_root / "pe",
                ),
            },
        )


DEFAULT_CONFIG = SearchConfig()

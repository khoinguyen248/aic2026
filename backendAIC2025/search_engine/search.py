from __future__ import annotations

import argparse
from pathlib import Path
import time
from typing import Any

import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.http.models import Distance, PointStruct, VectorParams

try:
    from .config import DEFAULT_CONFIG, SearchConfig
    from .model import ModelRegistry
    from .utils import (
        format_qdrant_hits,
        iter_embedding_metadata_pairs,
        l2_normalize,
        normalize_model_name,
    )
except ImportError:  # Allow `python search.py ...` from this directory.
    from config import DEFAULT_CONFIG, SearchConfig
    from model import ModelRegistry
    from utils import format_qdrant_hits, iter_embedding_metadata_pairs, l2_normalize, normalize_model_name


class SearchEngine:
    def __init__(self, config: SearchConfig = DEFAULT_CONFIG, registry: ModelRegistry | None = None):
        self.config = config
        self.registry = registry or ModelRegistry(config)
        self.client = self._create_client()

    def _create_client(self) -> QdrantClient:
        if self.config.qdrant_url:
            return QdrantClient(
                url=self.config.qdrant_url,
                api_key=self.config.qdrant_api_key,
                timeout=120,
            )
        return QdrantClient(
            host=self.config.qdrant_host,
            port=self.config.qdrant_port,
            api_key=self.config.qdrant_api_key,
            timeout=120,
        )

    def collection_name(self, model: str) -> str:
        name = normalize_model_name(model)
        return self.config.models[name].collection

    def _delete_collection_and_wait(
        self,
        collection_name: str,
        timeout_seconds: float = 120.0,
    ) -> None:
        """Delete a collection and wait until Qdrant no longer exposes it.

        Qdrant may finish the HTTP delete request slightly before the collection
        directory is fully released, especially when its storage is mounted from
        Docker Desktop on Windows. Waiting here prevents an immediate recreate
        request from racing with that cleanup.
        """
        self.client.delete_collection(collection_name=collection_name)

        deadline = time.monotonic() + timeout_seconds
        while self.client.collection_exists(collection_name):
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"Timed out waiting for collection {collection_name!r} to be deleted"
                )
            time.sleep(0.5)

        # collection_exists() can turn false just before the storage directory is
        # released. Give the server a short grace period before recreating it.
        time.sleep(1.0)

    def _create_collection_with_retry(
        self,
        collection_name: str,
        vector_size: int,
        attempts: int = 20,
    ) -> None:
        """Create a collection, retrying the transient stale-directory race."""
        for attempt in range(1, attempts + 1):
            try:
                self.client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(
                        size=vector_size,
                        distance=Distance.COSINE,
                    ),
                )
                return
            except UnexpectedResponse as exc:
                message = str(exc)
                stale_directory = (
                    "500" in message
                    and "File exists" in message
                    and f"collections/{collection_name}" in message.replace("\\", "/")
                )
                if not stale_directory:
                    raise

                if attempt == attempts:
                    raise RuntimeError(
                        f"Qdrant reports an orphaned storage directory for "
                        f"collection {collection_name!r}. The collection is absent "
                        "from the API, but its directory still exists in the Docker "
                        "storage volume. Stop Qdrant and move/remove only that stale "
                        "directory, then start Qdrant again."
                    ) from exc

                time.sleep(min(0.5 * attempt, 3.0))

    def build_collection(self, model: str, recreate: bool | None = None) -> dict[str, Any]:
        name = normalize_model_name(model)
        model_config = self.config.models[name]
        recreate = self.config.recreate_collections if recreate is None else recreate

        if not model_config.embedding_dir.exists():
            raise FileNotFoundError(f"Embedding directory not found: {model_config.embedding_dir}")
        if not self.config.metadata_root.exists():
            raise FileNotFoundError(f"Metadata directory not found: {self.config.metadata_root}")

        exists = self.client.collection_exists(model_config.collection)
        if exists and recreate:
            print(f"[INFO] Deleting collection {model_config.collection!r}...")
            self._delete_collection_and_wait(model_config.collection)
            exists = False
        if not exists:
            print(f"[INFO] Creating collection {model_config.collection!r}...")
            self._create_collection_with_retry(
                collection_name=model_config.collection,
                vector_size=model_config.vector_size,
            )

        total_points = 0
        started = time.time()
        for group_name, npy_path, metadata in iter_embedding_metadata_pairs(
            model_config.embedding_dir,
            self.config.metadata_root,
        ):
            vectors = np.load(npy_path, mmap_mode="r")
            if vectors.ndim != 2 or vectors.shape[1] != model_config.vector_size:
                raise ValueError(
                    f"Invalid shape for {npy_path}: {vectors.shape}, expected (*, {model_config.vector_size})"
                )
            if len(vectors) != len(metadata):
                raise ValueError(f"Count mismatch for {group_name}: {len(vectors)} vectors vs {len(metadata)} metadata")

            for start in range(0, len(vectors), self.config.batch_size):
                end = min(start + self.config.batch_size, len(vectors))
                batch_vecs = l2_normalize(np.asarray(vectors[start:end], dtype=np.float32))
                batch_meta = metadata[start:end]
                points = [
                    PointStruct(
                        id=int(payload.get("idx", total_points + start + i)),
                        vector=batch_vecs[i].tolist(),
                        payload=payload,
                    )
                    for i, payload in enumerate(batch_meta)
                ]
                self.client.upsert(collection_name=model_config.collection, points=points, wait=True)

            total_points += len(vectors)
            print(f"[OK] {model_config.collection}/{group_name}: {len(vectors)} points")

        return {
            "collection": model_config.collection,
            "model": name,
            "vector_size": model_config.vector_size,
            "points": total_points,
            "seconds": round(time.time() - started, 2),
        }

    def build_all_collections(self, recreate: bool | None = None) -> dict[str, dict[str, Any]]:
        return {name: self.build_collection(name, recreate=recreate) for name in self.config.models}

    def _query_vector(
        self,
        vector: np.ndarray,
        model: str,
        top_k: int,
        query_filter: Any = None,
        score_threshold: float | None = None,
    ) -> list[dict[str, Any]]:
        name = normalize_model_name(model)
        collection = self.config.models[name].collection
        query = l2_normalize(vector).astype(np.float32).tolist()
        try:
            response = self.client.query_points(
                collection_name=collection,
                query=query,
                limit=top_k,
                with_payload=True,
                with_vectors=False,
                query_filter=query_filter,
                score_threshold=score_threshold,
            )
        except TypeError:
            response = self.client.query_points(
                collection_name=collection,
                query_vector=query,
                limit=top_k,
                with_payload=True,
                with_vectors=False,
                query_filter=query_filter,
                score_threshold=score_threshold,
            )
        return format_qdrant_hits(response)

    def text_search(
        self,
        text: str,
        model: str = "beit3",
        top_k: int = 100,
        query_filter: Any = None,
        score_threshold: float | None = None,
    ) -> list[dict[str, Any]]:
        if not text or not text.strip():
            raise ValueError("text query must not be empty")
        vector = self.registry.encode_text(text, model)
        return self._query_vector(vector, model, top_k, query_filter, score_threshold)

    def image_search(
        self,
        image: str | Path,
        model: str = "beit3",
        top_k: int = 100,
        query_filter: Any = None,
        score_threshold: float | None = None,
    ) -> list[dict[str, Any]]:
        vector = self.registry.encode_image(image, model)
        return self._query_vector(vector, model, top_k, query_filter, score_threshold)


_DEFAULT_ENGINE: SearchEngine | None = None


def get_engine() -> SearchEngine:
    global _DEFAULT_ENGINE
    if _DEFAULT_ENGINE is None:
        _DEFAULT_ENGINE = SearchEngine()
    return _DEFAULT_ENGINE


def text_search(text: str, model: str = "beit3", top_k: int = 100) -> list[dict[str, Any]]:
    return get_engine().text_search(text=text, model=model, top_k=top_k)


def image_search(img: str | Path, model: str = "beit3", top_k: int = 100) -> list[dict[str, Any]]:
    return get_engine().image_search(image=img, model=model, top_k=top_k)


def img_search(img: str | Path, model: str = "beit3", top_k: int = 100) -> list[dict[str, Any]]:
    return image_search(img=img, model=model, top_k=top_k)


def main() -> None:
    parser = argparse.ArgumentParser(description="AIC 2026 Qdrant search engine")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build", help="Build Qdrant collection(s) from embedding-26")
    build_parser.add_argument("--model", choices=["beit3", "jina", "pe", "all"], default="all")
    build_parser.add_argument("--recreate", action="store_true")

    text_parser = subparsers.add_parser("text", help="Run text search")
    text_parser.add_argument("query")
    text_parser.add_argument("--model", choices=["beit3", "jina", "pe"], default="beit3")
    text_parser.add_argument("--top-k", type=int, default=10)

    image_parser = subparsers.add_parser("image", help="Run image search")
    image_parser.add_argument("image")
    image_parser.add_argument("--model", choices=["beit3", "jina", "pe"], default="beit3")
    image_parser.add_argument("--top-k", type=int, default=10)

    args = parser.parse_args()
    engine = SearchEngine()

    if args.command == "build":
        result = engine.build_all_collections(recreate=args.recreate) if args.model == "all" else engine.build_collection(
            args.model,
            recreate=args.recreate,
        )
        print(result)
    elif args.command == "text":
        for item in engine.text_search(args.query, model=args.model, top_k=args.top_k):
            print(item)
    elif args.command == "image":
        for item in engine.image_search(args.image, model=args.model, top_k=args.top_k):
            print(item)


if __name__ == "__main__":
    main()
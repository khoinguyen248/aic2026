from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from PIL import Image


PAYLOAD_KEYS = (
    "idx",
    "video_id",
    "L",
    "V",
    "keyframe_order",
    "frame_id",
    "fps",
    "frame_stamp",
    "path",
    "video_path",
    "video_url",
)


def normalize_model_name(model: str) -> str:
    name = (model or "").strip().lower()
    if name not in {"beit3", "jina", "pe"}:
        raise ValueError(f"Unsupported model '{model}'. Expected one of: beit3, jina, pe")
    return name


def l2_normalize(vector: np.ndarray) -> np.ndarray:
    arr = np.asarray(vector, dtype=np.float32)
    if arr.ndim == 1:
        norm = np.linalg.norm(arr)
        return arr if norm == 0 else arr / norm
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms[norms == 0] = 1
    return arr / norms


def load_image(image: str | Path | Image.Image) -> Image.Image:
    if isinstance(image, Image.Image):
        return image.convert("RGB")
    return Image.open(image).convert("RGB")


def compact_payload(item: dict[str, Any]) -> dict[str, Any]:
    return {key: item[key] for key in PAYLOAD_KEYS if key in item}


def load_metadata_file(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"Metadata file must contain a list: {path}")
    return [compact_payload(item) for item in data]


def metadata_files_for_l(metadata_root: Path, l_name: str) -> list[Path]:
    return sorted(metadata_root.glob(f"{l_name}_V*.json"))


def metadata_for_l(metadata_root: Path, l_name: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in metadata_files_for_l(metadata_root, l_name):
        items.extend(load_metadata_file(path))
    if not items:
        raise FileNotFoundError(f"No metadata files found for {l_name} in {metadata_root}")
    return items


def iter_embedding_metadata_pairs(
    embedding_dir: Path,
    metadata_root: Path,
) -> Iterable[tuple[str, Path, list[dict[str, Any]]]]:
    """Yield (group_name, npy_path, metadata) with vector order matching metadata order."""
    direct_npy = sorted(p for p in embedding_dir.glob("L*.npy") if p.is_file())
    if direct_npy:
        for npy_path in direct_npy:
            l_name = npy_path.stem
            yield l_name, npy_path, metadata_for_l(metadata_root, l_name)
        return

    for l_dir in sorted(p for p in embedding_dir.glob("L*") if p.is_dir()):
        for npy_path in sorted(l_dir.glob("*.npy")):
            meta_path = metadata_root / f"{npy_path.stem}.json"
            if not meta_path.exists():
                raise FileNotFoundError(f"Metadata file not found for {npy_path}: {meta_path}")
            yield npy_path.stem, npy_path, load_metadata_file(meta_path)


def format_qdrant_hits(response: Any) -> list[dict[str, Any]]:
    points = getattr(response, "points", response)
    results = []
    for point in points:
        payload = dict(getattr(point, "payload", None) or {})
        score = float(getattr(point, "score", 0.0))
        idx = payload.get("idx", getattr(point, "id", None))
        results.append({"idx": idx, "score": score, "metadata": payload, **payload})
    return results

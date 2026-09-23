#!/usr/bin/env python3
"""Create minimal keyframe metadata JSON files for L25."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


VIDEO_DIR_PATTERN = re.compile(r"^L(?P<L>\d+)_V(?P<V>\d+)$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create metadata_L25 JSON files from keyframe images in runtime-data/L25."
        )
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("runtime-data/L25"),
        help="Directory containing L25_Vxxx keyframe folders.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("runtime-data/metadata_L25"),
        help="Directory to write generated JSON metadata files.",
    )
    parser.add_argument(
        "--reference-dir",
        type=Path,
        default=Path("runtime-data/metadata/ocr"),
        help="Existing OCR metadata directory used for idx/fps/video_url hints.",
    )
    parser.add_argument(
        "--path-prefix",
        default="Keyframes",
        help=(
            "Prefix used in the output path field. "
            "Default produces paths like L25/L25_V001/000000.webp."
        ),
    )
    parser.add_argument(
        "--fps",
        type=float,
        default=25.0,
        help="Fallback FPS when reference metadata is unavailable.",
    )
    parser.add_argument(
        "--start-idx",
        type=int,
        default=None,
        help=(
            "Fallback idx start for frames not found in reference metadata. "
            "Defaults to max reference idx + 1, or 0 if no reference exists."
        ),
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing output JSON files.",
    )
    return parser.parse_args()


def load_reference(reference_file: Path) -> dict[int, dict[str, Any]]:
    if not reference_file.exists():
        return {}

    data = json.loads(reference_file.read_text(encoding="utf-8"))
    return {
        int(item["frame_id"]): item
        for item in data
        if isinstance(item, dict) and "frame_id" in item
    }


def max_reference_idx(reference_dir: Path) -> int | None:
    if not reference_dir.exists():
        return None

    max_idx: int | None = None
    for file_path in reference_dir.glob("*.json"):
        data = json.loads(file_path.read_text(encoding="utf-8"))
        for item in data:
            if not isinstance(item, dict) or "idx" not in item:
                continue
            idx = int(item["idx"])
            max_idx = idx if max_idx is None else max(max_idx, idx)
    return max_idx


def keyframe_files(video_dir: Path) -> list[Path]:
    return sorted(
        [
            file_path
            for file_path in video_dir.iterdir()
            if file_path.is_file()
            and file_path.suffix.lower() in {".webp", ".jpg", ".jpeg", ".png"}
        ],
        key=lambda file_path: (int(file_path.stem), file_path.name)
        if file_path.stem.isdigit()
        else (10**18, file_path.name),
    )


def build_metadata(
    video_dir: Path,
    reference_dir: Path,
    path_prefix: str,
    fallback_fps: float,
    next_idx: int,
) -> tuple[list[dict[str, Any]], int]:
    match = VIDEO_DIR_PATTERN.match(video_dir.name)
    if not match:
        return [], next_idx

    L = match.group("L")
    V = match.group("V")
    video_id = video_dir.name
    reference = load_reference(reference_dir / f"{video_id}.json")

    metadata: list[dict[str, Any]] = []
    for keyframe_order, image_path in enumerate(keyframe_files(video_dir)):
        if not image_path.stem.isdigit():
            continue

        frame_id = int(image_path.stem)
        ref_item = reference.get(frame_id, {})

        if "idx" in ref_item:
            idx = int(ref_item["idx"])
        else:
            idx = next_idx
            next_idx += 1

        fps = float(ref_item.get("fps", fallback_fps))
        frame_stamp = round(frame_id / fps, 3) if fps else 0.0

        metadata.append(
            {
                "idx": idx,
                "video_id": video_id,
                "L": L,
                "V": V,
                "keyframe_order": keyframe_order,
                "frame_id": frame_id,
                "fps": fps,
                "frame_stamp": frame_stamp,
                "path": f"{path_prefix}/{video_id}/{image_path.name}",
                "video_url": ref_item.get("video_url", ""),
                "ocr_text": "",
                "caption": "",
            }
        )

    return metadata, next_idx


def main() -> None:
    args = parse_args()
    input_dir = args.input_dir
    output_dir = args.output_dir

    if not input_dir.exists():
        raise SystemExit(f"Input directory does not exist: {input_dir}")

    max_idx = max_reference_idx(args.reference_dir)
    next_idx = args.start_idx
    if next_idx is None:
        next_idx = 0 if max_idx is None else max_idx + 1

    output_dir.mkdir(parents=True, exist_ok=True)

    written = 0
    skipped = 0
    for video_dir in sorted(input_dir.iterdir(), key=lambda path: path.name):
        if not video_dir.is_dir():
            continue

        metadata, next_idx = build_metadata(
            video_dir=video_dir,
            reference_dir=args.reference_dir,
            path_prefix=args.path_prefix.strip("/\\"),
            fallback_fps=args.fps,
            next_idx=next_idx,
        )
        if not metadata:
            continue

        output_file = output_dir / f"{video_dir.name}.json"
        if output_file.exists() and not args.overwrite:
            skipped += 1
            continue

        output_file.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        written += 1

    print(f"Written: {written} file(s)")
    print(f"Skipped: {skipped} existing file(s)")
    print(f"Output: {output_dir}")


if __name__ == "__main__":
    main()

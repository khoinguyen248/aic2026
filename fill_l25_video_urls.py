#!/usr/bin/env python3
"""Fill missing video_url values in L25 OCR metadata files."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Fill empty video_url fields in runtime-data/metadata/ocr/L25_V*.json "
            "using the non-empty URL already present in the same video file."
        )
    )
    parser.add_argument(
        "--metadata-dir",
        type=Path,
        default=Path("runtime-data/metadata/ocr"),
        help="Directory containing L25_V*.json metadata files.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write changes. Without this flag the script only reports what would change.",
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        help="Before writing, create a .bak copy next to each changed JSON file.",
    )
    return parser.parse_args()


def load_json(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON list in {path}")
    return data


def unique_non_empty_urls(records: list[dict[str, Any]]) -> list[str]:
    urls: list[str] = []
    seen = set()
    for item in records:
        url = str(item.get("video_url") or "").strip()
        if url and url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def fill_file(path: Path, write: bool, backup: bool) -> tuple[int, str | None, str]:
    records = load_json(path)
    urls = unique_non_empty_urls(records)

    if not urls:
        return 0, None, "skipped:no-url"
    if len(urls) > 1:
        return 0, None, f"skipped:multiple-urls:{len(urls)}"

    fill_url = urls[0]
    changed = 0
    for item in records:
        if not isinstance(item, dict):
            continue
        if not str(item.get("video_url") or "").strip():
            item["video_url"] = fill_url
            changed += 1

    if changed and write:
        if backup:
            backup_path = path.with_suffix(path.suffix + ".bak")
            if not backup_path.exists():
                shutil.copy2(path, backup_path)
        path.write_text(
            json.dumps(records, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    return changed, fill_url, "filled" if changed else "unchanged"


def main() -> None:
    args = parse_args()
    metadata_dir = args.metadata_dir

    if not metadata_dir.exists():
        raise SystemExit(f"Metadata directory does not exist: {metadata_dir}")

    total_changed = 0
    changed_files = 0
    skipped_files = 0

    for path in sorted(metadata_dir.glob("L25_V*.json")):
        changed, url, status = fill_file(path, args.write, args.backup)
        if status.startswith("skipped"):
            skipped_files += 1
        if changed:
            changed_files += 1
            total_changed += changed

        if changed or status.startswith("skipped"):
            suffix = f" -> {url}" if url else ""
            print(f"{path.name}: {status}, records={changed}{suffix}")

    mode = "WRITE" if args.write else "DRY-RUN"
    print(f"\nMode: {mode}")
    print(f"Changed files: {changed_files}")
    print(f"Filled records: {total_changed}")
    print(f"Skipped files: {skipped_files}")


if __name__ == "__main__":
    main()

import argparse
import json
import time
import zipfile
from pathlib import Path

from pymongo import ReplaceOne
from pymongo.errors import (
    AutoReconnect,
    NetworkTimeout,
    NotPrimaryError,
    ServerSelectionTimeoutError,
)

from src.mongo_connection import ocr_collection, asr_collection

BATCH_SIZE = 1000
MAX_WRITE_RETRIES = 8
TRANSIENT_WRITE_ERRORS = (
    AutoReconnect,
    NetworkTimeout,
    NotPrimaryError,
    ServerSelectionTimeoutError,
)


def flush(collection, operations, label="batch"):
    if not operations:
        return None

    for attempt in range(1, MAX_WRITE_RETRIES + 1):
        try:
            result = collection.bulk_write(operations, ordered=False)
            operations.clear()
            return result
        except TRANSIENT_WRITE_ERRORS as exc:
            if attempt >= MAX_WRITE_RETRIES:
                raise

            delay = min(2 ** (attempt - 1), 15)
            print(
                f"Transient MongoDB write error during {label}: "
                f"{type(exc).__name__}. Retry {attempt}/{MAX_WRITE_RETRIES} "
                f"in {delay}s..."
            )
            time.sleep(delay)


def iter_json_records(zip_path: Path):
    with zipfile.ZipFile(zip_path, "r") as zf:
        json_names = sorted(
            name for name in zf.namelist()
            if name.lower().endswith(".json")
        )
        if not json_names:
            raise ValueError(f"No JSON files found in {zip_path}")

        for name in json_names:
            payload = json.loads(zf.read(name))
            if not isinstance(payload, list):
                raise ValueError(
                    f"Expected a JSON list in {name}, "
                    f"got {type(payload).__name__}"
                )
            for item in payload:
                yield item


def ingest_ocr(zip_path: Path):
    operations = []
    total = 0
    non_empty_text = 0

    for item in iter_json_records(zip_path):
        required = {"idx", "video_id", "frame_id", "ocr_text"}
        missing = required.difference(item)
        if missing:
            raise KeyError(
                f"OCR record missing fields {sorted(missing)}: {item}"
            )

        doc = dict(item)
        doc["_id"] = item["idx"]

        if (item.get("ocr_text") or "").strip():
            non_empty_text += 1

        operations.append(
            ReplaceOne({"_id": doc["_id"]}, doc, upsert=True)
        )
        total += 1

        if len(operations) >= BATCH_SIZE:
            flush(
                ocr_collection,
                operations,
                label=f"OCR around document {total:,}",
            )
            if total % 10000 == 0:
                print(f"OCR progress: {total:,}")

    flush(ocr_collection, operations, label="final OCR batch")
    print(f"OCR ingested/upserted: {total:,} documents")
    print(f"OCR with non-empty text: {non_empty_text:,}")


def ingest_asr(zip_path: Path):
    operations = []
    total = 0

    for item in iter_json_records(zip_path):
        required = {
            "id",
            "video_id",
            "frame_start",
            "frame_end",
            "text",
        }
        missing = required.difference(item)
        if missing:
            raise KeyError(
                f"ASR record missing fields {sorted(missing)}: {item}"
            )

        doc = dict(item)
        doc["_id"] = item["id"]
        doc["frame_mid"] = (
            int(item["frame_start"]) + int(item["frame_end"])
        ) // 2

        operations.append(
            ReplaceOne({"_id": doc["_id"]}, doc, upsert=True)
        )
        total += 1

        if len(operations) >= BATCH_SIZE:
            flush(
                asr_collection,
                operations,
                label=f"ASR around document {total:,}",
            )
            if total % 10000 == 0:
                print(f"ASR progress: {total:,}")

    flush(asr_collection, operations, label="final ASR batch")
    print(f"ASR ingested/upserted: {total:,} documents")


def main():
    parser = argparse.ArgumentParser(
        description="Ingest AIC OCR + ASR metadata ZIPs into local MongoDB."
    )
    parser.add_argument(
        "--ocr", type=Path, required=True, help="Path to OCR metadata ZIP"
    )
    parser.add_argument(
        "--asr", type=Path, required=True, help="Path to ASR metadata ZIP"
    )
    args = parser.parse_args()

    if not args.ocr.exists():
        raise FileNotFoundError(args.ocr)
    if not args.asr.exists():
        raise FileNotFoundError(args.asr)

    print("=== Ingest OCR ===")
    ingest_ocr(args.ocr)

    print("\n=== Ingest ASR ===")
    ingest_asr(args.asr)

    print(
        "\nIngestion complete. Re-running is safe because documents "
        "are upserted by fixed _id values."
    )


if __name__ == "__main__":
    main()

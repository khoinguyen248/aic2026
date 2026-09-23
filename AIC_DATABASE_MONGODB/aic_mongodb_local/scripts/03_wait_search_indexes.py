import time

from src.mongo_connection import ocr_collection, asr_collection

TARGETS = [
    (ocr_collection, "ocr_search"),
    (ocr_collection, "caption_search"),
    (asr_collection, "asr_search"),
]
MAX_WAIT_SECONDS = 600
POLL_SECONDS = 5


def get_index_state(collection, name):
    for idx in collection.list_search_indexes():
        if idx.get("name") == name:
            return idx
    return None


def main():
    deadline = time.monotonic() + MAX_WAIT_SECONDS

    while time.monotonic() < deadline:
        all_ready = True
        print("--- Search index status ---")

        for collection, name in TARGETS:
            idx = get_index_state(collection, name)
            if idx is None:
                print(f"{name}: NOT FOUND")
                all_ready = False
                continue

            status = idx.get("status", "UNKNOWN")
            queryable = idx.get("queryable", False)
            print(f"{name}: status={status}, queryable={queryable}")

            if status != "READY" or not queryable:
                all_ready = False

        if all_ready:
            print("All Search indexes are READY.")
            return

        print(f"Waiting {POLL_SECONDS} seconds...\n")
        time.sleep(POLL_SECONDS)

    raise SystemExit(
        f"Search indexes did not become READY within {MAX_WAIT_SECONDS} seconds."
    )


if __name__ == "__main__":
    main()

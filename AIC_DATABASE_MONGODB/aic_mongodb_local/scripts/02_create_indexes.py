from pymongo.operations import SearchIndexModel

from src.mongo_connection import ocr_collection, asr_collection


def create_normal_indexes():
    print("Creating normal MongoDB indexes...")
    print(" OCR:", ocr_collection.create_index([("video_id", 1), ("frame_id", 1)], name="video_frame_idx"))
    print(
        " ASR:",
        asr_collection.create_index(
            [("video_id", 1), ("frame_start", 1), ("frame_end", 1)],
            name="video_frame_range_idx",
        ),
    )


def ensure_search_index(collection, name: str, field: str):
    existing = {idx.get("name") for idx in collection.list_search_indexes()}
    if name in existing:
        print(f"Search index '{name}' already exists; skipping creation.")
        return

    model = SearchIndexModel(
        definition={
            "mappings": {
                "dynamic": False,
                "fields": {
                    field: {"type": "string"}
                },
            }
        },
        name=name,
    )
    created_name = collection.create_search_index(model=model)
    print(f"Created Search index '{created_name}' on field '{field}'.")


def main():
    create_normal_indexes()
    print("\nCreating MongoDB Search indexes...")
    ensure_search_index(ocr_collection, "ocr_search", "ocr_text")
    ensure_search_index(ocr_collection, "caption_search", "caption")
    ensure_search_index(asr_collection, "asr_search", "text")
    print("\nSearch index builds are asynchronous. Run scripts/03_wait_search_indexes.py next.")


if __name__ == "__main__":
    main()

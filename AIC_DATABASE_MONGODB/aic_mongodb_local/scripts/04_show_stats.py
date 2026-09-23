from src.mongo_connection import db, ocr_collection, asr_collection

print("Database:", db.name)
print("OCR documents:", f"{ocr_collection.count_documents({}):,}")
print("OCR non-empty:", f"{ocr_collection.count_documents({'ocr_text': {'$nin': ['', None]}}):,}")
print("ASR documents:", f"{asr_collection.count_documents({}):,}")

print("\nOCR indexes:")
for idx in ocr_collection.list_indexes():
    print(" ", idx.get("name"))

print("\nASR indexes:")
for idx in asr_collection.list_indexes():
    print(" ", idx.get("name"))

print("\nSearch indexes:")
for collection, label in [(ocr_collection, "OCR"), (asr_collection, "ASR")]:
    for idx in collection.list_search_indexes():
        print(f" {label}: name={idx.get('name')} status={idx.get('status')} queryable={idx.get('queryable')}")

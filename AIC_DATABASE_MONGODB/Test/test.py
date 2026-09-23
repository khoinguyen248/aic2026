from mongo_search import search_ocr, search_asr


query = "Cơm Tấm"


ocr_results = search_ocr(
    query=query,
    limit=10,
)

asr_results = search_asr(
    query=query,
    limit=10,
)


print("OCR RESULTS")

for result in ocr_results:
    print(result)


print("\nASR RESULTS")

for result in asr_results:
    print(result)
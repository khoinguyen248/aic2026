import os
import json

def main(metadata_dir: str) -> None:
    if not os.path.exists(metadata_dir):
        raise ValueError(f"{metadata_dir} doesn't exist")
    idx = 0
    for video_file in sorted(os.listdir(metadata_dir)):
        video_path = os.path.join(metadata_dir, video_file)
        with open(video_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for item in data:
            item["idx"] = idx
            idx += 1
        with open(video_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print(f"[INFO] Dumps data in to {video_file.split(".")[0]}")

if __name__ == "__main__":
    main("runtime-data/metadata/ocr")
        

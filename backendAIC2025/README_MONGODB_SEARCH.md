# MongoDB OCR / ASR Search — Full Guide

How on-screen text (**OCR**) and spoken content (**ASR**) are stored, indexed, and
searched in MongoDB, and how those searches feed both the main scene search and TRAKE.

---

## 1. Overview

Two MongoDB collections back all text-based retrieval:

| Collection | Holds | Text field | Search index |
|---|---|---|---|
| `ocr_metadata` | One doc **per keyframe** (on-screen text) | `ocr_text` | `ocr_search` |
| `asr_metadata` | One doc **per speech segment** (a time range) | `text` | `asr_search` |

Both live in database **`aic2026`** (env `MONGO_SEARCH_DB`). Search uses **MongoDB
Atlas Search** (`$search`) with **fuzzy matching**, so small typos / OCR noise still match.

The image is `mongodb/mongodb-atlas-local` — it bundles the Atlas Search engine
(`mongot`) locally, which is why `$search` works without a cloud Atlas cluster.

---

## 2. Data model

### `ocr_metadata` (per keyframe)
```json
{
  "idx": 315264,                       // global keyframe id (also used as _id)
  "video_id": "L30_V079",
  "L": "30", "V": "079",
  "keyframe_order": 0,
  "frame_id": 2,                        // raw video frame number of this keyframe
  "fps": 25.0,
  "frame_stamp": 0.08,                  // seconds
  "path": "Keyframes/L30_V079/000002.webp",
  "video_path": "Videos/L30_V079.mp4",
  "video_url": "https://youtube.com/watch?v=...",
  "objects": [], "detection": [],
  "ocr_text": ""                        // on-screen text (may be empty)
}
```

### `asr_metadata` (per speech segment)
```json
{
  "id": "L30_V068_3",                   // also used as _id
  "video_id": "L30_V068",
  "t_start": 12.4, "t_end": 15.9,       // seconds
  "frame_start": 310, "frame_end": 398, // raw frame range of the segment
  "text": "…transcribed speech…"
}
```

> **Key link:** an ASR segment is a *frame range* `[frame_start, frame_end]`. To show a
> picture, that range is mapped onto the **OCR keyframes** of the same video that fall
> inside the range (they share the `frame_id` space).

---

## 3. Search indexes (Atlas Search)

Created by `scripts/import_ocr_asr.py` (or `02_create_indexes.py`):

```python
# ocr_search on ocr_metadata.ocr_text
{ "mappings": { "dynamic": False, "fields": { "ocr_text": { "type": "string" } } } }
# asr_search on asr_metadata.text
{ "mappings": { "dynamic": False, "fields": { "text": { "type": "string" } } } }
```

Plain B-tree indexes also exist for filtering: `video_id`, `frame_id` on OCR;
`(video_id, frame_start, frame_end)` on ASR.

Check they are built:
```bash
docker exec aic2026-mongodb-1 mongosh "mongodb://aicadmin:aic2026local@localhost:27017/aic2026?authSource=admin" \
  --quiet --eval "db.ocr_metadata.getSearchIndexes(); db.asr_metadata.getSearchIndexes()"
```

---

## 4. Core search functions

All in [`app/services/mongo_search.py`](app/services/mongo_search.py). Connection comes
from env `MONGO_SEARCH_URI` / `MONGO_SEARCH_DB` via `get_database()`.

### 4.1 `search_ocr(query, limit=20, max_edits=1, prefix_length=1)`
Fuzzy full-text search over `ocr_text`; returns keyframe docs (with `path`, `frame_id`,
`video_id`, `video_url`, `score`). Pipeline:
```python
[
  {"$search": {"index": "ocr_search",
               "text": {"query": query, "path": "ocr_text",
                        "fuzzy": {"maxEdits": 1, "prefixLength": 1}}}},
  {"$limit": limit},
  {"$project": {"_id": 0, "idx": 1, "video_id": 1, "frame_id": 1,
                "path": 1, "video_url": 1, "ocr_text": 1,
                "score": {"$meta": "searchScore"}}},
]
```

### 4.2 `search_asr(query, limit=20, …)`
Fuzzy search over `text`, then **maps each matched segment to OCR keyframes** inside
`[frame_start, frame_end]` of the same video, so results are displayable frames.

### Tuning fuzziness
- `max_edits` — allowed typos (0 = exact, 1 = default, 2 = loose). Pass `None` to disable fuzzy.
- `prefix_length` — leading chars that must match exactly (protects short tokens).

---

## 5. Video-scoped helpers (used by TRAKE)

These narrow a text search to **one already-selected video**. Same file.

| Function | Returns | Used for |
|---|---|---|
| `ocr_frame_ids_in_video(query, video_id, limit=50)` | `[(frame_id, path)]` matching OCR in that video | per-event OCR boost / inject |
| `asr_ranges_in_video(query, video_id, limit=50)` | `[(frame_start, frame_end)]` matching ASR in that video | per-event ASR boost |
| `keyframes_in_range(video_id, frame_start, frame_end, limit=50)` | `[(frame_id, path)]` keyframes inside a range | ASR-only event candidates |

Scoped OCR/ASR run `$search` → `$limit 300` (top by relevance) → `$match {video_id}` →
final `$limit`, because Atlas `$search` must be the first stage (can't put a plain
`$match` before it).

---

## 6. How OCR/ASR feed the rest of the system

### 6.1 Main scene search (KIS) — *boost / merge*
In the sidebar, OCR/ASR each have **Standalone** and **Merge** modes:
- **Standalone** → runs `search_ocr` / `search_asr` and shows those frames directly.
- **Merge** → matched frames are pushed to the top of the visual search results
  (`app/controllers/search_controller.py`, the ASR/OCR boost leg).

### 6.2 TRAKE — *per-event OCR/ASR*
Each event can carry optional `ocr` / `asr` text. In
[`app/services/trake_service.py`](app/services/trake_service.py):

1. **Tier 1 (pick video)** — `ocr_asr_candidate_videos()` searches OCR/ASR globally and
   guarantees any video that matches is added to the candidate set (so a strong text
   signal, e.g. OCR "củ năng" → `L26_V072`, is never dropped by the visual stage).
2. **Tier 2 (locate each event)** — `_event_ocr_asr_targets()` + `_apply_ocr_asr_boost()`
   multiply the score of candidate frames that match OCR (±window) or fall in an ASR
   range, and **inject** the matched OCR keyframes as new candidates.
3. **OCR/ASR-only events** — an event with *no visual description* gets its candidates
   purely from `_ocr_asr_frames_for_event()` (OCR keyframes + ASR-range keyframes).

Config (env): `TRAKE_OCRASR_BOOST` (score multiplier, default `0.3`),
`TRAKE_OCRASR_WINDOW` (frame proximity for OCR match, default `250`).

---

## 7. Importing / re-importing data

`ocr_metadata` / `asr_metadata` are populated by
[`scripts/import_ocr_asr.py`](scripts/import_ocr_asr.py) (idempotent — wipes and reloads):

```powershell
cd aic2026
$env:MONGO_SEARCH_URI="mongodb://aicadmin:aic2026local@localhost:27017/?authSource=admin&directConnection=true"
$env:MONGO_SEARCH_DB="aic2026"
python backendAIC2025/scripts/import_ocr_asr.py "path\to\ocr" "path\to\asr"
```
It also (re)creates the two Atlas Search indexes and the plain indexes.

---

## 8. Try it manually

### Python (inside the backend container)
```python
from app.services.mongo_search import search_ocr, search_asr
print(search_ocr("củ năng", limit=5))
print(search_asr("chào mừng", limit=5))
```

### mongosh — raw `$search`
```javascript
db.ocr_metadata.aggregate([
  { $search: { index: "ocr_search",
               text: { query: "củ năng", path: "ocr_text", fuzzy: { maxEdits: 1 } } } },
  { $limit: 5 },
  { $project: { _id: 0, video_id: 1, frame_id: 1, ocr_text: 1,
                score: { $meta: "searchScore" } } }
])
```

### Counts
```javascript
db.ocr_metadata.countDocuments({})   // ~317,961
db.asr_metadata.countDocuments({})   // ~25,168
```

---

## 9. Notes & gotchas

- **`$search` needs the Atlas Search index built.** After import, indexes take a few
  seconds to become queryable; a query before that returns empty.
- **`$search` must be the first pipeline stage** — filter by `video_id` *after* it
  (see the scoped helpers).
- **fps caveat:** some videos are **30 fps** even though metadata records **25** — a
  `frame_id` is a raw frame number, so mixing the two shifts time. Verify per video when
  computing timestamps.
- **ASR has no single frame** — always a range; display goes through the OCR keyframes in
  that range (`keyframes_in_range`).
- **Text is Vietnamese** — OCR/ASR queries are matched as-is (not translated); keep the
  query in Vietnamese to match the stored text.

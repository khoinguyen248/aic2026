# Improvements: TRAKE UI + ASR search + OCR search

> Everything that changed in this round of work and how to configure it. Read alongside
> [README_TRAKE.md](README_TRAKE.md) (the TRAKE pipeline) and `AIC2026_IMPROVEMENT_SPEC (1).md`
> (§8 OCR, §9 ASR, §10.3 TRAKE).

---

## 1. Summary of the work

1. **Three-tier TRAKE + rerank** — finds a chronological sequence of events and generates up to 100
   ranked frame combinations automatically.
   - Tier 1 picks the video (DP alignment), tier 2 locates events coarsely, tier 3 refines to the
     source frame (when the videos are available).
   - Moment rerank: **algorithmic** (peak detection, always on) plus **local Qwen2.5-VL** (only when the
     top two candidates tie).
2. **TRAKE UI** — a panel to enter N events → list of combinations → click one to view its frames for
   verification (images decoded from the video).
3. **ASR search** — search **spoken content** (collection `asr_segments`). Two modes: standalone, or
   merged into the main search.
4. **OCR search** — search **on-screen text** (`ocr_text` inside `frames`). Same two modes.
5. **UI cleanup** — removed the old object search (palette, drop area, object fill-in, AND/OR, "Text
   indicator", temporal-fuzzy selector). The UI is now entirely in English.

---

## 2. Files added / changed / deleted

### Backend (`backendAIC2025/`)

| File | Change |
|---|---|
| `app/services/trake_service.py` | **NEW** — the whole TRAKE algorithm (DP, refinement, Cartesian combinations, algorithmic + local Qwen rerank) |
| `app/controllers/trake_controller.py` | **NEW** — `trake_search()` and `trake_frame()` (decodes a frame for verification) |
| `app/controllers/asr_controller.py` | **NEW** — `asr_search()` (standalone) and `asr_boost_idxset()` (merge mode) |
| `app/controllers/ocr_controller.py` | **NEW** — `ocr_search()` (standalone) and `ocr_boost_idxset()` (merge mode) |
| `app/controllers/search_controller.py` | Added `ensure_models()`; accepts the `asr`/`ocr` parameters for merge boost |
| `app/models/eeiot_model.py` | Added `get_asr_collection()` → `asr_segments` |
| `app/routes/search_routes.py` | Added the `/trake`, `/frame`, `/asr` and `/ocr` routes |
| `app/config.py` | Added the TRAKE and Qwen keys (§4) |
| `app/models/search_model.py` | **Security fix**: removed the hard-coded Gemini API key and a personal checkpoint path; both now come from `Config` |
| `requirements.txt` | Added (commented out) the optional local-Qwen dependencies: `accelerate`, `bitsandbytes`, `qwen-vl-utils` |

### Frontend (`frontend-final/vite-project/src/`)

| File | Change |
|---|---|
| `TrakePanel.jsx` | **NEW** — the TRAKE panel (enter N events → combinations → verify frames) |
| `AsrResults.jsx` | **NEW** — renders standalone ASR results |
| `api.js` | Added `trakeSearch`, `asrSearch`, `ocrSearch`, `frameUrl` |
| `Jobs.jsx` | Removed object search; added the ASR and OCR blocks (two-mode toggle); wired in TrakePanel; UI in English |
| `ItemPalette.jsx`, `DropArea.jsx` | **DELETED** (dead code once object search was removed) |

### Data / config

| File | Change |
|---|---|
| `.env.example` | Added the TRAKE and Qwen keys |

---

## 3. New endpoints

| Method | Route | Purpose | Body / query |
|---|---|---|---|
| POST | `/search/trake` | TRAKE search | `{ "events": ["...","..."], "language": true }` |
| GET | `/search/frame` | Decode one source frame for verification | `?L=30&V=068&frame_id=1007` |
| POST | `/search/asr` | Standalone ASR search (spoken content) | `{ "query": "the chairman announced", "k": 50 }` |
| POST | `/search/ocr` | Standalone OCR search (on-screen text) | `{ "query": "TEAM A", "k": 100 }` |
| POST | `/search/collection` | Main search (existing) — **new** merge parameters | `{ ..., "asr": "...", "ocr": "..." }` |

> `asr`/`ocr` on `/search/collection` is the "merge" mode: frames whose speech or on-screen text match
> are pushed to the top of the results.

---

## 4. `.env` configuration

**ASR/OCR need no new variables** — they only need Mongo enabled and the data loaded (§5). The keys
below belong to **TRAKE**:

```env
# ===== TRAKE tier 3 (source-frame refinement) — enable only if the machine has the videos =====
TRAKE_TIER3_ENABLED=false          # true = three tiers; false = automatic two tiers
VIDEO_ROOT=                        # folder holding the original videos, e.g. /mnt/usb/aic2026_videos

TRAKE_TOP_M=150                    # top-M candidates per event in tier 1
TRAKE_TOP_VIDEOS=2                 # how many candidate videos to consider
TRAKE_MAX_COMBOS=100               # maximum submissions (the competition allows 100)
TRAKE_TIER3_RADIUS=15              # scan radius around the coarse position (±15 frames)
TRAKE_TIER3_STRIDE=1               # scan step (1 = every frame)
TRAKE_VIDEO_CONFIDENCE_THRESHOLD=0.8   # below this, share slots with the rank-2 video

# ===== Tier-3 moment rerank =====
TRAKE_RERANK_TIE_MARGIN=0.03       # candidates closer than this count as a "tie" -> only then call Qwen
TRAKE_QWEN_RERANK_ENABLED=false    # true = enable local Qwen (needs a GPU); false = algorithm only
QWEN_MODEL_PATH=Qwen/Qwen2.5-VL-7B-Instruct   # HF id or local folder; may point at an AWQ/GPTQ build
QWEN_QUANTIZATION=4bit             # 4bit | 8bit | none  (4bit ≈ 6-8GB VRAM for a 7B model)
QWEN_DEVICE_MAP=auto               # auto | cuda | cpu
QWEN_MAX_NEW_TOKENS=10

# ===== Enable search + Mongo (required for EVERY search, ASR/OCR included) =====
SEARCH_ENABLED=true
MONGO_ENABLED=true
MONGO_URI2=mongodb://localhost:27017/aic2026   # DB holding the frames + asr_segments collections
```

### The two TRAKE cases (automatic, no code changes)

| | Case 1 — videos available (3 tiers) | Case 2 — no videos (2 tiers) |
|---|---|---|
| Enabled by | `TRAKE_TIER3_ENABLED=true` and a valid `VIDEO_ROOT` | leaving the defaults (false/empty) |
| Source-frame refinement | yes | skipped, stops at keyframe level |
| Rerank | Qwen (if `TRAKE_QWEN_RERANK_ENABLED=true`) plus the algorithm | **algorithm** (peak detection) |
| Verification image in the UI | the exact frame decoded from the video | placeholder fallback (YouTube link + ±10 viewer) |

The TRAKE response reports `"mode"` (`case1_full`/`case2_coarse`), `"tier"` (3/2) and
`"rerank_method"` (`qwen`/`algorithm`) so you can tell what actually ran.

---

## 5. Data required in MongoDB

The backend uses **one database** (from `MONGO_URI2`) with two collections.

### `frames` — keyframes (already exists; used by KIS/QA/OCR/TRAKE)

One document per keyframe:

```json
{"idx": 315264, "video_id": "L30_V079", "L": "30", "V": "079", "frame_id": 2, "fps": 25.0,
 "frame_stamp": 0.08, "path": "Keyframes/L30_V079/000002.webp", "video_url": "https://youtube.com/watch?v=...",
 "objects": [], "detection": [], "ocr_text": ""}
```

- OCR search uses the **`ocr_text`** field.
- Add an index on `(video_id, frame_id)` so merge boost is fast, and a unique index on `idx`.

### `asr_segments` — speech segments (NEW, for ASR)

One document per ASR segment, derived from `metadata_asr_clean/<video_id>.json`:

```json
{"id": 3106800000, "video_id": "L30_V068", "t_start": 0.0, "t_end": 20.0,
 "frame_start": 0, "frame_end": 500, "text": "strolling along the picturesque road..."}
```

- ASR search uses the **`text`** field; merge mode uses `frame_start`/`frame_end` to project a match
  back onto keyframes.

### Full-text search

- ASR/OCR prefer an **Atlas Search index named `default`** (fuzzy). Without one they **fall back to
  regex** automatically — still correct, just slower.
- On Mongo Atlas Local (`mongodb/mongodb-atlas-local`), create the `default` Atlas Search index on
  `frames.ocr_text` and on `asr_segments.text`.

---

## 6. Running and testing

### Backend

Inside Docker (recommended on Linux — see [README.md](README.md)):

```bash
docker compose up -d --build backend-api
```

Outside Docker, when you need tier-3 video decoding:

```bash
cd backendAIC2025 && pip install -r requirements.txt && python run.py
```

Optional local Qwen: `pip install accelerate bitsandbytes qwen-vl-utils`. Either way `.env` needs
`SEARCH_ENABLED=true` and a reachable Mongo.

### Frontend

```bash
cd frontend-final/vite-project && npm install && npm run dev
```

The dev server runs at <http://localhost:5173>; the containerized build is served at
<http://localhost:8088>.

### Endpoint smoke tests

```bash
curl -X POST localhost:5000/search/trake -H "Content-Type: application/json" -d '{"events":["athlete plants the take-off foot","clears the bar","lands on the mat"],"language":true}'
```

```bash
curl -X POST localhost:5000/search/asr -H "Content-Type: application/json" -d '{"query":"chủ tịch công bố","k":50}'
```

```bash
curl -X POST localhost:5000/search/ocr -H "Content-Type: application/json" -d '{"query":"TEAM A","k":100}'
```

---

## 7. Using the new UI

- **Mode selector** (top right): KIS / QA / **TRAKE**.
  - Choosing **TRAKE** opens the panel: add N events (Add event) → **TRAKE search** → list of
    combinations → click one to expand the verification frame grid.
- **Sidebar (menu button)**: two text-search blocks — **ASR search** (spoken content) and **OCR search**
  (on-screen text).
  - Each block has a toggle: **Standalone** (its own results) or **Merge into main search** (folds into
    the Screen 1/2/3 search button and pushes matching frames to the top).

---

## 8. ⚠️ Reconciling with a teammate's Mongo/Qdrant

This backend was built against **the schema we currently have**. When pulling a teammate's Mongo or
Qdrant work, check:

1. **ASR collection name**: ours is `asr_segments` (`app/models/eeiot_model.py`). Rename if theirs
   differs.
2. **Field names**: `ocr_text` (frames) and `text`/`frame_start`/`frame_end`/`video_id`
   (asr_segments). Align if theirs differ.
3. **Atlas Search index `default`** on `ocr_text` / `text` — without it you are on the regex fallback.
4. **ASR data not loaded**: if `metadata_asr_clean/*.json` has not been ingested into `asr_segments`, an
   ingest script is needed (not written yet — ask if you need it).
5. **Semantic embeddings for ASR/OCR**: today ASR/OCR are **lexical full-text (Mongo)** only. Add a
   semantic leg once Qdrant embeddings for them exist.

---

## 9. PR checklist (per README_MEMBERS.md)

- **New env keys**: the `TRAKE_*` and `QWEN_*` keys from §4 (already in `.env.example`).
- **New endpoints**: `/search/trake`, `/search/frame`, `/search/asr`, `/search/ocr`; `/search/collection`
  gained `asr`/`ocr`.
- **New data**: the `asr_segments` collection must be ingested.
- **Never commit**: `.env`, videos/keyframes, checkpoints, embeddings.
- **Model impact**: Qwen2.5-VL runs **locally and quantized** (no API); CLIP is the main leg (BEiT-3 is
  not used for TRAKE yet because the `beit3/` package is missing there).

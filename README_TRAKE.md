# TRAKE — implementation guide (for people reading or changing the code)

> Purpose of this file: after reading it, someone who has **never touched the TRAKE code** should know
> where the code lives, in what order it runs, and which function to edit for a given change. It does
> not go deep into the maths — for that, read `trake_service.py` directly, where the tricky parts carry
> inline comments.

## 1. Call graph — who calls whom

```
Client (frontend/Postman)
   │  POST /search/trake  {events: [...], language: true}
   ▼
search_routes.py            -> route declaration only, delegates to the controller
   ▼
trake_controller.py         -> reads the request, translates VI->EN if asked, loads models, calls the service
   ▼
trake_service.run_trake()   -> the conductor; runs the four steps below in order
   │
   ├─ 1. select_video_dp()        -> pick the right video
   ├─ 2. allocate_video_slots()   -> split the submission slots between rank 1 and rank 2 videos
   ├─ 3. locate_events_exact()    -> coarsely locate each event inside the chosen video
   ├─ 4. refine_event_fine()      -> (only with original videos) refine down to the exact source frame
   │        └─ moment rerank: algorithmic (default) or Qwen (on a tie, when enabled)
   └─ 5. build_cartesian_submissions() -> combine into many ranked submissions
   ▼
Returns JSON: {mode, video_candidates, submissions}
```

## 2. Which file does what

| File | Role |
|---|---|
| [`app/routes/search_routes.py`](backendAIC2025/app/routes/search_routes.py) | Declares `POST /search/trake`; no logic |
| [`app/controllers/trake_controller.py`](backendAIC2025/app/controllers/trake_controller.py) | Handles the HTTP request, validates input, calls model + service, returns JSON |
| [`app/controllers/search_controller.py`](backendAIC2025/app/controllers/search_controller.py) | Holds `ensure_models()` — loads CLIP/FAISS **exactly once** (singleton). TRAKE reuses it instead of loading its own copy |
| [`app/services/trake_service.py`](backendAIC2025/app/services/trake_service.py) | **The whole algorithm lives here** — the only file to read if you want to understand or change TRAKE logic |
| [`app/config.py`](backendAIC2025/app/config.py) | TRAKE settings read from `.env` (refinement on/off, video path, Qwen rerank on/off, ...) |

## 3. Step by step through `trake_service.py`

### Step 0 — turn sentences into vectors

```python
event_vecs = encode_texts(events_text, clip_bundle, device)
```

Each event description becomes one vector (CLIP text encoder): `event_vecs[0]` for event 1,
`event_vecs[1]` for event 2, and so on. Every match later is a **vector-versus-vector** dot product —
higher means more similar.

### Step 1 — `select_video_dp()`: find the right video

Simplified:

1. For each event, take the top-150 most similar keyframes **across the whole corpus**, regardless of
   video.
2. Group those keyframes by video (`L`, `V`).
3. Only videos that appear in the top-150 of **every** event stay in the running. A video missing one
   event is treated as insufficient evidence and dropped.
4. For each remaining video, compute the best path through the events **in chronological order** — a
   later event must occur after an earlier one, no reordering allowed. `_dp_align()` does this; read
   its comments if you want to know how the optimal path is chosen.
5. The video with the highest total path score wins.

If no video survives step 3, the search automatically retries with top-450, then top-1350 (×3 each
time, at most three attempts) before reporting "no video found".

### Step 2 — `allocate_video_slots()`: should we fully trust the top video?

The competition allows up to 100 submissions. If rank 1 and rank 2 score close to each other, spending
all 100 on rank 1 is a gamble. This function splits them:

- Rank 1 is "very confident" (above `TRAKE_VIDEO_CONFIDENCE_THRESHOLD`, default 0.8) → all 100 slots go
  to rank 1.
- Otherwise the slots are shared, for example 80 for rank 1 and 20 for rank 2.

### Step 3 — `locate_events_exact()`: coarse position of each event

Take every keyframe of that one video (no cross-video mixing), score each event against each keyframe,
and keep the best match — **subject to the constraint that a later event's keyframe must come after the
earlier event's**. If that constraint yields nothing, the code relaxes it rather than returning empty.
The function returns the **top-3 candidates per event**, not just one, which is what feeds the
combination step.

### Step 4 — `refine_event_fine()`: refine to the source frame (ONLY WITH ORIGINAL VIDEOS)

This is the one step that needs the **real video file**, not just keyframes. Starting from the coarse
position of step 3, it opens the source video, reads about 30 frames around it (±15), scores each frame
against the event with CLIP, and gets a score curve over time. Whether this step runs at all is decided
automatically — see §4 (Case 1/2).

**Moment rerank (choosing the right frame among near-identical ones):**

1. **Default — algorithmic, free, always on** (`pick_semantic_frame_algorithmic()`): instead of taking
   the maximum score (argmax), it looks for a **distinct peak** in the score curve (prominence, via
   `scipy.signal.find_peaks`). That separates the real "moment" from a stretch of frames CLIP cannot
   tell apart. If no peak is found (or scipy is missing) it falls back to plain argmax, so it is never
   worse than the old behaviour.
2. **Optional — Qwen2.5-VL running LOCALLY, called only when needed**: if the top two candidates are
   still a **close tie** (score gap < `TRAKE_RERANK_TIE_MARGIN`, default 0.03) **and**
   `TRAKE_QWEN_RERANK_ENABLED=true`, the tied frames plus the event description go to Qwen, which picks
   the semantically correct moment. Qwen is **loaded locally through transformers and kept warm on the
   GPU** (spec §13), **quantized to 4bit/8bit** to fit the VRAM of a 7B/72B model — **no external API is
   used**. If loading or inference fails (no GPU, missing library, ...) it **falls back to the
   algorithmic result** and never breaks the response.

The Qwen on/off mechanism works **exactly like the Case 1/2 switch** used for tier 3: driven by
configuration, no code changes when moving to another machine.

## 4. Case 1 (original videos available) vs Case 2 (not) — where the decision lives

```python
def tier3_globally_ready():
    if not Config.TRAKE_TIER3_ENABLED:
        return False, "..."
    if not Config.VIDEO_ROOT or not os.path.isdir(Config.VIDEO_ROOT):
        return False, "..."
    ...
    return True, "tier 3 ready"
```

`run_trake()` calls this once. On `False`, the whole of step 4 is skipped and the coarse results of
step 3 feed step 5 directly. To enable Case 1, set two variables in `.env`:

```env
TRAKE_TIER3_ENABLED=true
VIDEO_ROOT=/mnt/usb/aic2026_videos
```

Leave them unset — or set them while the USB drive is unplugged — and it falls back to Case 2 without
code changes and without crashing.

**Qwen rerank has its own equivalent switch** (`qwen_rerank_ready()`), independent of Case 1/2. Qwen
runs **locally** (loaded through transformers, kept warm on the GPU, quantized to save RAM/VRAM), **not
through an API**:

```env
TRAKE_QWEN_RERANK_ENABLED=true
QWEN_MODEL_PATH=Qwen/Qwen2.5-VL-7B-Instruct
QWEN_QUANTIZATION=4bit          # 4bit | 8bit | none
QWEN_DEVICE_MAP=auto
QWEN_MAX_NEW_TOKENS=10
```

- `QWEN_QUANTIZATION=4bit` (default): a 7B model fits in ~6–8GB VRAM thanks to bitsandbytes. Use `8bit`
  if you have VRAM to spare, or `none` when `QWEN_MODEL_PATH` already points at a **prequantized
  AWQ/GPTQ** build.
- Extra packages, needed only when Qwen is enabled (and it needs a GPU): `accelerate`, `bitsandbytes`
  (for 4bit/8bit) and `qwen-vl-utils` — listed as comments in `requirements.txt`.
- The model is loaded **lazily, once**, on the first rerank and then kept warm. If loading fails (no
  GPU, missing library) Qwen switches itself off and the algorithmic path is used instead. Leave it
  disabled and only the algorithm ever runs.

## 5. Where to change what

| Goal | Edit |
|---|---|
| Change how many candidate videos are considered (currently top-2) | `Config.TRAKE_TOP_VIDEOS` in `.env` |
| Change the refinement radius (currently ±15 frames) | `Config.TRAKE_TIER3_RADIUS` |
| Change the score gap that counts as a "tie" for Qwen | `Config.TRAKE_RERANK_TIE_MARGIN` |
| Change the prompt sent to Qwen | `qwen_rerank_candidates()` in `trake_service.py` |
| Change how Qwen is loaded or quantized | `_load_qwen()` in `trake_service.py` plus the `QWEN_*` variables |
| Add a BEiT-3 or jina-clip-v2 leg to TRAKE (CLIP only today) | Write `encode_texts_beit3()`/`encode_images_beit3()` alongside `encode_texts()`/`encode_images()` in `trake_service.py`, then let `run_trake()` accept an extra `model_bundle` |
| Change how the video is chosen (step 1) | `_dp_align()` + `select_video_dp()` |
| Change how submissions are generated (step 5) | `build_cartesian_submissions()` + `nms_candidates()` |
| Test the logic quickly without Mongo or real models | `_dp_align`, `build_cartesian_submissions`, `pick_semantic_frame_algorithmic`, `qwen_rerank_ready` and `qwen_rerank_candidates` are pure functions (or fall back safely), so you can call them with fake data — no Flask, DB or model required |

## 6. Quick API use (manual testing)

```
POST /search/trake
{ "events": ["description of event 1", "description of event 2", "..."], "language": true }
```

The response contains `submissions`: a ranked list of `{video_id, frame_ids}` — take them from the top
of the list to submit. It also reports `qwen_rerank_globally_ready`, `qwen_rerank_reason` and
`qwen_rerank_used_events` so you can tell whether Qwen was actually invoked.

Requires `SEARCH_ENABLED=true`.

**Running inside Docker:** the `search` and `search-cuda` image stages ship torch, scipy and
open_clip, so the vector part of TRAKE runs in the container. Tier 3 does not: `opencv-python` is
installed but `import cv2` fails with `libGL.so.1: cannot open shared object file`, because the
`python:3.11-slim` base has no OpenGL runtime. Until the image switches to `opencv-python-headless` (or
installs `libgl1`), run tier-3 refinement and `/search/frame` outside Docker with `python run.py`.

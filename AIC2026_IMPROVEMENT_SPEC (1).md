# Technical specification — AIC 2026 retrieval system upgrade

> This document collects the full upgrade plan from the 2025 system (BEiT-3 + CLIP + FAISS + MongoDB)
> to a **multi-model ensemble + Qdrant + Qwen2.5-VL rerank** architecture, specifying each technique
> with worked examples.
> Scope: the three query types of the preliminary round — **Textual KIS**, **Q&A**, **TRAKE**.

---

## Table of contents

0. [Architecture summary](#0-architecture)
1. [Models and their roles](#1-models)
2. [Embedding generation (two main legs plus shared legs)](#2-embeddings)
3. [Qdrant — schema and configuration](#3-qdrant-schema)
4. [Ingestion](#4-ingestion)
5. [Query augmentation (templates, HyDE, bilingual)](#5-augmentation)
6. [Stage-1 ensemble — multi-leg RRF](#6-rrf)
7. [Stage-2 ensemble — Qwen2.5-VL cross-encoder rerank](#7-rerank)
8. [OCR leg](#8-ocr)
9. [Audio leg — ASR and sound events](#9-audio)
10. [Pipeline per query type](#10-pipelines)
    - 10.1 [Textual KIS](#101-kis)
    - 10.2 [Q&A and VQA](#102-qa)
    - 10.3 [Three-tier TRAKE with DP alignment](#103-trake)
11. [Embeddings shared by other teams](#11-shared-embeddings)
12. [Dev set and weight selection](#12-dev-set)
13. [Latency optimization](#13-latency)
14. [Security and configuration cleanup](#14-security)
15. [Hybrid Mongo + Qdrant architecture (orchestrator)](#15-hybrid)
16. [Implementation order](#16-roadmap)

---

<a name="0-architecture"></a>
## 0. Architecture summary

```
                 ┌─────────────── QUERY (Vietnamese) ───────────────┐
                 │                                                   │
        ┌────────┴─────────┐                            ┌────────────┴───────────┐
        │  Query augment   │                            │  HyDE (Qwen2.5-VL)     │
        │  templates + VI/EN│                           │  → hypothetical caption│
        └────────┬─────────┘                            └────────────┬───────────┘
                 │  encoded in parallel by each text tower           │
   ┌────────┬────┴─────┬──────────┬──────────────┬──────────────────┐
   ▼        ▼          ▼          ▼              ▼                  ▼
 jina     CLIP      BEiT-3    (shared legs)   OCR text          ASR text
 (img)    (img)     (img)     (img)           (text↔text)       (text↔text)
   └────────┴──────────┴──────────┴──────────────┴──────────────────┘
                 │  each leg = one Prefetch in Qdrant
                 ▼
        ╔═══════════════════════╗
        ║  RRF fusion (weighted)║   ← Stage 1: bi-encoder ensemble, scans the whole corpus
        ╚═══════════╤═══════════╝
                    │  top 50..100 candidates
                    ▼
        ╔═══════════════════════╗
        ║ Qwen2.5-VL rerank     ║   ← Stage 2: cross-encoder, actually reads the frame
        ╚═══════════╤═══════════╝
                    │
          ┌─────────┼───────────┐
          ▼         ▼           ▼
        KIS       Q&A(VQA)    TRAKE (video select → align → refine)
                    │
              top-100 submitted
```

**Two invariants:**

1. **Never mix embeddings from different spaces** (no averaging CLIP with BEiT-3). Combine only at the
   **rank level**, with RRF.
2. **Each retrieval leg is queried through that model's own text tower.** Qwen2.5-VL is **not** a vector
   leg — it is generative (HyDE / rerank / VQA).

---

<a name="1-models"></a>
## 1. Models and their roles

| Model | Type | Dim | Role | Vietnamese queries |
|---|---|---|---|---|
| **jina-clip-v2** | image↔text dual encoder, multilingual | 1024 | **Primary** retrieval leg | Encode directly, **no translation** |
| **CLIP ViT-L-14** (laion2B) | dual encoder | 768 | Retrieval leg (reuses the old `.npy` files) | Translate and cache |
| **BEiT-3 large** | dual encoder (XLM-R tokenizer) | 1024 | Retrieval leg, signal diversity | Handles Vietnamese partly; try English too |
| **Qwen2.5-VL** (7B/72B) | **generative VLM** | — | HyDE · keyframe captioning · **rerank** · **VQA** | Native VI/EN |
| PhoWhisper / Whisper-v3 | ASR | — | ASR-text leg | — |
| VietOCR / PaddleOCR | OCR | — | OCR-text leg | — |
| (Embeddings shared by other teams) | dual encoder | * | Additional retrieval legs (§11) | Needs the matching text tower |

---

<a name="2-embeddings"></a>
## 2. Embedding generation

**Technique:** encode every keyframe with several image encoders and store the results side by side as
**named vectors** in Qdrant.

- **Input:** `Keyframes/<video_id>/*.jpg` plus metadata (source frame id, fps).
- **Output:** per keyframe, a `jina` (1024), `clip` (768) and `beit3` (1024) vector, all **L2
  normalized**.
- **Parameters:** GPU batches of 128–256 images; **cosine** distance; skip the intermediate `.npy` step
  and upsert directly, but **reuse** the old CLIP `.npy` files if the keyframe set has not changed.
- **Critical invariant:** `frame_id` stores the **source frame index inside the video**, not the
  keyframe ordinal, so TRAKE can map onto the scoring window `[s,e]` (under 10 frames).

**Example record after encoding** (conceptual, before upsert):

```json
{
  "idx": 152344,
  "video_id": "L01_V001",
  "frame_id": 505,               // source frame, this is what gets scored
  "keyframe_order": 87,          // keyframe ordinal within the video
  "fps": 25.0,
  "vectors": { "jina": [...1024], "clip": [...768], "beit3": [...1024] }
}
```

---

<a name="3-qdrant-schema"></a>
## 3. Qdrant — schema and configuration

**Technique:** one `keyframes` collection, one point per keyframe, vectors and payload together so that
**ANN search can filter**.

```python
# create_collection (parameter specification)
vectors_config = {
    "jina":    VectorParams(size=1024, distance=Distance.COSINE),
    "clip":    VectorParams(size=768,  distance=Distance.COSINE),
    "beit3":   VectorParams(size=1024, distance=Distance.COSINE),
    "caption": VectorParams(size=1024, distance=Distance.COSINE),  # Qwen caption embedded as a vector
}
hnsw_config       = HnswConfigDiff(m=16, ef_construct=200)
on_disk_payload   = True          # required for batch 2

# payload (per-frame metadata and text only; NO asr_text, NO caption as text)
payload = {
  "idx", "video_id", "frame_id", "keyframe_order", "fps",
  "frame_stamp", "objects", "detection", "ocr_text",
  "video_path", "video_url", "path"
}

# MANDATORY payload indexes (they unlock TRAKE and filtering)
create_payload_index("video_id",  KEYWORD)
create_payload_index("frame_id",  INTEGER)
create_payload_index("ocr_text",  TEXT)     # full text (per-frame OCR)
```

> **`caption`** is embedded by the text encoder into the **named vector `caption`**; the text itself is
> not stored in the payload.
> **`asr_text`** lives entirely in the `asr_segments` collection (§7), never on a keyframe. Only
> `ocr_text`, which is per-frame, stays in the payload.

**Why Qdrant beats FAISS here:** FAISS `IndexFlatIP` cannot filter on payload, so TRAKE would have to
rerank offsets by hand. Qdrant does **ANN plus a `video_id`/`frame_id` filter in the same call**.

---

<a name="4-ingestion"></a>
## 4. Ingestion

**Technique:** walk the keyframes → encode in batches → `upsert` in chunks → create payload indexes
**after** loading.

- Upsert chunks of ~256 points with `wait=false` for speed.
- **Idempotent on `idx`**, so it can be re-run when batch 2 arrives without duplicating anything.
- `ocr_text` is added **afterwards** with `set_payload` (no re-encoding of image vectors). `caption`
  becomes the named vector `caption`. ASR goes into its own `asr_segments` collection.
- Post-load check: `count(video_id=X)` must equal the real keyframe count of video X.

---

<a name="5-augmentation"></a>
## 5. Query augmentation

Goal: more recall without wrecking latency. Split into a **fast path (no LLM)** and a **quality path
(LLM)**.

### 5.1 Template ensembling (no LLM, on by default)

Wrap the query in several templates and **mean-pool the text embeddings into one vector**:

```
templates = [
  "{q}",
  "a video frame showing {q}",
  "a scene of {q}",
  "a photo of {q}",
]
q_vec = normalize(mean([encode(t.format(q)) for t in templates]))
```

One search, no extra latency, +1–3% recall.

### 5.2 Bilingual VI/EN (exploiting the multilingual leg)

```
q_vec_jina = mean(encode_jina(q_vi), encode_jina(translate_en(q_vi)))
```

### 5.3 HyDE (LLM — Qwen2.5-VL, the strongest option)

Instead of paraphrasing the question, generate a **caption describing the frame we are looking for** and
embed that. Image↔caption matches far better than image↔question.

**Sample prompt (KIS):**

```
You are an image captioning expert. For the search query below, write one English
sentence describing the VISUAL DETAILS of the best matching frame (objects, colours,
actions, setting). No explanation, return only the sentence.
Query: "{q}"
```

**Example:**

- Query: *"Find a video of a speaker in a red shirt talking at an outdoor press conference with lots of
  green trees behind them."*
- HyDE output: *"A male speaker in a red shirt standing at a podium giving a speech at an outdoor press
  conference, lush green trees in the background, microphones in front."*
- → embed that sentence with all three image encoders.

### 5.4 Entity extraction → filter branch

Pull out objects and proper nouns to use as an `ocr_text` filter or for reranking. From the query above:
`["red shirt","podium","trees","press conference"]`.

**Fusing the variants:** the fast path **mean-pools** (5.1 + 5.2); the quality path adds HyDE as its
**own leg** and fuses with RRF (§6). The LLM runs **once per query and is cached** — the competition
gives complete descriptions up front, so augmentation can be done offline.

---

<a name="6-rrf"></a>
## 6. Stage-1 ensemble — multi-leg RRF

**Technique:** every leg returns a ranked list; combine them with **weighted Reciprocal Rank Fusion**.

**Formula:**

```
score(d) = Σ_leg  w_leg · 1 / (k_rrf + rank_leg(d))          k_rrf = 60
```

RRF works on **ranks**, so it is immune to models using different score scales.

**Qdrant Query API (specification):**

```python
client.query_points(
  "keyframes",
  prefetch=[
    Prefetch(query=q_jina,  using="jina",  limit=200),
    Prefetch(query=q_clip,  using="clip",  limit=200),
    Prefetch(query=q_beit3, using="beit3", limit=200),
    Prefetch(query=q_hyde_jina, using="jina", limit=200),   # HyDE leg
    Prefetch(query=ocr_kw, ... )                            # OCR leg (text)
  ],
  query=FusionQuery(fusion=Fusion.RRF),
  limit=100, with_payload=True,
)
```

This replaces the hand-written `RRF_ranking()` at `search_controller.py:347`.

**Starting weights (tune them on the dev set, §12):**

```
beit3 1.0 · jina 1.0 · clip 0.7 · HyDE 0.8 · OCR 0.6 · ASR 0.5
```

> Correlation note: jina and CLIP are both CLIP-family, so lower the CLIP weight to avoid
> double-counting the same signal.

---

<a name="7-rerank"></a>
## 7. Stage-2 ensemble — Qwen2.5-VL cross-encoder rerank

**Technique:** feed the **actual keyframe image plus the query** to Qwen2.5-VL and let it score the
match. The model "reads" the frame content and fixes what cosine similarity habitually gets wrong:
counting, spatial relations, text.

- **Input:** the top-K of stage 1 (K = 30–50; running it over the whole corpus is far too expensive).
- **Output:** a 0–100 score per frame, used to re-sort.

**Sample prompt (rerank):**

```
You are judging a video retrieval result. Does the image below match the description?
Description: "{q}"
Score the match from 0 to 100 (return only the number).
```

**Example:** query "speaker in a red shirt at an outdoor press conference". Stage 1 returns an
**indoor** red-shirt frame at rank 3 → Qwen scores it 40 and it drops; the correct outdoor frame at rank
8 scores 95 and moves to rank 1. This is exactly where R@1 is saved.

**Batching:** send several images per prompt (as a grid) to cut the number of calls, or score in batches
of 5–10 images.

---

<a name="8-ocr"></a>
## 8. OCR leg

**Technique:** extract on-screen text offline → store in the payload → use it in two ways.

- **Pipeline:** detection (PaddleOCR/DB) → recognition with **VietOCR / multilingual PaddleOCR** (mind
  the Vietnamese diacritics) → store `ocr_text` plus confidence.
- **Two uses:**
  1. **Filter/rerank** when the query contains a quoted string, a proper noun or a score line → match
     against `ocr_text` (full-text index).
  2. **A text↔text leg**: embed `ocr_text` with the text encoder and feed it into RRF.
- **Especially valuable for Q&A**, where answers are literal: names, numbers, scores.

**Example:** Q&A *"Which team won according to the scoreboard?"* → OCR read "3 - 1  TEAM A" in the frame
→ answer it directly.

---

<a name="9-audio"></a>
## 9. Audio leg — ASR and sound events

**Technique:** exploit speech and audio, a signal the organizer-provided features do **not** contain.

- **ASR:** **PhoWhisper** (Vietnamese) or Whisper-v3 → transcript **with timestamps** → stored in the
  **`asr_segments`** collection (§7, from `metadata_asr/<video_id>.json`); embed `text` per segment.
  Only at fusion time is it **projected onto frames** via `frame_start`/`frame_end`.
- **Use:** search by *what is being said* (an MC announcing, a speaker talking). Extremely strong for
  news and event footage, and for Q&A when the answer is spoken rather than shown.
- **Sound events (advanced):** CLAP/PANNs tagging applause, whistles, cheering → **time anchors for
  TRAKE**.

**Example:** query "the moment the referee blows the starting whistle" → the audio event "whistle" at
t=12.3s → frame ≈ 12.3×fps → an anchor for TRAKE event 1.

**Invariant:** OCR is **per frame**, ASR and audio are **per time span**. Everything must be joined back
to `(video_id, frame_id / time window)` before RRF can mix it.

---

<a name="10-pipelines"></a>
## 10. Pipeline per query type

<a name="101-kis"></a>
### 10.1 Textual KIS — `<video_id>, <frame_id>`

1. Augment (templates + VI/EN + HyDE).
2. Multi-leg RRF → top-100.
3. Qwen rerank on the top-30.
4. **Deduplicate keyframes** with `query_points_groups(group_by="video_id", group_size=3)` so a single
   scene cannot occupy the whole top-k → improves R@5/R@20.
5. Submit all 100.

**Scoring example:** ground truth `L01_V001 [500,510]`. Submitting `L01_V001,505` gives R-Score = 1.

<a name="102-qa"></a>
### 10.2 Q&A — `<video_id>, <frame_id>, <answer>`

Retrieval works exactly as for KIS to **locate the moment**, then **VQA with Qwen2.5-VL** produces the
`answer`.

**VQA prompt:**

```
Look at the frame and answer the question BRIEFLY (in Vietnamese, or as a number).
Question: "{question}"
```

**Example:** *"How many people came on stage to receive the grand prize?"* → locate the award ceremony
frame → Qwen counts → answer = "5". Submit `L?_V?, 3450, 5`.

> Without the VQA step, Q&A **always scores zero**, even when the frame is right.

<a name="103-trake"></a>
### 10.3 TRAKE — `<video_id>, <frame_id_1>, ..., <frame_id_N>`

**Scoring invariant:** the wrong video scores **zero**; with the right video, the score is the fraction
of events landing inside their window `[s_j,e_j]` (under 10 frames).

**Tier 1 — pick one video:**

- Encode the N events (each augmented separately).
- For each event, run `query_points_groups(group_by="video_id")`.
- Aggregate per video with **monotonic DP** (chronological order enforced).

**DP alignment (specification):**

```
# sim[j][t] = similarity of event j to the t-th keyframe (in time order) of the video
# Choose t_1 < t_2 < ... < t_N maximizing the total similarity
dp[j][t] = sim[j][t] + max_{t' < t} dp[j-1][t']
best_score(video) = max_t dp[N][t]
# backtrack → (t_1..t_N)
```

Rank videos by `best_score` and take the top candidates.

**Tier 2 — align each event inside the chosen video:**

```python
prev = -1
for j, ev_vec in enumerate(event_vecs):
    hit = query_points("keyframes", query=ev_vec, using="jina",
        query_filter=Filter(must=[
            FieldCondition("video_id", MatchValue(vid)),
            FieldCondition("frame_id", Range(gt=prev)),   # enforce ordering
        ]), limit=5).points[0]
    frames[j] = hit.payload["frame_id"]; prev = frames[j]
```

**Tier 3 — refinement to hit the sub-10-frame window (MANDATORY):**

Keyframes are sparse (one per shot, or one per second), so the answer window of `<10 source frames`
almost never contains a keyframe — tiers 1 and 2 only locate events *coarsely*. Tier 3 scans at
**source-frame resolution** to pick the right semantic frame. This step decides whether TRAKE points are
won in full.

**Input:** the chosen video (`video_path`), its `fps`, and for each event j: the coarse `frame_id` `f_j`
from tier 2, the event text vector `ev_vec_j`, and optionally the ASR span
`[frame_start,frame_end]` of the event.

**Algorithm (specification):**

```
R = 15                                  # scan radius around the coarse frame (at ~25fps → ±0.6s)
STRIDE = 1                              # 1 = every frame; 2-3 if you need speed
for j, (f_j, ev_vec_j) in enumerate(events):
    lo = max(prev_fine + 1, f_j - R)    # prev_fine: refined frame of event j-1 → enforces ordering
    hi = f_j + R
    frames = decode_native(video_path, lo, hi, STRIDE)   # read SOURCE frames (OpenCV/decord)
    embs   = encode_image(frames)                        # jina (primary leg); optionally + CLIP
    scores = embs @ ev_vec_j                             # cosine, already normalized
    # (optional) bonus if the frame falls inside the event's ASR span
    # (optional) rerank the top-3 with Qwen2.5-VL to pick the right semantic moment
    t_star     = argmax(scores)
    fine[j]    = lo + t_star * STRIDE                     # the source frame to SUBMIT
    prev_fine  = fine[j]
```

**Constraints and notes:**

- `lo = max(prev_fine+1, ...)` preserves **chronological order** between events (event j after j-1).
- Decode with **decord** (fast, seeks by index) or OpenCV `set(CAP_PROP_POS_FRAMES, lo)`; read only
  `[lo,hi]`, never the whole video.
- The **source frame** is what the scoring expects — with a window `[s_j,e_j] < 10` frames, being off by
  one or two frames loses that event.
- **Optimizing R@k:** besides `fine[j]`, also submit the variants `fine[j] ± 1..2` (the top-2/3 by
  `scores`) to raise the chance of landing inside `[s_j,e_j]`.
- **Semantics versus visual intensity:** a semantic moment (say "the take-off foot has just fully left
  the ground") often looks nearly identical in two adjacent frames, so **rerank the top-3 with
  Qwen2.5-VL** using a prompt that describes *the exact moment*, rather than trusting the frame that
  merely matches the general caption best.

**Qwen prompt for choosing the semantic keyframe (tier 3):**

```
Among the following images (consecutive in time), which one is EXACTLY the moment:
"{event j description, e.g. the take-off foot has just fully left the ground}"?
Return only the image number.
```

**Example (high jump, event 2 "clears the bar", ground truth `[145,155]`):**

- Tier 2 picks the coarse keyframe `f_2 = 150` (the nearest keyframe).
- Tier 3 decodes `[135,165]` at native fps → cosine peaks at 149 and 151, nearly tied.
- Qwen rerank picks 150 (hips highest relative to the bar) → submit `150` (plus the variants 149 and
  151) → inside `[145,155]`.

**Cost:** each event decodes about `2R/STRIDE` frames (≈30 images) and encodes them — a few hundred
milliseconds per event on a GPU. It runs only for the **one chosen video**, not the whole corpus, so it
is affordable.

**Optimizing R@k:** do not submit a single argmax combination. **Generate the Cartesian product of the
top-k candidates per event** and rank them — see §10.3.1.

**Example (high jump, 4 events):** ground truth `L10_V010` with windows `[95,105]`, `[145,155]`,
`[195,205]`, `[245,255]`.

- Tier 1 picks `L10_V010` correctly.
- Tier 2 locates coarsely: nearest keyframes `100,150,200,250`.
- Tier 3 refines on source frames → `101,150,203,251` → 4/4 → R-Score = 1.0.

#### 10.3.1 Submission strategy (Cartesian) — optimizing R@k *(a free improvement)*

TRAKE scoring takes `R@k = max` over `k∈{1,5,20,50,100}` and averages them, and **up to 100 combinations
may be submitted**. Submitting one argmax combination wastes that. Instead: take the **top-k candidate
frames with probabilities** per event, generate the **Cartesian product**, sort by the product of the
probabilities, and submit the first 100.

**Example (the same high jump question, `L10_V010`, N=4, windows `[95,105]`, `[145,155]`, `[195,205]`,
`[245,255]`):**

Top-3 candidates per event (bold = frame inside the correct window):

| Event | Cand. 1 | Cand. 2 | Cand. 3 |
|---|---|---|---|
| E1 Take-off | **101** (0.50) | 88 (0.30) | 112 (0.20) |
| E2 Over the bar | 160 (0.45) | **150** (0.35) | 141 (0.20) |
| E3 Landing | **203** (0.60) | 190 (0.25) | 215 (0.15) |
| E4 Standing up | **251** (0.55) | 240 (0.30) | 262 (0.15) |

Note E2: the model's **top-1 is wrong** (160 sits outside `[145,155]`); the correct frame is second.

**Naive approach (submit the argmax of each dimension):** `(101,160,203,251)` → 3/4 → R-Score 0.75. It is
the only submission, so `R@1 = … = R@100 = 0.75` → **Final Score = 0.75**.

**Cartesian approach:** generate `3⁴ = 81` combinations sorted by the product of probabilities:

| Rank | Combination | Product | R-Score |
|---|---|---|---|
| 1 | 101, 160, 203, 251 | 0.0743 | 0.75 |
| **2** | **101, 150, 203, 251** | **0.0578** | **1.00** |
| 3 | 88, 160, 203, 251 | 0.0446 | 0.50 |
| 4 | 101, 160, 203, 240 | 0.0405 | 0.50 |
| 5 | 88, 150, 203, 251 | 0.0347 | 0.75 |

The perfect combination lands at **rank 2** (one dimension away from rank 1), so `R@1 = 0.75` and
`R@5 = R@20 = R@50 = R@100 = 1.00` → **Final Score = (0.75+1+1+1+1)/5 = 0.95**. That is **+0.20** with
**the same model and the same candidate set**, no extra training.

**Why it can never lose:** the rank-1 Cartesian combination **is** the naive answer, so `R@1` is always
identical and `R@5` upwards can only improve. A pure gain with no trade-off.

> The quantity to optimize changes: it is no longer **top-1 accuracy per event** but **recall@k per
> event** (the correct frame being *somewhere* in the candidate set). A model that is poor at top-1 but
> good at recall@3 still scores well.

```python
from itertools import product
from math import prod
combos = sorted(product(*cands), key=lambda c: -prod(p[i][f] for i, f in enumerate(c)))
submit(video_id, combos[:100])
```

**Slot budget by N** (at most 100 combinations in total):

| N | Candidates per event | Combinations |
|---|---|---|
| 2 | 10 | 100 |
| 3 | 4 | 64 |
| 4 | 3 | 81 |
| 5 | 3,3,2,2,2 | 72 |
| 6 | 2 | 64 |
| 7+ | 2 for the hardest event, 1 for the rest | ≤ 64 |

When N is odd or does not divide evenly, **give the extra candidates to the event with the flattest
probability distribution** (low top-1 → give it 3; an event at 0.95 → give it 1). Be greedy on the
marginal recall gain from each doubling of the budget.

**Three traps (all must be handled):**

1. **Candidate spacing (temporal NMS).** The answer window is under 10 frames, so if E1's three
   candidates are 101/103/105 they all sit in one window — three slots buying a single bet. **Enforce a
   minimum spacing of ~15 frames** between candidates of the same event.
2. **Chronological constraint.** The event sequence is monotonically increasing (take-off before
   landing). Discard every non-increasing combination — typically **30–50%** of them, freeing slots for a
   fourth candidate or a backup video.
3. **Do not spend all 100 slots on one video when you are not sure.** With `P(video1)≈0.65`, giving 81
   slots to video 1 (3 candidates per event) and 16 to video 2 (2 per event) has a higher expected value
   than betting everything. Rough threshold: whenever top-1 video confidence is **below ~0.8**, always
   reserve slots for the second video. **Calibrate this threshold on the dev set** (§12) — it depends on
   how well your retrieval calibrates probabilities.

---

<a name="11-shared-embeddings"></a>
## 11. Embeddings shared by other teams

**Yes**, each shared set becomes one more named vector plus one more RRF leg. **Four make-or-break
conditions:**

1. **The model identity must come with it** so the right text tower can be loaded — image vectors of an
   unknown model are **useless** for text→image search.
2. **Join on `(video_id, frame_id)`, never on array position** — another team's keyframe extraction will
   not line up with yours.
3. **Pick diverse models** (CLIP + SigLIP + BEiT-3 + …) and avoid adding correlated ones; the sweet spot
   is 3–4 legs.
4. **Validate each leg on the dev set** before adding it; weight by score and drop any leg that hurts.

> ⚠️ **Check the AIC 2026 rules**: confirm that features or models shared by another team are allowed.

---

<a name="12-dev-set"></a>
## 12. Dev set and weight selection

The foundation that keeps every ensemble, OCR and audio addition from being pure noise.

- **Build:** 50–100 self-written queries against batch 1 data, with self-assigned ground truth
  `(video, [s,e])`, or reuse the sample questions.
- **Measure:** R@{1,5,20,50,100} and the Final Score (the average) **per individual leg** and then **for
  the combination**.
- **Choose RRF weights:** a small grid or coordinate search on the dev set.
- **Rule:** keep a leg only if adding it **raises** the Final Score (ablation).

---

<a name="13-latency"></a>
## 13. Latency optimization ("the query does not come back fast")

- Drop translation on the multilingual leg; **cache** it on the CLIP leg.
- **Keep models warm on the GPU**; remove the per-request `.to(device)` (`search_model.py:125`).
- Do augmentation and HyDE **offline with caching** (the competition provides full descriptions).
- Encode the N TRAKE events **once** and reuse them across all three tiers.
- Rerank with Qwen only on the top 30–50, never the whole corpus.
- Tune HNSW `ef` to balance recall against speed; use `on_disk` for batch 2.
- **Target budget:** stage 1 under 300ms, Qwen rerank 1–3s (only when high precision is required).

---

<a name="14-security"></a>
## 14. Security and configuration cleanup (do this during the migration)

- 🔴 **Rotate immediately**: the Gemini API key (`app/utils/helpers.py:33`) and the Mongo URI containing
  a username and password (`app/config.py:9-10`) — move both into `.env`.
- 🔴 Remove the hard-coded checkpoint path `C:\Users\PC\...` (`app/models/search_model.py:19`) and read it
  from config.
- If Mongo is dropped entirely: move the object/OCR filters into the Qdrant payload and delete
  `fuzzy_search`.

---

<a name="15-hybrid"></a>
## 15. Hybrid Mongo + Qdrant architecture (orchestrator)

The option that keeps **OCR/ASR in MongoDB Atlas** (for **real fuzzy `maxEdits`**, which Qdrant lacks)
and **embeddings in Qdrant**. The trade-off is two stores, so results must be joined and the calls made
carefully. This section specifies how to do that **without sacrificing either speed or accuracy**.

### 15.1 Responsibilities and the join key

| Store | Holds | Queried with |
|---|---|---|
| **Qdrant** | vectors `jina/clip/beit3` plus a minimal payload | dense ANN (+ sparse char n-grams if available) |
| **Mongo Atlas** | `ocr_text`, `asr_segments`, `objects` | `$search` **fuzzy** (`maxEdits:1, prefixLength:2`) |

- **Shared join key: `idx` (globally unique).** Results from both sides are reduced to lists of `idx`
  before fusion, so only `(idx, score)` pairs travel — **never** vectors.
- **OCR** matches produce keyframe `idx` values directly.
- **ASR** matches a segment and is then **projected onto frames**: the `idx` of the keyframe whose
  `frame_id ∈ [frame_start,frame_end]` (with no keyframe, the representative frame is
  `round((t_start+t_end)/2 · fps)`). See §7 and §9.

### 15.2 Orchestrator diagram (CALLED IN PARALLEL)

```
                          QUERY (VI)  ── route classification ──┐
                              │                            │ (KIS / Q&A / TRAKE / text-heavy)
        ┌─────────────────────┴─────────────────────┐     │
        ▼ (async, simultaneous)                      ▼     │
 ┌──────────────┐                          ┌───────────────────────┐
 │   QDRANT      │                          │   MONGO ATLAS ($search)│
 │ dense ANN     │                          │  ocr_fuzzy  asr_fuzzy  │
 │ limit=200     │                          │  limit=200  limit=200  │
 └──────┬───────┘                          └───────────┬───────────┘
        │ ranked idx (dense)                            │ ranked idx (ocr), (asr→frame)
        └───────────────┬───────────────────────────────┘
                        ▼
             ┌─────────────────────────┐
             │  ROUTE-AWARE RRF (§15.4) │   ← fuse on idx, weights depend on the query type
             └───────────┬─────────────┘
                         │ top-K idx
                         ▼
      batch  Mongo.find({idx:{$in:[...]}})  +  Qdrant.retrieve(ids)   (one round trip each)
                         │
                         ▼
      Qwen2.5-VL rerank/verify the top-K (re-reads the text in the image)  →  top-100 submitted

  Latency ≈ max(t_qdrant, t_mongo)  (NOT the sum, because they run in parallel)
```

### 15.3 Route classifier (cheap, decides the weights)

Classify the query first, with rules or a small LLM:

| Route | Signals | Intent |
|---|---|---|
| `visual` | a pure scene or action description | dense dominates |
| `text_in_scene` | quoted strings, proper nouns, numbers or scores | boost OCR fuzzy |
| `spoken` | "who said…", "was announced…", dialogue | boost ASR |
| `trake` | a sequence of two or more moments | dense + DP (§10.3), OCR/ASR as anchors |

### 15.4 Route-aware RRF formula

Fuse on `idx`; each source contributes the reciprocal of its rank, weighted by route:

```
score(idx) =  w_dense · 1/(k + rank_qdrant(idx))
            + w_ocr   · 1/(k + rank_ocr(idx))
            + w_asr   · 1/(k + rank_asr(idx))
            + w_obj   · 1/(k + rank_obj(idx))
        k = 60 ;  rank = +∞ when idx is absent from that source (the term becomes 0)
```

**Starting weights (tune on the dev set, §12):**

| Route | w_dense | w_ocr | w_asr | w_obj |
|---|---|---|---|---|
| `visual`        | 1.0 | 0.3 | 0.2 | 0.3 |
| `text_in_scene` | 0.6 | **1.0** | 0.3 | 0.4 |
| `spoken`        | 0.6 | 0.3 | **1.0** | 0.2 |
| `trake`         | 1.0 | 0.4 (anchor) | 0.4 (anchor) | 0.3 |

> On the `trake` route, ASR and OCR mostly act as **temporal constraints** for the DP, not just as extra
> score.

### 15.5 Latency optimization (mandatory)

1. **Call Qdrant and Mongo IN PARALLEL** (asyncio or threads) → latency is the `max`, not the sum.
2. **Run Mongo Atlas LOCALLY in Docker** (`mongodb/mongodb-atlas-local`, which ships `mongot`) to remove
   network RTT.
   ⚠️ Mongo Community does **not** provide `$search` fuzzy — you need the `atlas-local` image or Atlas
   cloud.
3. **One round trip per store** to fetch payloads: `find({idx:{$in:[...]}})` and `retrieve(ids)` after
   fusion.
4. `limit` around 200 per source; a unique index on `idx` plus Atlas Search indexes on
   `ocr_text`/`asr_text`.
5. **Cache** translations and augmentations; keep both clients warm (connection pooling).

### 15.6 Accuracy optimization

- **Route-aware RRF** (§15.4) with weights learned from the dev set.
- **Fuzzy string matching**: combine Atlas `maxEdits` with **sparse char-3gram** vectors in Qdrant (§8)
  to compensate for OCR errors and dropped characters.
- **Qwen2.5-VL verification of the top-K**: it re-reads the text in the original image, so the result no
  longer depends on how good the indexed OCR was.

### 15.7 Failure modes to avoid

- ❌ **No cross-filtering** (pushing a large `idx` set from Mongo into Qdrant as a filter) — filtering by
  a huge id list is very slow in Qdrant. Always **parallel + RRF**.
- **Fallback**: if one store errors or times out, return the other store's results rather than failing
  the whole query.
- **`idx` consistency**: the Qdrant and Mongo ingests must come from **the same metadata source**
  (§METADATA_SPEC) so that `idx` matches exactly.

### 15.8 Deployment (suggested docker-compose)

```
services:
  qdrant:       image: qdrant/qdrant                 # 6333
  mongo-atlas:  image: mongodb/mongodb-atlas-local   # 27017, provides $search fuzzy
```

The backend talks to both over localhost, so internal latency is a few milliseconds.

---

<a name="16-roadmap"></a>
## 16. Implementation order (highest ROI first)

1. Stand up Qdrant in Docker and freeze the schema (§3).
2. Ingest the three image legs (jina/CLIP/BEiT-3) (§2, §4).
3. KIS search with Qdrant RRF (§6, §10.1) — replacing FAISS.
4. **Three-tier TRAKE with DP alignment** (§10.3) — the priority for points.
5. Qwen2.5-VL rerank (§7) and VQA for Q&A (§10.2).
6. OCR leg (§8) — Mongo Atlas fuzzy plus sparse char-3gram.
7. Audio/ASR leg (§9).
8. **Hybrid Mongo + Qdrant orchestrator with parallel calls and route-aware RRF** (§15).
9. Fold in embeddings shared by other teams (§11).
10. Dev set and weight tuning (§12) — run this in parallel from step 3 onwards.
11. Latency optimization and security cleanup (§13, §14).

---

*Note: the specific model choices (jina-clip-v2, CLIP ViT-L-14, BEiT-3 large, Qwen2.5-VL 7B/72B,
PhoWhisper) are a starting proposal; swap or upgrade them depending on your GPU and dev-set results.*

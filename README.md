# AIC 2026 — Multimodal Video Retrieval System

Retrieval system for the [AI Challenge HCMC](https://aichallenge.hochiminhcity.gov.vn/) 2026 preliminary
round. It searches a keyframe corpus by free-text description (visual embeddings), by on-screen text
(OCR), by speech (ASR), and by temporal event sequences (TRAKE).

This README covers **running the whole stack on Linux with Docker**, **getting the models**, and
**monitoring the backends**. For everything else see [Documentation map](#12-documentation-map).

---

## 1. What runs where

Five containers, started by a single `docker compose up -d`:

| Service | Image | Port | Role |
|---|---|---|---|
| `frontend` | `aic2026-frontend:local` | 8088 | React/Vite UI behind nginx |
| `backend-api` | `aic2026-backend:local` | 5000 | Flask + gunicorn; embeddings, search, TRAKE |
| `frame-server` | `aic2026-frame-server:local` | 8081 | Express, serves keyframe images |
| `qdrant` | `qdrant/qdrant:latest` | 6333 / 6334 | Vector store (`beit3`, `jina`, `pe`) |
| `mongodb` | `mongodb/mongodb-atlas-local:8.0.25` | 27017 | OCR/ASR metadata + Atlas Search |

Request path for a text query:

```
browser :8088 ──> backend-api :5000 ──> encode text on GPU
                       │
                       ├──> qdrant :6333   (vector search, visual)
                       └──> mongodb :27017 (Atlas Search, OCR/ASR)
                                 │
browser <── frame-server :8081 <─┘ keyframe images
```

---

## 2. Prerequisites

Docker Engine with the Compose v2 plugin. Docker Desktop is **not** needed on Linux.

```bash
docker --version && docker compose version && docker info | grep 'Server Version'
```

If Docker is missing:

```bash
curl -fsSL https://get.docker.com | sh
```

```bash
sudo usermod -aG docker "$USER"
```

Log out and back in for the group change to apply.

### GPU (strongly recommended)

Visual search on CPU takes **13 minutes 32 seconds** per query; on an RTX 4060 Laptop (8GB) the same
query takes **~17 seconds** on the first call (model load into VRAM) and **0.07 seconds** afterwards.

Install the NVIDIA Container Toolkit:

```bash
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
```

```bash
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
```

```bash
sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
```

```bash
sudo nvidia-ctk runtime configure --runtime=docker && sudo systemctl restart docker
```

Verify the runtime reaches the GPU:

```bash
docker run --rm --gpus all nvidia/cuda:12.0.0-base-ubuntu20.04 nvidia-smi
```

### Hardware used for the numbers in this document

Ubuntu (kernel 6.8), 23GB RAM, RTX 4060 Laptop 8GB, driver 580.x, NVMe SSD.

---

## 3. Data layout

The heavy data (17GB of keyframes, 5GB of Qdrant storage) lives **outside** the repository.
`runtime-data/` holds only symlinks pointing at it, so `git clean` can never destroy the corpus.

```text
AIC-2026/                     <- DATA_ROOT
├── keyframes/                <- 873 folders: L21_V001/, L21_V002/, ...
├── metadata/                 <- one JSON per video
├── qdrant_storage/           <- collections beit3, jina, pe
└── aic2026/                  <- this repository
    └── runtime-data/
        ├── keyframes       -> ../../keyframes
        ├── qdrant_storage  -> ../../qdrant_storage
        ├── metadata        -> ../../metadata
        ├── checkpoints/      <- BEiT-3 .pth goes here
        └── videos/           <- empty unless you run TRAKE tier 3
```

OCR/ASR documents are **not** in the repository; they live in the Docker volume
`aic2026_mongodb_data_v2` and survive `docker compose down`.

---

## 4. Setup

```bash
./setup-linux.sh
```

The script is idempotent — run it as often as you like. It:

1. Checks Docker, Compose, and whether a usable NVIDIA GPU is present.
2. Creates the `runtime-data/*` symlinks from `DATA_ROOT`.
3. Creates the `aic2026_mongodb_{data,config,mongot}_v2` volumes if absent.
4. Repairs `compose.yaml` (MongoDB tag `8.0.25`, `_v2` volume names) and appends the `search-cuda`
   stage to `backendAIC2025/Dockerfile` if either has been reverted.
5. Generates `.env` — only when missing — with `BACKEND_BUILD_TARGET=search-cuda`,
   `SEARCH_DEVICE=cuda` and `COMPOSE_FILE=compose.yaml:compose.gpu.yaml`.
6. Validates the result with `docker compose config`.

Options:

```bash
GPU=0 ./setup-linux.sh
```

```bash
DATA_ROOT=/mnt/ssd/aic ./setup-linux.sh
```

Then build and start:

```bash
docker compose up -d --build
```

The first build takes roughly 40 minutes and produces a 9.78GB backend image — almost all of it is
`torch 2.6.0+cu124` plus the search dependencies. Later starts need no `--build`.

---

## 5. Models

Three encoders are selectable per query through the `model` field. They share one slot in VRAM:
`SEARCH_MODEL_CACHE_SIZE=1` means switching models evicts the current one and reloads the other.

| Model | Where the weights come from | Size | Vector dim | Status |
|---|---|---|---|---|
| `beit3` | BEiT-3 checkpoint file you place on disk | 1.35GB | 1024 | works |
| `jina` | `jinaai/jina-embeddings-v5-omni-small`, auto-downloaded | ~4GB | 1024 | works |
| `pe` | `timm/PE-Core-bigG-14-448`, auto-downloaded | 9.68GB | 1280 | needs fp16 patch, see below |

All Hugging Face downloads land in the named volume `aic2026_huggingface_cache`
(mounted at `/root/.cache/huggingface`), so they survive container recreation and are downloaded once.

### 5.1 BEiT-3

The Qdrant `beit3` collection was built with `beit3_large_patch16_224.pth`. Query embeddings must come
from the same checkpoint, otherwise scores are meaningless. Get the file from the team's
[Google Drive folder](https://drive.google.com/drive/folders/1lLyvVkyQcw4orZvFsQk0bLmtEFiNpBCF?usp=drive_link)
and drop it in:

```bash
cp /path/to/beit3_large_patch16_224.pth runtime-data/checkpoints/
```

Point `.env` at it — the filename must match exactly:

```text
BEIT3_CHECKPOINT_PATH=/models/beit3_large_patch16_224.pth
```

```bash
docker compose up -d backend-api
```

The tokenizer (`beit3.spm`) is already committed under `backendAIC2025/search_engine/beit3/`, so
nothing else is needed. On load, the 224px position embeddings are interpolated to the 384px retrieval
model; a first query takes ~12 seconds, later ones 0.06 seconds, and the model occupies ~3.3GB VRAM.

### 5.2 Jina

Nothing to do. On the first `model=jina` query the weights are pulled from Hugging Face into the cache
volume (~4GB, a few minutes on a decent connection). VRAM footprint is ~2.9GB.

### 5.3 PE (Perception Encoder)

`open_clip` resolves the name in `PE_MODEL_NAME` (default `hf-hub:timm/PE-Core-bigG-14-448`) and
downloads `open_clip_model.safetensors` — **9.68GB**. To fetch it ahead of time instead of during the
first query:

```bash
docker compose exec backend-api python -c "import open_clip; open_clip.create_model_and_transforms('hf-hub:timm/PE-Core-bigG-14-448')"
```

The repository is public, so no token is required. `open_clip.get_tokenizer()` pulls another ~5MB of
tokenizer files on the first real query.

**VRAM warning.** The checkpoint is fp32: ~9.7GB of weights against 8.0GB of VRAM on a 4060, so
loading it on the GPU as shipped will OOM. Options: run PE on CPU, or pass `precision="fp16"` to
`open_clip.create_model_and_transforms` in `search_engine/model.py` to halve it to ~4.9GB. Loading also
peaks around 10GB of host RAM.

### 5.4 Hugging Face token (optional)

Downloads work unauthenticated; a token only raises rate limits and download speed. Create a **read**
token at `huggingface.co/settings/tokens`, then either add it to `.env` (Compose passes every variable
in that file into the container):

```text
HF_TOKEN=hf_xxxxxxxxxxxxxxxxxxxx
```

or log in inside the container, which stores the token in the cache volume so it survives recreation:

```bash
docker compose exec -it backend-api hf auth login
```

```bash
docker compose exec -T backend-api hf auth whoami
```

`HF_TOKEN` takes precedence over the stored token file. Never commit a token — `.env` is gitignored
and should stay `chmod 600`.

---

## 6. Verifying the install

```bash
docker compose ps
```

All five services should report `healthy` (Qdrant ships no healthcheck and just reports `Up`).

```bash
curl -s localhost:5000/health/app
```

```bash
curl -s localhost:5000/search/health
```

```bash
curl -s localhost:6333/collections/beit3 | python3 -m json.tool | head -20
```

Expect `status: green` and 317,961 indexed points.

```bash
curl -s -o /dev/null -w '%{http_code}\n' localhost:8081/Keyframes/L21_V001/000000.webp
```

Is the GPU actually visible inside the container?

```bash
docker exec aic2026-backend-api-1 python -c "import torch;print(torch.__version__, torch.cuda.is_available())"
```

End-to-end visual search:

```bash
time curl -s -X POST localhost:5000/search/collection -H 'Content-Type: application/json' -d '{"query":"a man riding a motorbike on the street","model":"jina","top_k":5}'
```

OCR and ASR search. The corpus is Vietnamese, so these two examples deliberately use Vietnamese
queries ("thời sự" = current affairs, "kinh tế" = economy):

```bash
curl -s -X POST localhost:5000/search/ocr -H 'Content-Type: application/json' -d '{"query":"thời sự","top_k":5}'
```

```bash
curl -s -X POST localhost:5000/search/asr -H 'Content-Type: application/json' -d '{"query":"kinh tế","top_k":5}'
```

Document counts (317,961 OCR / 25,168 ASR):

```bash
docker exec aic2026-mongodb-1 mongosh -u aicadmin -p "$(grep ^MONGO_ROOT_PASSWORD .env | cut -d= -f2)" --authenticationDatabase admin --quiet --eval 'db=db.getSiblingDB("aic2026");db.getCollectionNames().forEach(c=>print(c,db[c].countDocuments()))'
```

Then open <http://localhost:8088>.

---

## 7. Tracking the backends

### 7.1 Request logs with timings

The `search-cuda` stage runs gunicorn with a custom access log format, so every request records its
duration:

```text
172.18.0.1 "POST /search/collection HTTP/1.1" 200 1121B 18.993776s
```

Follow every service at once, each line prefixed with its service name:

```bash
docker compose logs -f --since 10m
```

Backend only, without the healthcheck line that fires every 15 seconds:

```bash
docker compose logs -f backend-api | grep -v 'health/app'
```

List requests slower than one second:

```bash
docker compose logs backend-api | grep -oE '"[A-Z]+ [^"]+" [0-9]+ [0-9]+B [0-9]+\.[0-9]+s' | awk '$NF+0 > 1'
```

### 7.2 Container health and resources

```bash
docker compose ps
```

```bash
docker stats
```

Typical idle usage: backend ~3GB RSS, Qdrant ~2.3GB, MongoDB ~880MB, frame-server ~56MB,
frontend ~14MB.

```bash
docker inspect --format '{{json .State.Health}}' aic2026-backend-api-1 | python3 -m json.tool
```

### 7.3 GPU

```bash
nvidia-smi -l 2
```

Expect ~2.9GB of VRAM with `jina` resident and ~3.3GB with `beit3`. If VRAM stays at 0 while queries
run, the backend fell back to CPU — check `BACKEND_BUILD_TARGET` and `SEARCH_DEVICE`.

### 7.4 Qdrant

```bash
curl -s localhost:6333/collections/beit3 | python3 -m json.tool
```

Watch `status` (`green` = ready, `yellow` = optimizing, `grey` = idle after restore) and
`indexed_vectors_count`. Prometheus metrics are exposed too:

```bash
curl -s localhost:6333/metrics | grep -E 'collection|rest_responses_duration'
```

### 7.5 MongoDB

Turn on the profiler for anything slower than 100ms:

```bash
docker exec aic2026-mongodb-1 mongosh -u aicadmin -p aic2026_local_password --authenticationDatabase admin --quiet --eval 'db=db.getSiblingDB("aic2026");db.setProfilingLevel(1,{slowms:100});print("profiling on")'
```

Read the most recent slow operations:

```bash
docker exec aic2026-mongodb-1 mongosh -u aicadmin -p aic2026_local_password --authenticationDatabase admin --quiet --eval 'db=db.getSiblingDB("aic2026");db.system.profile.find().sort({ts:-1}).limit(5).forEach(d=>print(d.ts,d.millis+"ms",JSON.stringify(d.command).slice(0,120)))'
```

Check that the Atlas Search indexes are actually queryable:

```bash
docker exec aic2026-mongodb-1 mongosh -u aicadmin -p aic2026_local_password --authenticationDatabase admin --quiet --eval 'db=db.getSiblingDB("aic2026");db.ocr_metadata.getSearchIndexes().forEach(i=>print(i.name,i.status,i.queryable))'
```

### 7.6 Known log noise

`search_engine/model.py` prints the raw embedding tensor on every Jina text encode. It is harmless but
floods the log; delete that `print(output)` if you want clean output.

---

## 8. Day-to-day operation

```bash
docker compose up -d
```

```bash
docker compose down
```

```bash
docker compose logs -f backend-api
```

Rebuild after changing backend code:

```bash
docker compose up -d --build backend-api
```

Never run `docker compose down -v` — it deletes the MongoDB volumes holding the OCR/ASR corpus. Never
delete `qdrant_storage`, and never run the collection builder with `--recreate` against the team's
storage; the collections are already complete.

---

## 9. Configuration reference

`.env` is machine-local and gitignored. The variables that matter most:

| Variable | Value used here | Meaning |
|---|---|---|
| `COMPOSE_FILE` | `compose.yaml:compose.gpu.yaml` | Always load the GPU override |
| `BACKEND_BUILD_TARGET` | `search-cuda` | Dockerfile stage: `production` (no torch), `search` (CPU torch), `search-cuda` (CUDA torch) |
| `SEARCH_ENABLED` | `true` | Registers the Qdrant/TRAKE routes |
| `SEARCH_DEVICE` | `cuda` | Device passed to every encoder |
| `SEARCH_MODEL_CACHE_SIZE` | `1` | How many encoders stay resident |
| `BEIT3_CHECKPOINT_PATH` | `/models/beit3_large_patch16_224.pth` | Path **inside** the container |
| `PE_MODEL_NAME` | `hf-hub:timm/PE-Core-bigG-14-448` | open_clip model id |
| `JINA_MODEL_NAME` | `jinaai/jina-embeddings-v5-omni-small` | Hugging Face model id |
| `MONGO_SEARCH_ENABLED` | `true` | Enables OCR/ASR search |
| `MONGO_SEARCH_URI` | `mongodb://aicadmin:...@mongodb:27017/...` | Password must match `MONGO_ROOT_PASSWORD` |
| `TRAKE_TIER3_ENABLED` | `false` | Frame-exact refinement; needs original videos |
| `TRAKE_QWEN_RERANK_ENABLED` | `false` | Local Qwen2.5-VL tie-break rerank |

Visual search needs **both** `SEARCH_ENABLED=true` and a build target containing torch. The
`production` target only installs `requirements-core.txt`, so it lacks numpy and the search routes
fail to register.

---

## 10. Troubleshooting

| Symptom | Fix |
|---|---|
| `permission denied` talking to Docker | `sudo usermod -aG docker "$USER"`, then log out and back in |
| `could not select device driver "nvidia"` | NVIDIA Container Toolkit missing or unconfigured — see §2 |
| `torch.cuda.is_available()` is False | Image was built from the CPU `search` stage. Set `BACKEND_BUILD_TARGET=search-cuda` and rebuild `backend-api` |
| BEiT-3 query returns HTTP 500, `FileNotFoundError` | `BEIT3_CHECKPOINT_PATH` does not match the filename in `runtime-data/checkpoints/` |
| PE query dies with CUDA OOM | fp32 weights exceed 8GB — see §5.3 |
| `.env`, `compose.gpu.yaml` or `runtime-data/` vanished after a branch switch or `git clean` | Re-run `./setup-linux.sh` |
| Qdrant collection stuck `grey` | `curl -X PATCH localhost:6333/collections/jina -H 'Content-Type: application/json' -d '{"optimizers_config":{}}'` and wait for `green`; never restart while `yellow` |
| Mongo search index stuck `PENDING` | You are on the `:preview` image. Use `8.0.25`. Check real index size with `docker system df -v \| grep mongot` — a real index is ~42MB, ~1MB means empty |
| First query times out | The `search-cuda` stage sets gunicorn `--timeout 900`; if it still trips, check free VRAM with `nvidia-smi` |
| Ports 5000/8088/27017 already taken | Change `BACKEND_PORT`, `FRONTEND_PORT`, `MONGO_PORT` in `.env` |

---

## 11. Linux-specific files

| File | Git status | Purpose |
|---|---|---|
| `setup-linux.sh` | new | Recreates the whole local configuration |
| `compose.gpu.yaml` | new | Reserves one NVIDIA GPU for `backend-api` |
| `backendAIC2025/Dockerfile` | modified | Adds the `search-cuda` stage (CUDA 12.4 torch, 900s timeout, timed access log) |
| `compose.yaml` | modified | MongoDB `8.0.25` and `_v2` volumes |
| `.env` | gitignored | Machine-local configuration |
| `runtime-data/` | gitignored | Symlinks to the corpus |

---

## 12. Documentation map

| Document | Audience |
|---|---|
| `README.md` (this file) | Anyone running the stack on Linux |
| [README_MEMBERS.md](README_MEMBERS.md) | Team members: data layout, git rules, Windows notes |
| [README_USER.md](README_USER.md) | People who only use the website |
| [README_TRAKE.md](README_TRAKE.md) | How the TRAKE pipeline is implemented |
| [README_TRAKE_UI.md](README_TRAKE_UI.md) | Proposed UI for verifying TRAKE answers |
| [README_IMPROVE_TRAKEUI_ASR_OCR.md](README_IMPROVE_TRAKEUI_ASR_OCR.md) | Delivered ASR/OCR/TRAKE-UI improvements |
| [AIC2026_IMPROVEMENT_SPEC (1).md](<AIC2026_IMPROVEMENT_SPEC (1).md>) | Full technical specification of the 2026 architecture |

---

## License

Submitted as part of the AI Challenge HCMC. Use and distribution follow the challenge's terms.

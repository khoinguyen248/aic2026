# Guide for AIC 2026 team members

For members who develop the system or run the full stack on their own machine. If you only use the
website that the main dev operates, read [README_USER.md](README_USER.md) instead — you need neither
Docker nor any model files.

Linux setup, model downloads and backend monitoring are covered in detail in [README.md](README.md).
This document adds the parts that are team conventions rather than machine setup.

## 1. Current components

The system runs on Docker Compose:

- Frontend: `http://localhost:8088`
- Backend API: `http://localhost:5000`
- Frame server: `http://localhost:8081`
- Qdrant: vector collections `beit3`, `jina`, `pe`
- MongoDB Atlas Local: OCR/ASR search

BEiT-3 and Jina text search both work. PE needs more VRAM than a laptop GPU has (see §5.3 of
[README.md](README.md)) — do not enable it on a low-spec machine.

## 2. Prerequisites

Install Git and Docker with the Compose v2 plugin, then check:

```bash
git --version && docker version && docker compose version
```

Clone the source and create the environment file:

```bash
git clone https://github.com/khoinguyen248/aic2026.git
```

```bash
cd aic2026 && ./setup-linux.sh
```

On Windows the equivalent of the setup script is manual: copy `.env.example` to `.env`, create the
three MongoDB volumes, and place the data under `runtime-data\`.

## 3. Data layout

Arrange the corpus like this — on Linux `runtime-data/` entries are symlinks into the folder above the
repository, on Windows they are real folders:

```text
runtime-data/
├── checkpoints/
│   └── beit3_large_patch16_224.pth
├── keyframes/
│   ├── L21_V001/
│   └── ...
├── metadata/
│   ├── asr/
│   └── ocr/
└── qdrant_storage/
    ├── aliases/
    ├── collections/
    │   ├── beit3/
    │   ├── jina/
    │   └── pe/
    └── raft_state.json
```

## 4. `.env` configuration

Generate a secret of your own and enable only the features whose data you actually have:

```env
SECRET_KEY=replace-with-a-random-string

SEARCH_ENABLED=true
SEARCH_DEVICE=cuda
SEARCH_MODEL_CACHE_SIZE=1
BACKEND_BUILD_TARGET=search-cuda
BEIT3_CHECKPOINT_PATH=/models/beit3_large_patch16_224.pth
QDRANT_URL=http://qdrant:6333

MONGO_ROOT_USER=aicadmin
MONGO_ROOT_PASSWORD=replace-with-your-own-password
MONGO_SEARCH_ENABLED=true
MONGO_SEARCH_URI=mongodb://aicadmin:PASSWORD@mongodb:27017/?authSource=admin&directConnection=true
MONGO_SEARCH_DB=aic2026
```

`MONGO_ROOT_PASSWORD` and the password inside `MONGO_SEARCH_URI` must be identical. Never commit
`.env`. On a machine without a GPU use `SEARCH_DEVICE=cpu` and `BACKEND_BUILD_TARGET=search`.

If OCR/ASR has not been imported yet:

```env
MONGO_SEARCH_ENABLED=false
```

## 5. First-time MongoDB setup

Compose expects three external named volumes. Create them once per machine:

```bash
docker volume create aic2026_mongodb_data_v2 && docker volume create aic2026_mongodb_config_v2 && docker volume create aic2026_mongodb_mongot_v2
```

OCR/ASR data is imported from the separate MongoDB package the team distributes; ingesting 343k
documents takes about three minutes. You do not need to re-import after restarting Docker, because the
data lives in the volumes.

Use the image tag `mongodb/mongodb-atlas-local:8.0.25`. The `:preview` tag registers search indexes but
never runs the initial sync, leaving them stuck at `status=PENDING` forever.

## 6. Running the stack

From the repository root:

```bash
docker compose up -d --build
```

```bash
docker compose ps
```

Check:

```bash
curl -s localhost:5000/health/app
```

```bash
curl -s localhost:5000/search/health
```

```bash
curl -s localhost:6333/collections
```

Open <http://localhost:8088>, pick Visual Search, choose `beit3` or `jina`, type a description and
search.

## 7. When a Qdrant collection shows `grey`

Storage restored from a ZIP can sit waiting for optimization. Poke the optimizer without touching any
vector:

```bash
for c in beit3 jina pe; do curl -s -X PATCH "http://localhost:6333/collections/$c" -H 'Content-Type: application/json' -d '{"optimizers_config":{}}'; done
```

Wait for `grey -> yellow -> green`. Do not restart Qdrant while it is `yellow`.

Never run this against the team's storage:

```bash
python -m search_engine.search build --model beit3 --recreate
```

`--recreate` drops the collection before rebuilding it, and the team's `qdrant_storage` already holds
complete collections.

## 8. Stopping and restarting

Stop the containers but keep all data:

```bash
docker compose down
```

Start again:

```bash
docker compose up -d
```

Do not delete `runtime-data/qdrant_storage`, do not use `docker compose down -v`, and do not remove a
Mongo volume without a backup.

## 9. Git rules

Update the source and work on your own branch:

```bash
git checkout main && git pull && git checkout -b feature/your-feature
```

Before pushing:

```bash
docker compose config --quiet && docker compose up -d --build --wait && git status
```

Do not push directly to `main`. A pull request must describe what changed, how to verify it, any new
environment variables, and the impact on MongoDB, Qdrant, keyframes or model files.

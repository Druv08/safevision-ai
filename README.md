# SafeVision AI

PPE (personal protective equipment) violation monitor. It runs YOLOv8 models
on uploaded images, uploaded videos and browser-webcam frames, flags workers
without a helmet or a high-visibility vest, and stores each violation with a
screenshot for review.

It is a prototype. See [Known limitations](#known-limitations) before relying on it.

## What it does

- **Detection:** three YOLOv8 models run on every frame: a 5-class PPE model
  (used for vest / no-vest), a 17-class construction-safety model (used for
  hardhat / no-hardhat) and COCO `yolov8n` (used only for the person class).
  A violation is logged only when a missing-helmet or missing-vest detection
  overlaps a detected person, at most once per person per type. A helmet
  held in the hand rather than worn counts as missing.
- **Inputs:** image upload (jpg, png), video upload (mp4, mov, avi, webm), and
  a browser camera on the Live Monitoring page (a frame every 3 s, or 5 s clips).
- **Storage:** violations go to Supabase Postgres; screenshots go to a private
  Supabase Storage bucket and are shown through signed URLs that expire after
  5 minutes.
- **Login:** Supabase Auth (email + password). Two roles: `viewer` (read,
  export) and `admin` (also acknowledge, close and delete).
- **Review:** dashboard with KPI counts, a violations-over-time chart (24 h / 7 d /
  30 d / all), breakdowns by type, source and review status, and live system
  health; violations list with filters by type, status, source and date,
  search, sorting, pagination, a detail view with the evidence image, status
  changes with notes (`new` → `acknowledged` → `closed`), delete with
  confirmation, and CSV export.
- **Audit:** every screenshot view, export, delete and status change is written
  to an append-only `audit_log` table.

## Stack

| Part | Technology |
|---|---|
| Frontend | React 19 + Vite, Tailwind CSS, Recharts, `@supabase/supabase-js` |
| Backend | FastAPI (Python 3.12), Ultralytics YOLOv8, OpenCV |
| Database, storage, login | Supabase (Postgres with Row Level Security, Storage, Auth) |
| Model training | Scripts in `ai-model/training/` (datasets: [DATASETS.md](DATASETS.md)) |

```
browser (React) ──sign in──▶ Supabase Auth
      │  Bearer <access token>
      ▼
FastAPI backend ──service-role key──▶ Supabase Postgres + Storage
      │
      ▼
YOLOv8 models (local weights files)
```

## Repository layout

```
safevision-ai/
├── backend/            FastAPI app
│   ├── main.py         app, CORS, /health
│   ├── config.py       settings from environment variables
│   ├── auth.py         Supabase token check, viewer/admin dependencies
│   ├── supabase_client.py
│   ├── routes/         detection.py (uploads, list, status, stats), evidence.py (screenshots, export, delete)
│   ├── services/       detection, video, models, violations, storage
│   ├── scripts/        migrate_csv.py (import old CSV logs)
│   ├── tests/          pytest; Supabase and models are mocked
│   └── Dockerfile
├── frontend/           React + Vite app
├── supabase/           SQL migration and setup guide
├── ai-model/           training, dataset-building and local inference scripts
├── docs/               research and progress notes
└── docker-compose.yml
```

## Setup

You need Python 3.12 (3.11+ works), Node 20.19+ or 22.12+, a Supabase project,
and the model weights files (they are not in git).

### 1. Supabase

Follow [supabase/README.md](supabase/README.md): run the migration, turn off
public sign-ups, create a user and make it an admin.

### 2. Backend

```bash
python -m venv venv
venv\Scripts\activate          # Windows; on macOS/Linux: source venv/bin/activate
cd backend
pip install -r requirements-dev.txt --extra-index-url https://download.pytorch.org/whl/cpu
copy .env.example .env         # macOS/Linux: cp .env.example .env
```

Edit `backend/.env`: set `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`, and
point the three `*_MODEL_PATH` variables at your weights:

| Variable | Default | What it is |
|---|---|---|
| `PPE_MODEL_PATH` | newest of `ai-model/outputs/training-runs/safevision_yolov8n_5class_v5d_50epochs` and `..._5class_v2` (`weights/best.pt`) | 5-class PPE model |
| `HELMET_MODEL_PATH` | `ai-model/outputs/training-runs/safevision_yolov8n_v1/weights/best.pt` | 17-class helmet model |
| `PERSON_MODEL_PATH` | `yolov8n.pt` in the repository root | COCO yolov8n, [download](https://github.com/ultralytics/assets/releases) |

Optionally set `*_MODEL_SHA256` to pin each file. All variables are listed in
[backend/.env.example](backend/.env.example).

```bash
python -m uvicorn main:app --reload
```

The backend refuses to start without the Supabase variables. If weights are
missing it still starts, `/health` reports `"model": {"loaded": false}`, and
the detection endpoints return 503.

### 3. Frontend

```bash
cd frontend
npm install
copy .env.example .env         # macOS/Linux: cp .env.example .env
npm run dev
```

Set `VITE_API_URL` (default `http://127.0.0.1:8000`), `VITE_SUPABASE_URL` and
`VITE_SUPABASE_ANON_KEY` (the **anon** key, never the service-role key).
Open http://localhost:5173 and sign in.

### Docker (backend only)

```bash
docker compose up --build
```

`docker-compose.yml` reads `backend/.env`, sets `ENV=production` (no `/docs`),
and mounts `ai-model/outputs/training-runs/` and `./yolov8n.pt` read-only. Both
must exist on the host first; if `./yolov8n.pt` is missing, Docker creates an
empty directory with that name.

### Tests and lint

```bash
cd backend && pytest -q && ruff check .
cd frontend && npm run lint && npm run build
```

The backend tests use an in-memory fake of the Supabase client and never load
model weights, so they need no keys. CI (`.github/workflows/ci.yml`) runs the
same commands.

## API

Every endpoint except `/health` needs `Authorization: Bearer <Supabase access token>`.
Interactive docs are at `/docs` and `/redoc` unless `ENV=production`.

| Method | Path | Role | Description |
|---|---|---|---|
| GET | `/health` | none | Model loading state, Supabase connection, free disk space |
| GET | `/` | viewer | Liveness message |
| POST | `/detect-image` | viewer | Form field `image` (jpg/jpeg/png), optional `source=image\|camera`. Returns detections (each with `class_id`, `confidence` and a pixel `box` `[x1, y1, x2, y2]`) and a per-image summary; logs violations. |
| POST | `/detect-video` | viewer | Form field `video` (mp4/mov/avi/webm), optional `source=video\|camera`. Returns violation counts, `frames_processed`, `duration_seconds` and `events` (`type`, `time` in seconds, `confidence`) for each logged violation; 422 if the video cannot be decoded. |
| GET | `/violations` | viewer | Query: `type` (`no_helmet`/`no_vest`), `status` (`new`/`acknowledged`/`closed`), `source` (`image`/`video`/`camera`), `date_from`, `date_to` (ISO, exclusive), `q`, `page`, `page_size` (≤ 500), `sort` (`newest` default, or `oldest`). |
| PATCH | `/violations/{id}` | admin | Body `{"status": "acknowledged" \| "closed", "note": "..."}` |
| DELETE | `/violations/{id}` | admin | Deletes the row and its screenshot (audited) |
| GET | `/violations/{id}/evidence` | viewer | `{"url": <signed URL>, "expires_in": 300}` (audited) |
| GET | `/download-violations` | viewer | CSV of all violations (audited); 404 if there are none |
| GET | `/dashboard-stats` | viewer | Totals by type and model status |

Upload rules: extension must be in the list above **and** the file's magic
bytes must match it; files over `MAX_UPLOAD_MB` (default 50) get 413; uploads
are saved under a random name and deleted after processing. Detection requests
are limited to `RATE_LIMIT_PER_MINUTE` (default 30) per user. Missing or
mismatched weights give 503.

## Known limitations

- **Accuracy is limited.** The helmet model (v1) has helmet mAP50 0.72 on its
  validation split; the PPE model (v2) has vest mAP50 0.95 and no-vest 0.82
  (see `docs/research-log.md`). These are validation numbers on public
  datasets, not field results. Expect false positives and misses.
- **No live CCTV / RTSP ingestion, no alerts or escalation, no tracking,
  no zones, no multi-site support, no compliance certificates.** These are
  planned and labelled as such in the UI.
- **No deduplication across frames or requests.** Video uses a per-type
  cooldown (`VIDEO_COOLDOWN_SECONDS`, measured in video time), and webcam
  mode sends independent frames, so the same person can be logged repeatedly.
- **Synchronous processing.** A video is analysed inside the HTTP request, all
  frames, three models per frame, on CPU. Long videos will time out.
- **Rate limiting is in-process.** It resets on restart and is per worker.
- **Every request calls Supabase Auth** to verify the token (one network
  round-trip per request).
- **The dashboard chart only covers the newest 500 violations.**
- **Search** matches type, status, note and model version only.
- **The person model is COCO `yolov8n`** and is downloaded separately; it is not
  covered by the checksum unless you set `PERSON_MODEL_SHA256`.
- `ai-model/inference/` scripts still write a local CSV and JPEGs; they are
  offline tools and do not use Supabase.

## License

[AGPL-3.0](LICENSE), because the project uses Ultralytics YOLOv8 (AGPL-3.0).
Training data licences are listed in [DATASETS.md](DATASETS.md).

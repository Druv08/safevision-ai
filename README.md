# SafeVision AI

PPE (personal protective equipment) violation monitor. It runs YOLOv8 models
on uploaded images, uploaded videos and browser-webcam frames, flags workers
without a helmet or a high-visibility vest, and stores each violation with a
screenshot for review.

It is a prototype. See [Known limitations](#known-limitations) before relying on it.

## What it does

- **Detection:** one shared pipeline (`backend/services/pipeline.py`) is used
  by the image and video endpoints, the CLI scripts and evaluation. Per frame it
  runs a PPE model (vest / no-vest), a helmet model (`HELMET_MODEL_PATH`) and a
  person model; with a `-pose` person model, head and torso regions come from
  keypoints, otherwise from box geometry. In video, each person is tracked
  (ByteTrack) and a violation is logged only after the same person has been
  missing an item for `VIOLATION_WINDOW_SECONDS` (default 2): one row per
  person per episode, with start/end time, track ID and one screenshot.
  Compliant people are recorded too, so `/dashboard-stats` reports a
  compliance rate.
  A violation is logged only when a missing-helmet or missing-vest detection
  overlaps a detected person, at most once per person per type. A helmet
  held in the hand rather than worn counts as missing.
- **Inputs:** network cameras over RTSP, read continuously by the backend
  (see below); image upload (jpg, png); video upload (mp4, mov, avi, webm); and
  a **webcam demo** page that sends frames or 5 s clips from a camera attached
  to the browser.
- **Cameras and zones:** admins add RTSP cameras on the Cameras page. Each
  running camera has a background reader on the server that grabs every frame
  and analyses the newest one up to `sample_fps` times a second (default 5),
  reconnects with backoff (1 s doubling to 30 s) when the stream drops, and
  reports its status (streaming / reconnecting / error, analysed fps, last
  frame, alerts, reconnects). Credentials are stored encrypted
  (`CAMERA_SECRET_KEY`) and never returned by the API. Zones are polygons drawn
  on a camera snapshot, each with a rule: hard hat and vest, hard hat only,
  vest only, no PPE required, or no entry. A person is in a zone when their
  feet are; overlapping zones combine (strictest wins); outside every zone the
  camera's default rule applies. A person in a no-entry zone for the 2 s
  window is a `zone_intrusion` violation.
- **Storage:** violations go to Supabase Postgres; screenshots go to a private
  Supabase Storage bucket and are shown through signed URLs that expire after
  5 minutes.
- **Login:** Supabase Auth (email + password). Two roles: `viewer` (read,
  export) and `admin` (also acknowledge, close and delete).
- **Review:** the dashboard is aggregate by default: violations by zone, shift
  (`SHIFTS`, in `SITE_TIMEZONE`) and type, PPE presence rates overall and per
  shift, review status, recorded causes, and a weekly report (HTML, print to
  PDF) with the week before for comparison. Individual records and their
  screenshots are one click deeper, on the Violations page: filters, search,
  a detail view with the evidence image, and the workflow `new` →
  `acknowledged` → `action_taken` (a note is required) → `closed`, with a
  cause: PPE not issued, issued but not worn, damaged, false detection, other.
- **Alerts:** one message per violation episode (from cameras, by default) to
  every enabled recipient, at most once (a unique `(violation, recipient)` row
  is claimed before sending). Channels: WhatsApp (Meta Cloud API or Twilio,
  from environment variables; with no credentials the message is logged and
  nothing fails) and signed JSON webhooks. Templates in English and Hindi,
  chosen per recipient; each message links to the record. Recipients and the
  delivery log are on the Alerts page (admin).
- **Privacy:** every detected person is pixelated in stored screenshots before
  the boxes and labels are drawn (`PRIVACY_BLUR`). The unblurred original is
  kept only encrypted (`EVIDENCE_SECRET_KEY`) for `ORIGINAL_RETENTION_HOURS`
  (72); only admins can open it and each view is audited. A job inside the
  backend deletes screenshots older than `RETENTION_DAYS` (30), expired
  originals and leftover uploads, except records on legal hold. See
  [docs/privacy-policy-template.md](docs/privacy-policy-template.md) for the
  notice, signage, retention statement and usage policy to adapt.
- **Evidence integrity:** the SHA-256 of each screenshot is stored with the
  violation and the model version at capture; "Verify" re-hashes the stored
  file. Admins can export one record as a zip (image, metadata with both
  hashes, the record's audit trail, `SHA256SUMS`). `audit_log` is append-only
  for every database role, the service role included.
- **Audit:** screenshot and original views, exports, deletes, status changes,
  legal holds, retention deletions and alert-recipient changes are written to
  `audit_log`.

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
│   ├── routes/         detection, evidence (screenshots, export, legal hold), cameras, alerts, reports
│   ├── services/       pipeline, tracker, zones, streams, violations, storage, privacy, evidence, alerts, reports
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
| `PPE_MODEL_PATH` | `…5class_v5d_50epochs`, else `…5class_v2` (`ai-model/outputs/training-runs/*/weights/best.pt`) | vest / no-vest |
| `HELMET_MODEL_PATH` | `…5class_v5d_50epochs`, else `…_v1` (17-class) | helmet / no-helmet; classes matched by name |
| `PERSON_MODEL_PATH` | `yolov8n-pose.pt`, else `yolov8n.pt`, in the repository root | person (+ keypoints with the pose model), [download](https://github.com/ultralytics/assets/releases) |

Defaults live in `backend/weights.py` and are shared with the CLI scripts and
`evaluate.py`, so every tool uses the same best available weights.

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

### Edge device (ONNX)

To run on a small CPU-only computer without PyTorch inference, export the
weights to ONNX and point the backend (or the CLI scripts) at the `.onnx` files:

```bash
pip install -r backend/requirements-onnx.txt
python ai-model/training/export_onnx.py            # the PPE, helmet and person weights in use
# then in backend/.env: PPE_MODEL_PATH=…/best.onnx  HELMET_MODEL_PATH=…/best.onnx  PERSON_MODEL_PATH=…/yolov8n-pose.onnx
```

The loader reads each ONNX model's task (detect / pose) and class names from
the metadata written at export. ONNX models run at the export size (640 by
default). Run `evaluate.py` with the `.onnx` files before deploying. **The
ONNX path has not been run yet:** the ONNX packages could not be downloaded in
the session that added it.

Ultralytics normally `pip install`s missing packages at run time; this project
turns that off (`YOLO_AUTOINSTALL=false`), so a missing package fails with an
error instead of being installed on a server or edge device.

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
| GET | `/violations` | viewer | Query: `type` (`no_helmet`/`no_vest`/`zone_intrusion`), `status` (`new`/`acknowledged`/`action_taken`/`closed`), `source` (`image`/`video`/`camera`), `camera_id`, `zone_id`, `date_from`, `date_to` (ISO, exclusive), `q`, `page`, `page_size` (≤ 500), `sort` (`newest` default, or `oldest`). |
| PATCH | `/violations/{id}` | admin | Body `{"status": "acknowledged" \| "action_taken" \| "closed", "note"?, "cause"?}`; `action_taken` needs a note. Causes: `ppe_not_issued`, `ppe_not_worn`, `ppe_damaged`, `false_detection`, `other`. |
| DELETE | `/violations/{id}` | admin | Deletes the row, its screenshot and original (audited); 409 on legal hold |
| GET | `/violations/{id}/evidence` | viewer | `{"url": <signed URL>, "expires_in": 300}` (audited) |
| GET | `/violations/{id}/verify` | viewer | Re-hashes the stored screenshot: `{"status": "ok" \| "mismatch" \| "missing" \| …}` |
| GET | `/violations/{id}/original` | admin | Unblurred original JPEG while it is kept (audited before it is returned); 410 when gone |
| GET | `/violations/{id}/export` | admin | Evidence zip: screenshot, metadata, audit trail, SHA256SUMS (audited) |
| PUT | `/violations/{id}/legal-hold` | admin | `{"hold": true, "reason": "..."}` or `{"hold": false}` (audited) |
| GET | `/reports/summary` | viewer | `date_from`, `date_to`, `bucket` (`day`/`hour`): totals by type, zone, shift, status, cause; presence rates; trend |
| GET | `/reports/weekly` | viewer | `week_start` (Monday, default last complete week): HTML report (audited) |
| GET, POST | `/alerts/recipients` | admin | List (with the active WhatsApp provider) / add `{"name", "channel": "whatsapp" \| "webhook", "address", "language": "en" \| "hi"}` |
| PATCH, DELETE | `/alerts/recipients/{id}` | admin | Edit / remove a recipient |
| POST | `/alerts/recipients/{id}/test` | admin | Sends a sample alert now: `{"status": "sent" \| "logged" \| "failed", "error"}` |
| GET | `/alerts` | admin | Recent deliveries |
| GET | `/download-violations` | viewer | CSV of all violations (audited); 404 if there are none |
| GET | `/dashboard-stats` | viewer | Totals by type, compliance rate and model status |
| GET | `/cameras` | viewer | Cameras with live status. Never includes credentials (`has_credentials` only). |
| POST | `/cameras` | admin | `{"name", "url": "rtsp://…", "username"?, "password"?, "sample_fps"?, "default_policy"?, "enabled"?}`. Credentials in the URL are moved to encrypted storage. |
| PATCH | `/cameras/{id}` | admin | Change any field; omitted credentials are kept, `clear_credentials` removes them. A running camera restarts with the new settings. |
| DELETE | `/cameras/{id}` | admin | Stops the camera, deletes it and its zones (violations are kept) |
| POST | `/cameras/{id}/start`, `/stop` | admin | Start / stop analysis (also sets whether it starts with the backend) |
| GET | `/cameras/{id}/snapshot` | viewer | JPEG of the latest frame (or one fetched now); 503 if unreachable |
| GET, PUT | `/cameras/{id}/zones` | viewer, admin | Zones as `[{"name", "policy", "polygon": [[x, y], …]}]`, coordinates 0..1. PUT replaces all zones and applies to a running camera from the next frame. |

Camera changes (create, edit, delete, start, stop, zones) are written to `audit_log`.

Upload rules: extension must be in the list above **and** the file's magic
bytes must match it; files over `MAX_UPLOAD_MB` (default 50) get 413; uploads
are saved under a random name and deleted after processing. Detection requests
are limited to `RATE_LIMIT_PER_MINUTE` (default 30) per user. Missing or
mismatched weights give 503.

## Known limitations

- **Accuracy is limited.** The helmet model (v1) has helmet mAP50 0.72 on its
  validation split; the PPE model (v2) has vest mAP50 0.95 and no-vest 0.82
  (see `docs/research-log.md`). These come from random splits in which frames
  of the same video appear in train and validation, so they are optimistic;
  [docs/evaluation-protocol.md](docs/evaluation-protocol.md) describes the
  camera-level split and event metrics to use instead. No event-level numbers
  exist yet.
- **No escalation, no multi-site support, no compliance certificates.**
- **Alerts are untested against real WhatsApp providers.** The Meta and Twilio
  requests follow their documented APIs, but no message has been sent with
  real credentials. Both providers deliver free-form text only within 24 hours
  of the recipient last messaging your number; outside that window they need
  an approved template, which is not implemented. Alerts go to every enabled
  recipient (no per-camera routing) and are sent from an in-process pool: a
  hard kill can leave an alert in `sending`, never retried.
- **Blurring covers detected people only.** Anyone the person model misses is
  stored unblurred. Pixelation also blurs the PPE itself; the drawn labels and
  the original (while kept) are the evidence.
- **Retention deletes files, not rows.** Violation rows, the alert log and the
  audit log are kept until an administrator deletes them. The audit log cannot
  be changed through the application or the service-role key, but the database
  owner can still disable its triggers.
- **Reports aggregate in Python** over every row in the range: fine for tens
  of thousands of records, slow beyond that. Presence rates are per shift and
  overall, not per zone (an observation spans the person's whole time in view).
- **Camera reading is tested over HTTP-MJPEG only.** The RTSP path uses the same
  OpenCV/FFMPEG reader (RTSP over TCP, 10 s timeouts), but it has not been run
  against a real RTSP camera or server.
- **Camera throughput is CPU-bound.** All cameras share one model, one frame
  at a time. On the development laptop (CPU, three models per frame) that is
  about 6 analysed frames per second in total: three cameras got about 2 fps
  each, not the configured 5. Use fewer cameras per machine, a GPU, or ONNX
  on a faster CPU.
- **Run the backend as a single process.** Camera readers are threads inside
  the API process; with several uvicorn workers each would read every camera.
- **A hard kill leaves episodes open.** Stopping a camera or shutting the
  backend down cleanly closes open violations; after a crash their end time
  stays empty.
- **Tracks restart when the picture jumps.** A camera that cuts, loops or
  re-connects starts new track IDs, which can log the same person again.
- **Tracking only within one video.** IDs reset per upload, so a webcam clip
  sent every few seconds starts new tracks each time, and a tracker ID switch
  (occlusion, camera movement) can log the same person twice. Single images
  (including webcam frame mode) have no time dimension: every person missing
  an item is logged at once, so frame mode can log the same person repeatedly.
- **Synchronous processing.** A video is analysed inside the HTTP request, all
  frames, three models per frame, on CPU. Long videos will time out.
- **Rate limiting is in-process.** It resets on restart and is per worker.
- **Every request calls Supabase Auth** to verify the token (one network
  round-trip per request).
- **Search** matches type, status, note and model version only.
- **Snapshots for the zone editor are plain frames** (no overlays), fetched
  through the API.
- **The person model is COCO `yolov8n(-pose)`** and is downloaded separately; it is not
  covered by the checksum unless you set `PERSON_MODEL_SHA256`.
- `ai-model/inference/violation_detection.py` writes a local CSV and JPEGs
  (`ai-model/outputs/violations/violation_episodes.csv`); import it with
  `backend/scripts/migrate_csv.py`.

## License

[AGPL-3.0](LICENSE), because the project uses Ultralytics YOLOv8 (AGPL-3.0).
Training data licences are listed in [DATASETS.md](DATASETS.md).

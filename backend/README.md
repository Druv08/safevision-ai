# Backend (FastAPI)

API for SafeVision AI: runs the YOLO models on uploads, stores violations and
screenshots in Supabase, and serves them to the React frontend. Setup, the
endpoint list and known limitations are in the [main README](../README.md).

## Layout

- `main.py` — app, CORS, `/health`, 503 handler for missing weights
- `config.py` — all settings, from environment variables / `.env`
- `auth.py` — verifies the Supabase access token, loads the role from `profiles`
- `supabase_client.py` — the one service-role client
- `routes/detection.py` — uploads, violation list, status changes, dashboard stats
- `routes/evidence.py` — signed screenshot URLs, CSV export, delete (all audited)
- `services/` — detection rules, video processing, model loading, violations, storage
- `scripts/migrate_csv.py` — import old CSV logs into Supabase
- `tests/` — pytest; Supabase and the models are mocked

## Run

```bash
cd backend
python -m uvicorn main:app --reload
pytest -q
ruff check .
```

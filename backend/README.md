# Backend (FastAPI)

FastAPI service for SafeVision AI. Handles inference requests, violation
storage, and serves data to the Next.js dashboard.

## Folders

- `routes/` — API route modules (added as features grow).
- `services/` — Business logic: detection, Supabase upload, violation rules.
- `uploads/` — Temporary local uploads (videos/images).

## Run locally

```bash
cd backend
uvicorn main:app --reload
```

Open: http://127.0.0.1:8000/docs

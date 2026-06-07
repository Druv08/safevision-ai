"""
main.py
-------
SafeVision AI - FastAPI backend entry point.

Run from inside the backend/ folder:
    uvicorn main:app --reload

Then open:
    http://127.0.0.1:8000          -> root endpoint
    http://127.0.0.1:8000/health   -> health + model + storage status
    http://127.0.0.1:8000/docs     -> interactive Swagger UI
    http://127.0.0.1:8000/api/...  -> detection endpoints
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes.detection import router as detection_router
from services.model_service import get_model_status


# ---------------------------------------------------------------------------
# App + CORS
# ---------------------------------------------------------------------------
app = FastAPI(title="SafeVision AI Backend")

# CORS for the local React/Next frontend that will be added on Day 8+.
# We intentionally keep this narrow (localhost:3000 only) for now.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount the AI detection routes under /api/...
app.include_router(detection_router)


# ---------------------------------------------------------------------------
# Storage locations the backend writes to (declared here so /health can
# report on them without each route having to know).
# ---------------------------------------------------------------------------
BACKEND_DIR = Path(__file__).resolve().parent
UPLOADS_DIR = BACKEND_DIR / "uploads"
RESULTS_DIR = BACKEND_DIR / "results"


def _storage_status() -> dict:
    """Report whether the local upload / result folders are usable."""
    out: dict = {}
    for label, path in (("uploads", UPLOADS_DIR), ("results", RESULTS_DIR)):
        try:
            path.mkdir(parents=True, exist_ok=True)
            out[label] = {
                "path": str(path),
                "writable": True,
            }
        except Exception as exc:  # noqa: BLE001
            out[label] = {
                "path": str(path),
                "writable": False,
                "error": str(exc),
            }
    return out


# ---------------------------------------------------------------------------
# Root + health
# ---------------------------------------------------------------------------
@app.get("/")
def root() -> dict:
    """Basic root endpoint to confirm the backend is up."""
    return {
        "message": "SafeVision AI backend is running",
        "status": "success",
    }


@app.get("/health")
def health() -> dict:
    """Health check: backend, AI model availability, local storage."""
    model = get_model_status()
    return {
        "backend": "active",
        "model": {
            "loaded": model["model_loaded"],
            "path":   model["model_path"],
            "message": model["message"],
        },
        "storage": _storage_status(),
    }

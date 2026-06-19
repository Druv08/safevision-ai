"""
main.py
-------
SafeVision AI - FastAPI backend starter.

Run from inside the backend/ folder:

    python -m uvicorn main:app --reload

Then open:

    http://127.0.0.1:8000
    http://127.0.0.1:8000/docs
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Import detection router
from routes.detection import router as detection_router

# Create FastAPI app
app = FastAPI(
    title="SafeVision AI Backend",
    version="1.0.0"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(detection_router)

# -----------------------------
# Screenshots Static Folder
# -----------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]

SCREENSHOT_DIR = (
    PROJECT_ROOT
    / "ai-model"
    / "outputs"
    / "violations"
    / "screenshots"
)

app.mount(
    "/screenshots",
    StaticFiles(directory=str(SCREENSHOT_DIR)),
    name="screenshots"
)


@app.get("/")
def root():
    return {
        "message": "SafeVision AI backend is running",
        "status": "success",
    }


@app.get("/health")
def health():
    return {
        "backend": "active",
        "ai_model": "connected",
        "database": "not connected yet",
    }
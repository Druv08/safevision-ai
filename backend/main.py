"""
main.py
-------
SafeVision AI - FastAPI backend starter.

Run from inside the backend/ folder:
    uvicorn main:app --reload

Then open:
    http://127.0.0.1:8000        -> root endpoint
    http://127.0.0.1:8000/docs   -> interactive Swagger UI
"""

from fastapi import FastAPI

# Create the FastAPI app instance
app = FastAPI(title="SafeVision AI Backend")


@app.get("/")
def root():
    """Basic root endpoint to confirm the backend is up."""
    return {
        "message": "SafeVision AI backend is running",
        "status": "success",
    }


@app.get("/health")
def health():
    """Lightweight health check. Will be expanded as we wire up services."""
    return {
        "backend": "active",
        "ai_model": "not connected yet",
        "database": "not connected yet",
    }

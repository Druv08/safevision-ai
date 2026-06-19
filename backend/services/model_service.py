"""
services/model_service.py
-------------------------
SafeVision AI - YOLO model loader (singleton).

Why this file exists (beginner-friendly):
    Loading a YOLO model from disk takes a couple of seconds and uses
    a few hundred MB of RAM. We do NOT want to repay that cost on every
    HTTP request. This module loads the model ONCE the first time it is
    needed and caches it in a module-level variable; every subsequent
    call to `get_model()` returns the already-loaded instance.

If the weights file is missing or corrupt:
    - `get_model()` returns `None` and stores the error message
    - `get_model_status()` reports `model_loaded: False` plus the message
    - This means the backend stays UP and `/health` still works; only
      the detection endpoints will return a "model not available" error.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

# Ultralytics is heavy; we import it lazily inside the loader so simply
# importing this module (e.g. for tests / `--help`) does not pull in torch.
# But we still need the type for annotations, so we use `Any`.


# ---------------------------------------------------------------------------
# Project paths
# ---------------------------------------------------------------------------
# This file lives at:
#   <project_root>/backend/services/model_service.py
# So PROJECT_ROOT is two parents up from this file.
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

DEFAULT_MODEL_RELATIVE = Path(
    "ai-model/outputs/training-runs/safevision_yolov8n_5class_v5c_fast/weights/best.pt"
)
DEFAULT_MODEL_PATH: Path = PROJECT_ROOT / DEFAULT_MODEL_RELATIVE

# Class id -> human-readable name (must match v2 training order)
CLASS_NAMES = {
    0: "person",
    1: "helmet",
    2: "no_helmet",
    3: "vest",
    4: "no_vest",
}


# ---------------------------------------------------------------------------
# Cached singletons
# ---------------------------------------------------------------------------
_model: Optional[Any] = None
_model_error: Optional[str] = None
_model_path_used: Optional[Path] = None


def _try_load(model_path: Path) -> None:
    """Internal: actually import ultralytics and load the weights."""
    global _model, _model_error, _model_path_used

    if not model_path.exists():
        _model = None
        _model_error = f"Model weights not found at: {model_path}"
        _model_path_used = model_path
        return

    try:
        # Import inside the function so importing this module is cheap.
        from ultralytics import YOLO  # type: ignore
        _model = YOLO(str(model_path))
        _model_error = None
        _model_path_used = model_path
    except Exception as exc:  # noqa: BLE001 - we want to surface any error
        _model = None
        _model_error = f"Failed to load YOLO model: {exc}"
        _model_path_used = model_path


def get_model(model_path: Optional[Path] = None) -> Optional[Any]:
    """Return the cached YOLO model, loading it on first call.

    Args:
        model_path: Optional override. If supplied AND different from the
            currently-loaded path, the model is reloaded. Use `None`
            (the default) in production code so the cached instance
            is reused.

    Returns:
        The loaded ultralytics `YOLO` instance, or `None` if loading
        failed (in which case `get_model_status()` will explain why).
    """
    global _model_path_used

    target = Path(model_path) if model_path else DEFAULT_MODEL_PATH

    # First load, or path changed -> (re)load.
    if _model is None or _model_path_used != target:
        _try_load(target)

    return _model


def get_model_status() -> dict:
    """Return a JSON-friendly status dict for `/health` and `/api/model-status`.

    Calling this also triggers a load attempt if the model has not yet
    been loaded, so the first HTTP call to `/health` may take a moment.
    """
    # Trigger lazy load (ignored if already loaded).
    get_model()

    loaded = _model is not None
    return {
        "model_loaded": loaded,
        "model_path": str(_model_path_used or DEFAULT_MODEL_PATH),
        "class_names": CLASS_NAMES,
        "message": "Model loaded successfully" if loaded else (
            _model_error or "Model not loaded"
        ),
    }

"""
Default model weights, shared by the backend, the CLI scripts and evaluation.

Each role is resolved the same way everywhere: the environment variable if set,
otherwise the first candidate file that exists. Importing this module needs no
Supabase settings, so the offline tools can use it.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
RUNS_DIR = PROJECT_ROOT / "ai-model" / "outputs" / "training-runs"

load_dotenv(BACKEND_DIR / ".env")

# Ultralytics pip-installs missing packages (lap, onnx, ...) at runtime unless told
# not to. Servers and edge devices must not install code on their own: fail instead.
os.environ.setdefault("YOLO_AUTOINSTALL", "false")

# Best first. Class ids are looked up by name, so 5-class and 17-class weights
# are interchangeable. Never includes COCO yolov8n.pt: it has no PPE classes.
CANDIDATES = {
    # vest / no_vest
    "PPE_MODEL_PATH": [
        RUNS_DIR / "safevision_yolov8n_5class_v5d_50epochs" / "weights" / "best.pt",
        RUNS_DIR / "safevision_yolov8n_5class_v2" / "weights" / "best.pt",
    ],
    # helmet / no_helmet. v5d_50epochs is the best helmet model documented in
    # train_safevision_v5.py; v1 (17-class) is the older fallback.
    "HELMET_MODEL_PATH": [
        RUNS_DIR / "safevision_yolov8n_5class_v5d_50epochs" / "weights" / "best.pt",
        RUNS_DIR / "safevision_yolov8n_v1" / "weights" / "best.pt",
    ],
    # person. The pose model adds keypoints for head/torso regions; plain
    # yolov8n gives boxes only (box-geometry fallback).
    "PERSON_MODEL_PATH": [
        PROJECT_ROOT / "yolov8n-pose.pt",
        PROJECT_ROOT / "yolov8n.pt",
    ],
}


def resolve(env_name: str) -> Path:
    """Weights path for one role: env var (relative to backend/), else best existing candidate."""
    value = os.getenv(env_name)
    if value:
        p = Path(value)
        return p if p.is_absolute() else (BACKEND_DIR / p).resolve()
    candidates = CANDIDATES[env_name]
    return next((p for p in candidates if p.is_file()), candidates[0])

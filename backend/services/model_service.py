from pathlib import Path
from ultralytics import YOLO

PROJECT_ROOT = Path(__file__).resolve().parents[2]

MODEL_CANDIDATES = [
    PROJECT_ROOT / "ai-model" / "outputs" / "training-runs" / "safevision_yolov8n_5class_v5d_50epochs" / "weights" / "best.pt",
    PROJECT_ROOT / "ai-model" / "outputs" / "training-runs" / "safevision_yolov8n_5class_v2" / "weights" / "best.pt",
    PROJECT_ROOT / "ai-model" / "outputs" / "training-runs" / "safevision_yolov8n_5class_smoke" / "weights" / "best.pt",
    PROJECT_ROOT / "yolov8n.pt",
]

# Select the first candidate that exists, falling back to the first one by default if none are found.
MODEL_PATH = next((c for c in MODEL_CANDIDATES if c.exists()), MODEL_CANDIDATES[0])

# v1 model trained on 17-class construction-safety dataset — used for Hardhat / NO-Hardhat detection
HELMET_MODEL_PATH = (
    PROJECT_ROOT
    / "ai-model"
    / "outputs"
    / "training-runs"
    / "safevision_yolov8n_v1"
    / "weights"
    / "best.pt"
)

model = None
helmet_model = None
person_model = None


def get_model():
    global model

    if model is None:
        print(f"[INFO] Loading YOLO model from: {MODEL_PATH}")
        model = YOLO(str(MODEL_PATH))

    return model


def get_helmet_model():
    global helmet_model

    if helmet_model is None:
        print(f"[INFO] Loading helmet YOLO model from: {HELMET_MODEL_PATH}")
        helmet_model = YOLO(str(HELMET_MODEL_PATH))

    return helmet_model


def get_person_model():
    global person_model

    if person_model is None:
        person_model_path = PROJECT_ROOT / "yolov8n.pt"
        if not person_model_path.exists():
            person_model_path = "yolov8n.pt"
        print(f"[INFO] Loading Person YOLO model from: {person_model_path}")
        person_model = YOLO(str(person_model_path))

    return person_model

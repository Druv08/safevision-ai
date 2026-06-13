from pathlib import Path
from ultralytics import YOLO

PROJECT_ROOT = Path(__file__).resolve().parents[2]

MODEL_PATH = (
    PROJECT_ROOT
    / "ai-model"
    / "outputs"
    / "training-runs"
    / "safevision_yolov8n_5class_v2"
    / "weights"
    / "best.pt"
)

model = None


def get_model():
    global model

    if model is None:
        model = YOLO(str(MODEL_PATH))

    return model
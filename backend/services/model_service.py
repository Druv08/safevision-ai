"""
YOLO model loading.

Weights paths come from config. A missing or checksum-mismatched file raises
ModelUnavailableError (the API turns it into 503). There is no fallback to the
COCO yolov8n weights for PPE classes; yolov8n(-pose) is only the person model.
"""

import hashlib
import logging
from functools import cache
from pathlib import Path

from config import settings
from services.pipeline import Detector, load_yolo
from services.pipeline import model_version as pipeline_model_version

log = logging.getLogger(__name__)


class ModelUnavailableError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def _load(path: Path, expected_sha256: str, what: str, env_name: str):
    if not path.is_file():
        log.error("%s weights not found at %s", what, path)
        raise ModelUnavailableError(f"{what} weights not found ({path.name}); set {env_name}")
    if expected_sha256 and _sha256(path) != expected_sha256:
        log.error("%s weights at %s do not match %s_SHA256", what, path, env_name)
        raise ModelUnavailableError(f"{what} weights checksum mismatch; check {env_name}_SHA256")

    log.info("Loading %s model from %s", what, path)
    return load_yolo(path)  # .pt or .onnx; imports ultralytics (torch) lazily


# functools.cache does not cache exceptions, so a failed load is retried next call.
# Loading is keyed by path, so a helmet model that is also the PPE model loads once.
@cache
def _model(path: Path, sha256: str, what: str, env_name: str):
    return _load(path, sha256, what, env_name)


def get_model():
    """PPE model; used for vest / no_vest."""
    return _model(settings.ppe_model_path, settings.ppe_model_sha256, "PPE", "PPE_MODEL_PATH")


def get_helmet_model():
    """Helmet model (HELMET_MODEL_PATH); used for helmet / no_helmet."""
    return _model(settings.helmet_model_path, settings.helmet_model_sha256, "Helmet", "HELMET_MODEL_PATH")


def get_person_model():
    """Person model: a pose model gives head/torso keypoints; plain yolov8n gives boxes."""
    return _model(settings.person_model_path, settings.person_model_sha256, "Person", "PERSON_MODEL_PATH")


@cache
def get_detector() -> Detector:
    """The shared Detector. Raises ModelUnavailableError if a model lacks a needed class."""
    try:
        return Detector(
            get_model(), get_helmet_model(), get_person_model(),
            ppe_conf=settings.ppe_confidence, person_conf=settings.person_confidence,
        )
    except ValueError as e:  # e.g. helmet weights with no helmet class
        raise ModelUnavailableError(str(e)) from None


def model_version() -> str:
    return pipeline_model_version(settings.ppe_model_path, settings.helmet_model_path, settings.person_model_path)


def model_status() -> dict:
    """Load all models (cached after the first success) and report the outcome."""
    try:
        detector = get_detector()
    except ModelUnavailableError as e:
        return {"loaded": False, "error": str(e)}
    except Exception as e:  # corrupt weights, torch errors, ...
        log.exception("Model loading failed")
        return {"loaded": False, "error": f"model load failed: {type(e).__name__}"}
    return {"loaded": True, "version": model_version(), "pose": detector.uses_pose}

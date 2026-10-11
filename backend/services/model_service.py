"""
YOLO model loading.

Weights paths come from config. A missing or checksum-mismatched file raises
ModelUnavailableError (the API turns it into 503). There is no fallback to the
COCO yolov8n weights for PPE classes; yolov8n is only used as the person model.
"""

import hashlib
import logging
from functools import cache
from pathlib import Path

from config import settings

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

    from ultralytics import YOLO  # imported lazily: pulls in torch

    log.info("Loading %s model from %s", what, path)
    return YOLO(str(path))


# functools.cache does not cache exceptions, so a failed load is retried next call.
@cache
def get_model():
    """5-class PPE model; used for vest / no-vest."""
    return _load(settings.ppe_model_path, settings.ppe_model_sha256, "PPE", "PPE_MODEL_PATH")


@cache
def get_helmet_model():
    """v1 17-class construction-safety model; used for hardhat / no-hardhat."""
    return _load(settings.helmet_model_path, settings.helmet_model_sha256, "Helmet", "HELMET_MODEL_PATH")


@cache
def get_person_model():
    """COCO yolov8n; only class 0 (person) is used."""
    return _load(settings.person_model_path, settings.person_model_sha256, "Person", "PERSON_MODEL_PATH")


def model_version() -> str:
    # Training-run folder names, e.g. "safevision_yolov8n_5class_v2+safevision_yolov8n_v1".
    return "+".join(p.parent.parent.name for p in (settings.ppe_model_path, settings.helmet_model_path))


def model_status() -> dict:
    """Load all models (cached after the first success) and report the outcome."""
    try:
        get_model()
        get_helmet_model()
        get_person_model()
    except ModelUnavailableError as e:
        return {"loaded": False, "error": str(e)}
    except Exception as e:  # corrupt weights, torch errors, ...
        log.exception("Model loading failed")
        return {"loaded": False, "error": f"model load failed: {type(e).__name__}"}
    return {"loaded": True, "version": model_version()}

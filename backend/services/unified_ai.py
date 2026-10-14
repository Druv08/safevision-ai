"""
Adapter between the backend pipeline and the shared SafeVision engine
(ai-model/inference/safevision_engine.py), the live camera's AI.

The engine decides each worker's helmet and vest (worn-vs-held helmet
validation, colour assist, helmet smoothing, held-hard-hat-is-not-a-vest,
pose + COCO person fallback). The backend Pipeline keeps doing what it already
did around that: tracking, zones, the violation time window, evidence and
observations.

Models load once per process (one engine). Each UnifiedDetector owns its own
stream state, so an image, a video, a webcam session or a camera never shares
helmet smoothing with another.
"""

import os
import sys
from functools import cache
from pathlib import Path

from config import settings
from services.pipeline import WORN, Det, FrameDets, Person, load_yolo
from weights import PROJECT_ROOT

# Where safevision_engine.py lives; override when the backend runs without the repo (e.g. a container).
INFERENCE_DIR = Path(os.getenv("SAFEVISION_ENGINE_DIR") or PROJECT_ROOT / "ai-model" / "inference")


def _engine_module():
    if str(INFERENCE_DIR) not in sys.path:
        sys.path.insert(0, str(INFERENCE_DIR))
    import safevision_engine

    return safevision_engine


@cache
def get_engine():
    """The process-wide engine with its models loaded. Raises FileNotFoundError / ValueError."""
    se = _engine_module()
    engine = se.SafeVisionEngine(
        settings.ppe_model_path, settings.person_model_path, settings.fallback_person_model_path, loader=load_yolo,
    ).load_models()
    if getattr(engine.pose, "task", None) != "pose":
        raise ValueError(f"unified AI needs a pose model as PERSON_MODEL_PATH ({settings.person_model_path.name})")
    return engine


class UnifiedDetector:
    """Detector-compatible callable: frame -> FrameDets with the engine's per-worker decisions."""

    uses_pose = True

    def __init__(self, engine):
        self.engine = engine
        self.state = engine.new_state()
        self.last = None  # the engine's last EngineResult (per-worker details for the API)

    def __call__(self, frame) -> FrameDets:
        r = self.last = self.engine.process_frame(frame, state=self.state)
        out = FrameDets(decisions=[])
        for w in r.workers:
            out.persons.append(Person(w.box, w.conf, w.keypoints))
            # A missing item's evidence is the worker's own box (head / torso region) and confidence.
            out.decisions.append({
                "helmet": (w.helmet, Det(w.helmet_box, w.helmet_conf if w.helmet == WORN else w.conf)),
                "vest": (w.vest, Det(w.vest_box, w.vest_conf if w.vest == WORN else w.conf)),
            })
        return out

"""Single-image detection: one pass of the shared pipeline (services/pipeline.py)."""

from services.model_service import get_detector, model_version
from services.pipeline import Pipeline, PipelineConfig, detections_for_api
from services.privacy import redactor
from services.violations_service import record_observations, save_episode


def detect_image(frame, source="image"):
    """
    A still image has no duration, so the time window does not apply: every
    person missing an item is one violation (window 0). Each image is processed
    on its own, so there are no track IDs across images.
    """
    pipe = Pipeline(get_detector(), PipelineConfig(window_s=0.0), redact=redactor())
    result = pipe.process(frame, 0.0)
    episodes, observations = pipe.finish()

    version = model_version()
    for ep in episodes:
        save_episode(ep, source, version, tracked=False)
    record_observations(observations, source, version, tracked=False)
    return detections_for_api(result.labelled), result.summary

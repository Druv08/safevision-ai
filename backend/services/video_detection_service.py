"""Video detection: the shared pipeline with person tracking and the violation time window."""

from config import settings
from services.model_service import get_detector, model_version
from services.pipeline import Pipeline, PipelineConfig, VideoDecodeError, compliance, probe_video, run_video
from services.privacy import redactor
from services.tracker import PersonTracker
from services.violations_service import record_observations, save_episode

__all__ = ["VideoDecodeError", "detect_video"]


def detect_video(video_path, source="video"):
    probe_video(video_path)  # a broken upload is a 422 even when the models are unavailable
    pipe = Pipeline(
        get_detector(),
        PipelineConfig(window_s=settings.violation_window_seconds, clear_s=settings.violation_clear_seconds),
        tracker=PersonTracker(settings.tracker),
        redact=redactor(),
    )
    run = run_video(video_path, pipe)

    version = model_version()
    for ep in run.episodes:
        save_episode(ep, source, version)
    record_observations(run.observations, source, version)

    counts = {"no_helmet": 0, "no_vest": 0}
    for ep in run.episodes:
        counts[ep.type] += 1
    return {
        "status": "processed",
        "message": "Video analyzed successfully",
        "frames_processed": run.frames,
        "total_violations": len(run.episodes),
        "helmet_violations": counts["no_helmet"],
        "vest_violations": counts["no_vest"],
        "duration_seconds": round(run.duration_s, 2),
        "people_tracked": len({o.track_id for o in run.observations}),
        "compliance": compliance(run.observations),
        # `time` is when the alert was raised (start + window), so the player jumps to the evidence frame.
        "events": [
            {
                "type": ep.type,
                "time": round(ep.alert_s, 2),
                "start": round(ep.start_s, 2),
                "end": round(ep.end_s, 2),
                "track_id": ep.track_id,
                "confidence": round(ep.confidence, 3),
            }
            for ep in run.episodes
        ],
    }

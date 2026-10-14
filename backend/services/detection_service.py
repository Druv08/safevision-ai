"""Single-image detection: one pass of the shared pipeline (services/pipeline.py).

Browser-webcam frames sent with a session id are instead run through one
stateful pipeline per session (tracking, helmet smoothing, the violation time
window), like a camera stream, so one persistent violation is one record and
not one per frame.
"""

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from config import settings
from services.model_service import get_detector, model_version
from services.pipeline import Pipeline, PipelineConfig, detections_for_api
from services.privacy import redactor
from services.tracker import PersonTracker
from services.violations_service import record_observations, save_episode, set_episode_end

SESSION_IDLE_S = 60.0  # a webcam session not heard from this long is closed
MAX_SESSIONS = 32


def _response(pipe, result) -> dict:
    out = {"detections": detections_for_api(result.labelled), "summary": result.summary}
    last = getattr(pipe.detect, "last", None)  # unified engine: per-worker details
    if last is not None:
        workers = last.to_dict()["workers"]
        for w, st in zip(workers, result.statuses, strict=True):
            w["track_id"] = st.person.track_id
            w["violations"] = [v for v, item in (("no_helmet", "helmet"), ("no_vest", "vest")) if st.missing(item)]
        out["workers"] = workers
        out["counts"] = dict(last.counts)
        out["inference_ms"] = round(last.inference_ms, 1)
    return out


def analyze_image(frame, source="image") -> dict:
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
    return _response(pipe, result)


def detect_image(frame, source="image"):
    r = analyze_image(frame, source)
    return r["detections"], r["summary"]


# ---------------------------------------------------------------------------
# Browser webcam sessions
# ---------------------------------------------------------------------------
@dataclass
class _Session:
    pipe: Pipeline
    t0: float = field(default_factory=time.monotonic)
    wall0: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_used: float = field(default_factory=time.monotonic)
    rows: dict = field(default_factory=dict)  # id(Episode) -> violation row id
    lock: threading.Lock = field(default_factory=threading.Lock)


_sessions: dict[tuple[str, str], _Session] = {}
_sessions_lock = threading.Lock()


def _close(s: _Session, closed, observations) -> None:
    version = model_version()
    for ep in closed:
        row_id = s.rows.pop(id(ep), None)
        if row_id:
            set_episode_end(row_id, ep.end_s, s.wall0 + timedelta(seconds=ep.end_s))
    if observations:
        record_observations(observations, "camera", version)


def _expire(now: float) -> None:
    """Close idle sessions, and the oldest ones while at capacity (room for one more)."""
    with _sessions_lock:
        oldest_first = sorted(_sessions, key=lambda k: _sessions[k].last_used)
        gone = []
        for k in oldest_first:
            if now - _sessions[k].last_used > SESSION_IDLE_S or len(_sessions) >= MAX_SESSIONS:
                gone.append(_sessions.pop(k))
    for s in gone:
        with s.lock:
            _close(s, *s.pipe.finish())


def analyze_camera_frame(frame, user_id: str, session_id: str) -> dict:
    """One frame of a browser-webcam session (source 'camera')."""
    now = time.monotonic()
    _expire(now)
    key = (user_id, session_id)
    with _sessions_lock:
        s = _sessions.get(key)
        if s is None:
            pipe = Pipeline(
                get_detector(),
                PipelineConfig(window_s=settings.violation_window_seconds, clear_s=settings.violation_clear_seconds),
                tracker=PersonTracker(settings.tracker),
                redact=redactor(),
            )
            s = _sessions[key] = _Session(pipe)
        s.last_used = now
    with s.lock:
        result = s.pipe.process(frame, now - s.t0)
        version = model_version()
        for ep in result.opened:
            row = save_episode(ep, "camera", version, started_at=s.wall0 + timedelta(seconds=ep.start_s))
            s.rows[id(ep)] = row["id"]
        _close(s, result.closed, result.observations)
        return _response(s.pipe, result)

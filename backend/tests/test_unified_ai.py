"""The backend on top of the unified engine: per-worker decisions in, Prem's pipeline around them.

The engine itself is faked (its rules are tested in ai-model/tests); these check
the adapter, the API shape, per-session webcam state and the error path.
"""

import io

import cv2
import numpy as np
import pytest
from fake_supabase import VIEWER

from services import detection_service, model_service
from services.pipeline import HELMET_ID, NO_HELMET_ID, NO_VEST_ID, PERSON_ID, VEST_ID, Pipeline, PipelineConfig
from services.unified_ai import INFERENCE_DIR, UnifiedDetector


def _engine_mod():
    import sys

    sys.path.insert(0, str(INFERENCE_DIR))
    import safevision_engine

    return safevision_engine


class FakeEngine:
    """Returns scripted per-worker results; records the state object it was given."""

    def __init__(self, frames):
        self.se = _engine_mod()
        self.frames = list(frames)  # each: list of (box, helmet_worn, vest_worn)
        self.states = []

    def new_state(self):
        return object()

    def process_frame(self, frame, state=None, **_):
        self.states.append(state)
        spec = self.frames.pop(0) if len(self.frames) > 1 else self.frames[0]
        se = self.se
        workers = []
        for box, h, v in spec:
            x1, y1, x2, y2 = box
            workers.append(se.WorkerResult(
                box, 0.9, "pose",
                helmet=se.WORN if h else se.MISSING, helmet_box=(x1, y1, x2, y1 + 40), helmet_conf=0.8 if h else 0.0,
                vest=se.WORN if v else se.MISSING, vest_box=(x1, y1 + 60, x2, y1 + 160), vest_conf=0.7 if v else 0.0,
            ))
        n, nh, nv = len(workers), sum(w.helmet == se.WORN for w in workers), sum(w.vest == se.WORN for w in workers)
        counts = {"workers": n, "helmet": nh, "no_helmet": n - nh, "vest": nv, "no_vest": n - nv}
        return se.EngineResult(workers, counts, dict(counts), [], inference_ms=5.0)


A = (100, 50, 200, 350)
B = (300, 50, 400, 350)
FRAME = np.zeros((480, 640, 3), np.uint8)


@pytest.mark.parametrize("helmet, vest, expected", [
    (True, True, (1, 0, 1, 0)),     # A: helmet + vest
    (True, False, (1, 0, 0, 1)),    # B: helmet only
    (False, True, (0, 1, 1, 0)),    # C: vest only
    (False, False, (0, 1, 0, 1)),   # D: neither (incl. a rejected held helmet)
])
def test_single_worker_summary(helmet, vest, expected):
    pipe = Pipeline(UnifiedDetector(FakeEngine([[(A, helmet, vest)]])), PipelineConfig(window_s=0.0))
    s = pipe.process(FRAME, 0.0).summary
    assert s["total_persons"] == 1
    assert (s["helmet_worn"], s["no_helmet"], s["vest_worn"], s["no_vest"]) == expected


def test_no_worker_is_all_zero():
    s = Pipeline(UnifiedDetector(FakeEngine([[]])), PipelineConfig(window_s=0.0)).process(FRAME, 0.0).summary
    assert (s["total_persons"], s["helmet_worn"], s["no_helmet"], s["vest_worn"], s["no_vest"]) == (0, 0, 0, 0, 0)


def test_each_worker_gets_its_own_boxes_and_violations():
    pipe = Pipeline(UnifiedDetector(FakeEngine([[(A, True, True), (B, False, False)]])), PipelineConfig(window_s=0.0))
    result = pipe.process(FRAME, 0.0)
    ids = sorted(cid for cid, _ in result.labelled)
    assert ids == sorted([PERSON_ID, PERSON_ID, HELMET_ID, VEST_ID, NO_HELMET_ID, NO_VEST_ID])
    assert [st.violating for st in result.statuses] == [False, True]
    episodes, _ = pipe.finish()
    assert sorted(e.type for e in episodes) == ["no_helmet", "no_vest"]
    assert all(e.box == B for e in episodes)


def test_each_detector_has_its_own_stream_state():
    engine = FakeEngine([[(A, True, True)]])
    d1, d2 = UnifiedDetector(engine), UnifiedDetector(engine)
    d1(FRAME), d2(FRAME), d1(FRAME)
    assert engine.states[0] is engine.states[2] is d1.state and engine.states[1] is d2.state
    assert d1.state is not d2.state


def test_image_response_adds_workers_and_counts(monkeypatch, sb):
    engine = FakeEngine([[(A, True, False)]])
    monkeypatch.setattr(detection_service, "get_detector", lambda: UnifiedDetector(engine))
    r = detection_service.analyze_image(FRAME, "image")
    assert r["summary"]["no_vest"] == 1 and r["counts"] == {"workers": 1, "helmet": 1, "no_helmet": 0,
                                                           "vest": 0, "no_vest": 1}
    assert r["workers"][0]["violations"] == ["no_vest"]
    assert {d["class_id"] for d in r["detections"]} == {PERSON_ID, HELMET_ID, NO_VEST_ID}


@pytest.mark.parametrize("gap_s", [1, 3])  # the browser sends a frame every 3 s
def test_webcam_session_logs_one_violation_not_one_per_frame(monkeypatch, gap_s):
    saved = []
    engine = FakeEngine([[(A, True, False)]])
    monkeypatch.setattr(detection_service, "get_detector", lambda: UnifiedDetector(engine))
    monkeypatch.setattr(detection_service, "save_episode", lambda ep, *a, **k: saved.append(ep) or {"id": "row"})
    monkeypatch.setattr(detection_service, "set_episode_end", lambda *a, **k: None)
    monkeypatch.setattr(detection_service, "record_observations", lambda *a, **k: None)
    clock = iter(float(t) for t in range(0, 10000, gap_s))
    monkeypatch.setattr(detection_service.time, "monotonic", lambda: next(clock))
    detection_service._sessions.clear()

    for _ in range(12):  # the worker never wears a vest
        r = detection_service.analyze_camera_frame(FRAME, "user-1", "session-abc")
        assert r["counts"]["no_vest"] == 1
    assert [e.type for e in saved] == ["no_vest"]
    assert len({id(s) for s in engine.states}) == 1  # one smoothing state for the whole session

    detection_service.analyze_camera_frame(FRAME, "user-1", "session-xyz")
    assert len({id(s) for s in engine.states}) == 2  # a new session starts fresh
    detection_service._sessions.clear()


def test_unified_engine_failure_is_a_model_error_not_a_silent_fallback():
    assert model_service.settings.use_unified_ai  # the default
    status = model_service.model_status()  # test weights do not exist
    assert status["loaded"] is False and "SafeVision AI unavailable" in status["error"]


def test_detect_image_route_validates_the_session_id(client):
    ok, buf = cv2.imencode(".jpg", FRAME)
    files = {"image": ("f.jpg", io.BytesIO(buf.tobytes()), "image/jpeg")}
    r = client.post("/detect-image", files=files, data={"source": "camera", "session": "bad id!"},
                    headers=VIEWER)
    assert r.status_code == 422

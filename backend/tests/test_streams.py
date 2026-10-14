"""StreamWorker with a fake capture and clock: sampling, reconnect, persistence, stop (no network, no weights)."""

import threading
import time
from datetime import datetime, timezone

import numpy as np

from services.model_service import ModelUnavailableError
from services.pipeline import Det, FrameDets, Person, PipelineConfig
from services.stream_service import StreamWorker
from services.zones import Zone, ZoneMap

FRAME = np.zeros((480, 640, 3), np.uint8)
WALL0 = datetime(2026, 10, 12, 9, 0, tzinfo=timezone.utc)


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


class FakeCapture:
    """A stream of `seconds` at `fps`; grab() advances the shared clock by one frame period."""

    def __init__(self, clock, seconds, fps=30, opened=True):
        self.clock, self.left, self.period, self.opened = clock, int(seconds * fps), 1 / fps, opened
        self.retrieved = 0

    def isOpened(self):  # noqa: N802 (OpenCV's name)
        return self.opened

    def grab(self):
        if self.left <= 0:
            return False  # end of stream / read timeout
        time.sleep(0.002)  # a little real pacing, so the analysis thread gets to run
        self.left -= 1
        self.clock.t += self.period
        return True

    def retrieve(self):
        self.retrieved += 1
        return True, FRAME

    def release(self):
        pass


class Captures:
    """open_capture(): hands out the given captures in order, then unopenable ones."""

    def __init__(self, clock, *caps):
        self.clock, self.caps, self.urls = clock, list(caps), []

    def __call__(self, url):
        self.urls.append(url)
        return self.caps.pop(0) if self.caps else FakeCapture(self.clock, 0, opened=False)


class Sink:
    def __init__(self, fail_opened=False):
        self.opened, self.closed, self.observations, self.fail_opened = [], [], [], fail_opened

    def opened_(self, ep, started_at):
        if self.fail_opened:
            raise RuntimeError("database down")
        self.opened.append((ep.type, ep.track_id, started_at))
        return f"row-{len(self.opened)}"

    def closed_(self, row_id, ep, ended_at):
        self.closed.append((row_id, ep.type, ended_at))

    def observations_(self, obs):
        self.observations += obs


class SinkAdapter:
    def __init__(self, sink):
        self.opened, self.closed, self.observations = sink.opened_, sink.closed_, sink.observations_


def bare_head(frame):
    """Detector stand-in: one person, no helmet, vest worn, feet at (0.25, 0.8)."""
    return FrameDets([Person((110, 50, 210, 384), 0.9)], no_helmet=[Det((140, 45, 180, 90), 0.7)],
                     vest=[Det((120, 130, 200, 280), 0.9)])


class OneTrack:
    def update(self, persons, frame):
        for p in persons:
            p.track_id = 1


def make_worker(clock, captures, sink, detector=lambda: bare_head, zones=None, fps=5.0):
    return StreamWorker(
        "cam-1", "rtsp://user:pw@cam.local/live", fps, zones or ZoneMap([], "both"),
        sink=SinkAdapter(sink), detector_factory=detector, tracker_factory=OneTrack,
        open_capture=captures, clock=clock, wall=lambda: WALL0,
        config=PipelineConfig(window_s=2.0, clear_s=1.0), backoff_s=0.01,
    )


def wait_for(cond, timeout=5.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.01)
    return False


def test_samples_5_fps_from_a_30_fps_stream_and_logs_one_episode():
    clock, sink = Clock(), Sink()
    cap = FakeCapture(clock, seconds=4)
    w = make_worker(clock, Captures(clock, cap), sink)
    w.start()
    assert wait_for(lambda: w.status.reconnects >= 1)  # stream ended -> trying to reconnect
    w.stop()

    assert w.status.frames_read == 120  # every frame grabbed...
    assert 12 <= w.status.frames_analyzed <= 21  # ...at most 5 fps over 4 s analysed
    assert cap.retrieved == w.status.frames_analyzed  # only analysed frames are decoded
    [(vtype, track_id, started_at)] = sink.opened
    assert (vtype, track_id) == ("no_helmet", 1)
    assert 0 <= (started_at - WALL0).total_seconds() < 0.1  # wall time of the first violating frame
    assert len(sink.closed) == 1 and sink.closed[0][0] == "row-1"  # closed on stop
    assert {o.item: o.outcome for o in sink.observations} == {"helmet": "violation", "vest": "compliant"}
    assert w.status.state == "stopped" and w.status.alerts == 1


def test_reconnects_with_backoff_and_keeps_the_url_secret():
    clock, sink = Clock(), Sink()
    opens = Captures(clock, FakeCapture(clock, 0, opened=False), FakeCapture(clock, 0, opened=False),
                     FakeCapture(clock, seconds=1))
    w = make_worker(clock, opens, sink)
    w.start()
    assert wait_for(lambda: w.status.frames_analyzed > 0)
    assert wait_for(lambda: w.status.reconnects >= 3)
    w.stop()
    assert opens.urls[0] == "rtsp://user:pw@cam.local/live"  # credentials reach OpenCV...
    assert "pw" not in str(w.status) and "user" not in str(w.status)  # ...but never the status
    assert "could not open the stream" in w.status.last_error or w.status.state == "stopped"


def test_open_errors_are_redacted_in_status():
    clock = Clock()

    def explode(url):
        raise OSError(f"cannot connect to {url}")

    w = make_worker(clock, explode, Sink())
    w.start()
    assert wait_for(lambda: w.status.last_error is not None)
    w.stop()
    assert "pw" not in w.status.last_error and "***@cam.local" in w.status.last_error


def test_model_unavailable_is_an_error_state_and_retried():
    clock, calls = Clock(), []

    def no_model():
        calls.append(1)
        raise ModelUnavailableError("PPE weights not found")

    w = make_worker(clock, Captures(clock), Sink(), detector=no_model)
    w.start()
    assert wait_for(lambda: len(calls) >= 3)
    assert w.status.state == "error" and "weights not found" in w.status.last_error
    w.stop()


def test_database_errors_do_not_stop_the_stream():
    clock, sink = Clock(), Sink(fail_opened=True)
    w = make_worker(clock, Captures(clock, FakeCapture(clock, seconds=4)), sink)
    w.start()
    assert wait_for(lambda: w.status.reconnects >= 1)
    w.stop()
    assert w.status.persist_errors == 1 and w.status.frames_analyzed >= 12


def test_zone_change_applies_to_the_running_pipeline():
    clock, sink = Clock(), Sink()
    gate = threading.Event()

    class SlowCapture(FakeCapture):
        def grab(self):
            if self.left == 120:  # 4 s before the end: wait until the test has changed the zones
                gate.wait(5)
            return super().grab()

    none_everywhere = ZoneMap([Zone("z1", "all", "none", ((0, 0), (1, 0), (1, 1), (0, 1)))], "both")
    w = make_worker(clock, Captures(clock, SlowCapture(clock, seconds=6)), sink, zones=none_everywhere)
    w.start()
    assert wait_for(lambda: w.status.frames_analyzed >= 9)
    assert sink.opened == []  # helmet not required anywhere so far
    w.set_zones(ZoneMap([], "helmet"))
    gate.set()
    assert wait_for(lambda: w.status.reconnects >= 1)
    w.stop()
    assert [t for t, _, _ in sink.opened] == ["no_helmet"]


class LiveCapture:
    """A real-time 30 fps source with a buffer: grab() returns the next buffered frame
    at once if the source is ahead, else waits for it (like RTSP / HTTP over TCP)."""

    def __init__(self, seconds):
        self.start, self.n, self.total = time.monotonic(), 0, int(seconds * 30)

    def live_index(self):
        return int((time.monotonic() - self.start) * 30)

    def isOpened(self):  # noqa: N802
        return True

    def grab(self):
        if self.n >= self.total:
            return False
        wait = self.start + self.n / 30 - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self.n += 1
        return True

    def retrieve(self):
        return True, np.full((48, 64, 3), (self.n - 1) % 256, np.uint8)

    def release(self):
        pass


def test_slow_analysis_still_sees_the_live_picture():
    """Analysis (0.3 s) is slower than the sampling interval (0.2 s): the reader keeps
    draining the stream, so each analysed frame is within a few frames of live."""
    cap = LiveCapture(seconds=3)
    lags = []

    def slow_detector(frame):
        lags.append(cap.live_index() - int(frame[0, 0, 0]))
        time.sleep(0.3)
        return FrameDets()

    w = StreamWorker("cam-1", "rtsp://cam.local/live", 5.0, ZoneMap([], "both"), sink=SinkAdapter(Sink()),
                     detector_factory=lambda: slow_detector, tracker_factory=OneTrack,
                     open_capture=Captures(None, cap), backoff_s=0.01)
    w.start()
    assert wait_for(lambda: w.status.reconnects >= 1, timeout=10)
    w.stop()
    assert len(lags) >= 5
    assert max(lags) <= 3, lags  # at most 0.1 s behind live
    assert w.status.frames_read == 90

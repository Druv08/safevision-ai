"""
Network camera (RTSP) ingestion: one background thread per running camera.

Each worker
  * opens the stream with OpenCV / FFMPEG (RTSP over TCP, 10 s open and read timeouts),
  * grabs every frame, so the decoder never falls behind real time, but decodes
    and analyses only `sample_fps` frames per second (default 5),
  * runs them through its own Pipeline (tracker, zones, time window); all
    workers share one Detector, behind a lock,
  * saves a violation row when an episode's alert fires and records the end
    time when it closes,
  * reconnects with exponential backoff (1 s doubling to 30 s) when the stream
    fails or stalls, and keeps a status for the API.

Credentials: the worker is given the full URL (with decrypted credentials) and
never logs it or puts it in its status; errors pass through `redact()`.

ponytail: workers are threads in the API process. Run the backend with a single
uvicorn worker, or each process would read every camera. Move to a separate
ingest service when you need more cameras than one machine can analyse.
"""

import logging
import os
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone

import cv2

from config import settings
from services import cameras_service
from services.model_service import get_detector, model_version
from services.pipeline import Pipeline, PipelineConfig
from services.privacy import redactor
from services.tracker import PersonTracker
from services.violations_service import record_observations, save_episode, set_episode_end
from services.zones import ZoneMap, zones_from_rows

log = logging.getLogger(__name__)

# RTSP over TCP: no lost UDP packets, works through NAT. Must be set before the first open.
os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")
TIMEOUT_MS = 10_000
MAX_BACKOFF_S = 30.0

# One inference at a time across all cameras: YOLO models are not thread-safe.
# ponytail: global lock, so N cameras share one model's throughput; give each
# worker its own model instance (or a GPU batcher) when that is the bottleneck.
_infer_lock = threading.Lock()


def open_capture(url: str):
    return cv2.VideoCapture(
        url, cv2.CAP_FFMPEG, [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, TIMEOUT_MS, cv2.CAP_PROP_READ_TIMEOUT_MSEC, TIMEOUT_MS]
    )


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class CameraStatus:
    state: str = "stopped"  # stopped | connecting | running | reconnecting | error
    since: str | None = None
    last_frame_at: str | None = None
    frames_read: int = 0
    frames_analyzed: int = 0
    analyzed_fps: float = 0.0
    reconnects: int = 0
    alerts: int = 0
    persist_errors: int = 0
    resolution: list | None = None
    last_error: str | None = None


class DatabaseSink:
    """Where a worker's episodes and observations go (violations_service, source 'camera')."""

    def __init__(self, camera_id: str):
        self.camera_id = camera_id
        self.version = model_version()

    def opened(self, episode, started_at: datetime) -> str:
        row = save_episode(episode, "camera", self.version, camera_id=self.camera_id, started_at=started_at)
        return row["id"]

    def closed(self, row_id: str, episode, ended_at: datetime) -> None:
        set_episode_end(row_id, episode.end_s, ended_at)

    def observations(self, observations) -> None:
        record_observations(observations, "camera", self.version, camera_id=self.camera_id)


class StreamWorker:
    def __init__(self, camera_id: str, url: str, sample_fps: float, zones: ZoneMap, *, sink=None,
                 detector_factory=get_detector, tracker_factory=None, open_capture=open_capture,
                 clock=time.monotonic, wall=_now, config: PipelineConfig | None = None, backoff_s: float = 1.0):
        self.camera_id = camera_id
        self._url = url  # contains credentials: never log or expose
        self.sample_fps = sample_fps
        self.zones = zones
        self.sink = sink or DatabaseSink(camera_id)
        self.detector_factory = detector_factory
        self.tracker_factory = tracker_factory or (lambda: PersonTracker(settings.tracker))
        self.open_capture = open_capture
        self.clock, self.wall = clock, wall
        self.config = config or PipelineConfig(
            window_s=settings.violation_window_seconds, clear_s=settings.violation_clear_seconds
        )
        self.backoff_s = backoff_s
        self.status = CameraStatus()
        self.pipeline: Pipeline | None = None
        self._rows: dict[int, str] = {}  # id(episode) -> violation row id
        self._latest = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name=f"camera-{camera_id[:8]}", daemon=True)

    # -- control ------------------------------------------------------------
    def start(self) -> None:
        self._thread.start()

    def stop(self, timeout: float = TIMEOUT_MS / 1000 + 5) -> None:
        self._stop.set()
        if self._thread.is_alive() and threading.current_thread() is not self._thread:
            self._thread.join(timeout)

    @property
    def alive(self) -> bool:
        return self._thread.is_alive()

    def set_zones(self, zones: ZoneMap) -> None:
        self.zones = zones
        if self.pipeline is not None:
            self.pipeline.zones = zones  # applies from the next frame

    def latest_frame(self):
        with self._lock:
            return None if self._latest is None else self._latest.copy()

    # -- internals ----------------------------------------------------------
    def _set(self, state: str, error: str | None = None) -> None:
        if self.status.state != state:
            self.status.since = self.wall().isoformat()
        self.status.state = state
        if error is not None:
            self.status.last_error = cameras_service.redact(error)

    def _persist(self, fn, *args):
        try:
            return fn(*args)
        except Exception:
            self.status.persist_errors += 1
            log.exception("camera %s: could not save a result", self.camera_id)
            return None

    def _handle(self, result, wall0: datetime) -> None:
        for ep in result.opened:
            self.status.alerts += 1
            row_id = self._persist(self.sink.opened, ep, wall0 + timedelta(seconds=ep.start_s))
            if row_id:
                self._rows[id(ep)] = row_id
        for ep in result.closed:
            row_id = self._rows.pop(id(ep), None)
            if row_id:
                self._persist(self.sink.closed, row_id, ep, wall0 + timedelta(seconds=ep.end_s))
        if result.observations:
            self._persist(self.sink.observations, result.observations)

    def _run(self) -> None:
        backoff, first = self.backoff_s, True
        t0, wall0 = self.clock(), self.wall()
        while not self._stop.is_set():
            self._set("connecting" if first else "reconnecting")
            first = False
            cap = None
            try:
                if self.pipeline is None:
                    self.pipeline = Pipeline(self.detector_factory(), self.config, self.tracker_factory(), self.zones,
                                             redact=redactor())
                cap = self.open_capture(self._url)
                if cap is None or not cap.isOpened():
                    raise ConnectionError("could not open the stream (check the URL, credentials and network)")
                self._set("running")
                self.status.last_error = None
                backoff = self.backoff_s
                self._read(cap, t0, wall0)
            except Exception as e:  # stream failures, model unavailable, ...
                self._set("error" if self.pipeline is None else "reconnecting", f"{type(e).__name__}: {e}")
                log.warning("camera %s: %s", self.camera_id, self.status.last_error)
            finally:
                if cap is not None:
                    cap.release()
            if not self._stop.is_set():
                self.status.reconnects += 1
                self._stop.wait(backoff)
                backoff = min(backoff * 2, max(MAX_BACKOFF_S, self.backoff_s))

        if self.pipeline is not None:  # close open episodes, report everyone still in view
            closed, observations = self.pipeline.finish()
            for ep in closed:
                row_id = self._rows.pop(id(ep), None)
                if row_id:
                    self._persist(self.sink.closed, row_id, ep, wall0 + timedelta(seconds=ep.end_s))
            if observations:
                self._persist(self.sink.observations, observations)
        self._set("stopped")

    def _read(self, cap, t0: float, wall0: datetime) -> None:
        """
        A reader thread grabs every frame as it arrives, so nothing queues up in
        the network buffer; this loop decodes and analyses only the newest frame,
        at most `sample_fps` times a second. Without the split, a worker waiting
        for the shared model would stop reading and fall further and further
        behind the live picture.
        """
        cap_lock = threading.Lock()  # grab() and retrieve() must not run at once
        fresh, failed = threading.Event(), threading.Event()

        def reader():
            while not self._stop.is_set() and not failed.is_set():
                with cap_lock:
                    ok = cap.grab()
                if not ok:  # end of stream, or no data within the read timeout
                    failed.set()
                else:
                    self.status.frames_read += 1
                fresh.set()

        thread = threading.Thread(target=reader, name=f"{self._thread.name}-reader", daemon=True)
        thread.start()
        interval = 1.0 / self.sample_fps
        next_at = last_at = self.clock()
        try:
            while not self._stop.is_set():
                if not fresh.wait(0.5):
                    continue
                fresh.clear()
                if failed.is_set():
                    raise ConnectionError("stream ended or stalled")
                now = self.clock()
                if now < next_at:
                    continue  # grabbed, not decoded
                with cap_lock:
                    ok, frame = cap.retrieve()  # the newest grabbed frame
                if not ok or frame is None:
                    continue
                next_at = now + interval
                with _infer_lock:
                    result = self.pipeline.process(frame, now - t0)
                self._handle(result, wall0)
                with self._lock:
                    self._latest = frame
                s = self.status
                if s.frames_analyzed and now > last_at:  # moving average of the real analysis rate
                    s.analyzed_fps = round(0.8 * s.analyzed_fps + 0.2 / (now - last_at), 2)
                last_at = now
                s.frames_analyzed += 1
                s.resolution = [frame.shape[1], frame.shape[0]]
                s.last_frame_at = self.wall().isoformat()
        finally:
            failed.set()
            thread.join(TIMEOUT_MS / 1000 + 1)  # the capture is released after this returns


# ---------------------------------------------------------------------------
# Manager: the running workers of this process
# ---------------------------------------------------------------------------
class StreamManager:
    def __init__(self, worker_cls=StreamWorker):
        self.worker_cls = worker_cls
        self.workers: dict[str, StreamWorker] = {}
        self.start_errors: dict[str, str] = {}  # why a camera could not be started at all
        self._lock = threading.Lock()

    def start(self, camera: dict, zone_rows: list[dict], **worker_kwargs) -> None:
        """Start (or restart, to pick up new settings) the worker for one camera."""
        self.stop(camera["id"])
        try:
            url = cameras_service.stream_url(camera)  # raises CredentialsError if it cannot decrypt
            zones = ZoneMap(zones_from_rows(zone_rows), camera["default_policy"])
        except Exception as e:
            self.start_errors[camera["id"]] = cameras_service.redact(str(e))
            raise
        self.start_errors.pop(camera["id"], None)
        worker = self.worker_cls(camera["id"], url, camera["sample_fps"], zones, **worker_kwargs)
        with self._lock:
            self.workers[camera["id"]] = worker
        worker.start()
        log.info("camera %s (%s) started at %s fps", camera["id"], camera["name"], camera["sample_fps"])

    def stop(self, camera_id: str) -> None:
        self.start_errors.pop(camera_id, None)
        with self._lock:
            worker = self.workers.pop(camera_id, None)
        if worker is not None:
            worker.stop()

    def stop_all(self) -> None:
        for camera_id in list(self.workers):
            self.stop(camera_id)

    def running(self, camera_id: str) -> bool:
        w = self.workers.get(camera_id)
        return w is not None and w.alive

    def set_zones(self, camera_id: str, zone_rows: list[dict], default_policy: str) -> None:
        w = self.workers.get(camera_id)
        if w is not None:
            w.set_zones(ZoneMap(zones_from_rows(zone_rows), default_policy))

    def status(self, camera_id: str) -> dict:
        w = self.workers.get(camera_id)
        if w is not None:
            return asdict(w.status)
        if camera_id in self.start_errors:
            return asdict(CameraStatus(state="error", last_error=self.start_errors[camera_id]))
        return asdict(CameraStatus())

    def snapshot(self, camera_id: str):
        w = self.workers.get(camera_id)
        return w.latest_frame() if w is not None else None


manager = StreamManager()


def grab_frame(camera: dict):
    """One frame from a camera that is not running (for the zone editor). None if unreachable."""
    cap = open_capture(cameras_service.stream_url(camera))
    try:
        ok, frame = cap.read() if cap.isOpened() else (False, None)
        return frame if ok else None
    finally:
        cap.release()


def start_enabled_cameras() -> None:
    """At startup: start every camera marked enabled. A failing camera does not stop the others."""
    for camera in cameras_service.list_cameras():
        if camera["enabled"]:
            try:
                manager.start(camera, cameras_service.list_zones(camera["id"]))
            except Exception as e:
                log.error("camera %s not started: %s", camera["id"], cameras_service.redact(str(e)))

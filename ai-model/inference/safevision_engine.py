"""
SafeVision shared inference engine.

One importable home for the PPE decision logic of the standalone live camera
(video_detection.py), so the backend (image, video, browser webcam, RTSP) runs
the same AI as the camera instead of a second implementation.

video_detection.py is NOT modified: this module imports its helpers and
reproduces the per-frame decision block of its main() loop (stable default
mode, no drawing). tests/test_engine_parity.py replays a video through the
original main() and through this engine and compares every frame's counts.

    frame -> PPE model (v5d) + pose model + COCO person fallback
          -> workers (pose workers merged with COCO persons)
          -> helmet: validate_worn_helmet per person region (+ colour assist)
                     -> HelmetSmoother (per stream) -> per-worker helmet
          -> vest:   assign_vests_per_worker -> validate_worn_vest (held hard
                     hat at the chest is not a vest) -> per-worker vest
          -> counts per worker: helmet + no_helmet == vest + no_vest == workers

Thresholds default to the configuration used for the live demo
(DEMO_ARGV); anything else the CLI accepts can be passed as argv.
"""

from __future__ import annotations

import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import video_detection as vd  # noqa: E402  (the reference implementation)

# The flags the live camera is run with for the demo (README).
DEMO_ARGV = ["--conf", "0.4", "--pose-conf", "0.6", "--helmet-hold-frames", "8", "--helmet-color-assist"]

WORN, MISSING = "worn", "missing"


def engine_args(argv: list[str] | None = None):
    """The CLI's argparse namespace for `argv` (DEMO_ARGV by default): same defaults as the camera."""
    saved = sys.argv
    try:
        sys.argv = ["safevision_engine", *(DEMO_ARGV if argv is None else argv)]
        return vd.parse_args()
    finally:
        sys.argv = saved


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------
@dataclass
class WorkerResult:
    box: tuple
    conf: float
    source: str  # "pose" | "coco"
    keypoints: object = None  # (17, 3) x, y, conf, pose workers only
    helmet: str = MISSING  # worn | missing
    helmet_box: tuple | None = None
    helmet_conf: float = 0.0
    vest: str = MISSING
    vest_box: tuple | None = None
    vest_conf: float = 0.0
    track_id: int | None = None

    def to_dict(self) -> dict:
        r = lambda b: None if b is None else [round(float(v), 1) for v in b]  # noqa: E731
        return {
            "box": r(self.box), "confidence": round(self.conf, 3), "source": self.source,
            "track_id": self.track_id,
            "helmet": self.helmet, "helmet_box": r(self.helmet_box), "helmet_confidence": round(self.helmet_conf, 3),
            "vest": self.vest, "vest_box": r(self.vest_box), "vest_confidence": round(self.vest_conf, 3),
            "violations": [v for v, s in (("no_helmet", self.helmet), ("no_vest", self.vest)) if s == MISSING],
        }


@dataclass
class EngineResult:
    workers: list[WorkerResult]
    counts: dict  # per worker: workers, helmet, no_helmet, vest, no_vest
    hud: dict  # exactly what the live camera HUD shows (helmet may count non-worker heads)
    active_helmets: list  # (box, conf) worn helmets drawn by the camera
    inference_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "workers": [w.to_dict() for w in self.workers],
            "counts": dict(self.counts),
            "violations": [
                {"type": v, "worker": i, "box": w.to_dict()["box"]}
                for i, w in enumerate(self.workers) for v in w.to_dict()["violations"]
            ],
            "inference_ms": round(self.inference_ms, 1),
        }


@dataclass
class StreamState:
    """Per stream (camera / video / webcam session) temporal state."""

    smoother: object
    last_used: float = field(default_factory=time.monotonic)


# ---------------------------------------------------------------------------
# Decision logic (mirror of video_detection.main(), stable default mode)
# ---------------------------------------------------------------------------
def _kps(kxy, kcf):
    if kxy is None or kcf is None:
        return None
    import numpy as np

    return np.concatenate([np.asarray(kxy, dtype=float), np.asarray(kcf, dtype=float)[:, None]], axis=1)


def evaluate(frame, ppe_result, pose_result, person_result, smoother, args) -> EngineResult:
    """One frame's per-worker PPE decision from raw model results (no drawing)."""
    ppe_boxes = vd.get_ppe_boxes(ppe_result)
    helmet_dets = ppe_boxes["helmet"]

    pose_workers = vd.dedupe_person_detections(
        vd.get_valid_worker_boxes(pose_result, args.pose_conf) if pose_result is not None else []
    )
    pose_evidence = vd.other_person_poses(
        vd.get_person_regions(pose_result, vd.POSE_EVIDENCE_CONF) if pose_result is not None else [],
        pose_workers,
    )
    coco_persons = vd.filter_coco_persons(vd.get_coco_person_boxes(person_result, args.person_conf), pose_evidence)
    workers, worker_sources = vd.merge_workers(pose_workers, coco_persons)
    worker_boxes = [w[0] for w in workers]
    workers_n = len(worker_boxes)

    person_regions = vd.dedupe_person_detections(
        vd.get_person_regions(pose_result, args.pose_conf) if pose_result is not None else []
    )
    for w, src in zip(workers, worker_sources):
        if (src == "coco" and vd.has_head_keypoints(w[0], pose_evidence)
                and not any(vd._same_person(w[0], p[0], iou_thr=0.45) for p in person_regions)):
            person_regions.append(w)
    person_boxes = [p[0] for p in person_regions]
    person_anchors = [vd.get_face_anchor(p[0], p[2], p[3]) for p in person_regions]

    # Vest: per worker, a hard hat held at the chest is not a vest.
    worker_vest = vd.assign_vests_per_worker(worker_boxes, ppe_boxes["vest"])
    worker_vest = [
        v if v is None or vd.validate_worn_vest(frame, w, v[0]) else None
        for w, v in zip(workers, worker_vest)
    ]
    no_helmet_head, _l, _d = vd.classify_head_ppe(ppe_boxes["no_helmet"], worker_boxes,
                                                  overlap_threshold=args.helmet_worker_overlap)

    # Worn-helmet decision anchored to person regions.
    fh, fw = frame.shape[:2]
    worker_real = [None] * len(person_boxes)
    region_rejected = [False] * len(person_boxes)
    helmet_dbg, helmet_rejected = [], []
    for i, pb in enumerate(person_boxes):
        face = person_anchors[i]
        chosen = None
        for hb, hc in helmet_dets:
            if not vd.helmet_belongs_to_worker(hb, pb):
                continue
            verdict, _core = vd.validate_worn_helmet(hb, pb, face, frame.shape)
            helmet_dbg.append((i, verdict))
            if verdict == "accept":
                if chosen is None or hc > chosen[1]:
                    chosen = (tuple(hb), hc)
            elif verdict == "reject":
                helmet_rejected.append(hb)
        if args.helmet_color_assist and chosen is None:
            cbox = vd.find_yellow_blob_for_worker(frame, pb, fw, fh)
            if cbox is not None and any(vd.calculate_iou(cbox, rb) >= 0.30 for rb in helmet_rejected):
                helmet_dbg.append((i, "reject"))
                cbox = None
            if cbox is not None:
                verdict, _core = vd.validate_worn_helmet(cbox, pb, face, frame.shape)
                helmet_dbg.append((i, verdict))
                if verdict == "accept":
                    chosen = (tuple(cbox), vd.COLOR_ASSIST_CONF)
                elif verdict == "reject":
                    helmet_rejected.append(cbox)
        if chosen is not None:
            worker_real[i] = chosen
        else:
            verdicts = [v for j, v in helmet_dbg if j == i]
            region_rejected[i] = bool(verdicts) and all(v == "reject" for v in verdicts)

    support_boxes = [hb for hb, hc in helmet_dets
                     if hc >= args.helmet_fallback_conf and not any(hb is rb for rb in helmet_rejected)]
    helmet_status, helmet_ghosts = smoother.update(
        person_boxes, worker_real, support_boxes=support_boxes,
        allow_ghost=args.helmet_worker_fallback, worker_rejected=region_rejected,
    )
    active_helmets = [(e[0], e[1]) for e in helmet_status if e is not None]
    active_helmets += list(helmet_ghosts)
    active_helmets = vd.dedupe_helmet_boxes(active_helmets)

    # Per worker: the active worn helmet near this worker's head, if any.
    out = []
    for i, (w, src, vest) in enumerate(zip(workers, worker_sources, worker_vest)):
        wb = w[0]
        mine = [(ab, ac) for ab, ac in active_helmets
                if vd.box_on_worker_head(ab, wb) or vd.calculate_overlap_ratio(ab, wb) >= 0.05]
        wr = WorkerResult(tuple(wb), float(w[1]), src, keypoints=_kps(w[2], w[3]))
        if mine:
            hb, hc = max(mine, key=lambda h: h[1])
            wr.helmet, wr.helmet_box, wr.helmet_conf = WORN, tuple(hb), float(hc)
        else:
            wr.helmet_box = tuple(vd.get_worker_head_box(wb))
        if vest is not None:
            wr.vest, wr.vest_box, wr.vest_conf = WORN, tuple(vest[0]), float(vest[1])
        else:
            wr.vest_box = tuple(vd.get_worker_torso_box(wb))
        out.append(wr)

    helmet_workers = sum(w.helmet == WORN for w in out)
    vest_workers = sum(w.vest == WORN for w in out)
    counts = {
        "workers": workers_n,
        "helmet": helmet_workers,
        "no_helmet": workers_n - helmet_workers,
        "vest": vest_workers,
        "no_vest": workers_n - vest_workers,
    }
    hud = {
        "workers": workers_n,
        "vest": vest_workers,
        "no_vest": workers_n - vest_workers,
        "helmet": len(active_helmets),
        "no_helmet": (workers_n - helmet_workers) if args.infer_no_helmet else len(no_helmet_head),
    }
    return EngineResult(out, counts, hud, active_helmets)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
class SafeVisionEngine:
    """
    Models load once and are shared; temporal state (helmet smoothing) lives in
    a StreamState per stream, so cameras, videos and webcam sessions never
    share it. Model calls are serialised with a lock (YOLO predict is not
    thread safe on a shared model).
    """

    def __init__(self, ppe_model_path, pose_model_path, person_model_path=None, argv: list[str] | None = None,
                 loader=None):
        self.args = engine_args(argv)
        self.paths = {"ppe": Path(ppe_model_path), "pose": Path(pose_model_path),
                      "person": Path(person_model_path) if person_model_path else None}
        self._loader = loader
        self.ppe = self.pose = self.person = None
        self._lock = threading.Lock()
        self._streams: dict[str, StreamState] = {}
        self.error: str | None = None

    # -- models ------------------------------------------------------------
    def load_models(self) -> "SafeVisionEngine":
        load = self._loader or (lambda p: vd.YOLO(str(p)))
        for role in ("ppe", "pose"):
            if not self.paths[role].is_file():
                self.error = f"{role} weights not found ({self.paths[role]})"
                raise FileNotFoundError(self.error)
        self.ppe = load(self.paths["ppe"])
        self.pose = load(self.paths["pose"])
        if self.args.person_fallback and self.paths["person"] is not None:
            if not self.paths["person"].is_file():
                self.error = f"person fallback weights not found ({self.paths['person']})"
                raise FileNotFoundError(self.error)
            self.person = load(self.paths["person"])
        self.error = None
        return self

    def get_model_status(self) -> dict:
        return {
            "loaded": self.ppe is not None and self.pose is not None,
            "ppe": str(self.paths["ppe"]), "pose": str(self.paths["pose"]),
            "person_fallback": self.person is not None,
            "error": self.error,
        }

    # -- state -------------------------------------------------------------
    def new_state(self) -> StreamState:
        return StreamState(vd.HelmetSmoother(hold_frames=self.args.helmet_hold_frames))

    def stream_state(self, camera_id: str) -> StreamState:
        st = self._streams.get(camera_id)
        if st is None:
            st = self._streams[camera_id] = self.new_state()
        st.last_used = time.monotonic()
        return st

    def reset_stream_state(self, camera_id: str) -> None:
        self._streams.pop(camera_id, None)

    def expire_states(self, max_idle_s: float = 300.0) -> None:
        now = time.monotonic()
        for cid in [c for c, s in self._streams.items() if now - s.last_used > max_idle_s]:
            self._streams.pop(cid, None)

    # -- inference ---------------------------------------------------------
    def predict(self, frame):
        """(ppe_result, pose_result, person_result): the same three model calls as the camera."""
        a = self.args
        with self._lock:
            ppe = self.ppe.predict(source=frame, conf=a.conf, verbose=False)[0]
            pose = self.pose.predict(source=frame, conf=min(a.pose_conf, vd.POSE_EVIDENCE_CONF), verbose=False)[0]
            person = None
            if self.person is not None:
                person = self.person.predict(source=frame, conf=a.person_conf,
                                             classes=[vd.COCO_PERSON_CLASS], verbose=False)[0]
        return ppe, pose, person

    def process_frame(self, frame, camera_id: str | None = None, timestamp=None,
                      state: StreamState | None = None) -> EngineResult:
        """
        Per-worker PPE status for one frame. `state` (or `camera_id`) carries
        helmet smoothing between frames of one stream; with neither, the frame
        is judged on its own (e.g. an uploaded image).
        """
        if self.ppe is None:
            raise RuntimeError(self.error or "models not loaded")
        if state is None:
            state = self.stream_state(camera_id) if camera_id is not None else self.new_state()
        t0 = time.perf_counter()
        ppe, pose, person = self.predict(frame)
        result = evaluate(frame, ppe, pose, person, state.smoother, self.args)
        result.inference_ms = (time.perf_counter() - t0) * 1000
        state.last_used = time.monotonic()
        return result

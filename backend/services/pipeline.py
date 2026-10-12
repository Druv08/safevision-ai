"""
The one PPE violation pipeline, used by the backend image and video paths,
the CLI scripts in ai-model/inference/ and ai-model/training/evaluate.py.

    frame ─▶ Detector ─▶ FrameDets ─▶ associate() ─▶ per-person status
                                          │
                     PersonTracker ──▶ track IDs ──▶ Pipeline: time window ─▶ Episodes
                                                                         └──▶ Observations

1. Detector runs the person, helmet and vest models (class ids looked up by name).
2. associate() gives every helmet / no_helmet / vest / no_vest box to at most one
   person, using head and torso regions from pose keypoints when visible, else
   box geometry. Each person gets worn / missing / unknown per item.
3. The tracker gives each person a persistent ID.
4. Pipeline keeps per-track state. An Episode (one Violation row) opens only after
   the same track has been missing an item for `window_s`, and closes after
   `clear_s` without the item missing. Each track and item has its own episode.
5. With zones (services/zones.py) the PPE a person must wear depends on where
   their feet are; outside every zone the camera default applies (both, when
   there are no zones at all). A person in a no-entry zone for `window_s` is a
   zone_intrusion episode.
6. Every track also yields an Observation per required item (compliant /
   violation / unknown), the basis of the compliance rate.

Only numpy and OpenCV are needed here; models are passed in, so the rules can be
tested with synthetic detections and no weights.
"""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from services.zones import DEFAULT_REQUIREMENT, Requirement, ZoneMap, ground_point

# Ultralytics pip-installs missing packages (lap, onnx, ...) at runtime unless told
# not to. Servers and edge devices must not install code on their own: fail instead.
os.environ.setdefault("YOLO_AUTOINSTALL", "false")

ITEMS = ("helmet", "vest")  # PPE decided per frame by associate()
RULES = ("helmet", "vest", "entry")  # what the time window runs on
VIOLATION_TYPE = {"helmet": "no_helmet", "vest": "no_vest", "entry": "zone_intrusion"}
# violation type -> (label shown to people, severity)
TYPE_LABELS = {
    "no_helmet": ("Helmet Missing", "High"),
    "no_vest": ("Safety Vest Missing", "Medium"),
    "zone_intrusion": ("Zone Intrusion", "High"),
}
WORN, MISSING, UNKNOWN = "worn", "missing", "unknown"
EXEMPT = "not_required"  # the item is not required where the person stands

# API / overlay class ids (unchanged from the earlier backend responses)
PERSON_ID, HELMET_ID, NO_HELMET_ID, VEST_ID, NO_VEST_ID = 0, 1, 2, 3, 4

# COCO pose keypoints
NOSE, L_EYE, R_EYE, L_EAR, R_EAR, L_SHO, R_SHO, L_HIP, R_HIP = 0, 1, 2, 3, 4, 5, 6, 11, 12
KP_CONF = 0.4


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
Box = tuple[float, float, float, float]  # x1, y1, x2, y2 in pixels


@dataclass
class Det:
    box: Box
    conf: float


@dataclass
class Person:
    box: Box
    conf: float
    keypoints: np.ndarray | None = None  # (17, 3): x, y, confidence
    track_id: int | None = None


@dataclass
class FrameDets:
    persons: list[Person] = field(default_factory=list)
    helmet: list[Det] = field(default_factory=list)
    no_helmet: list[Det] = field(default_factory=list)
    vest: list[Det] = field(default_factory=list)
    no_vest: list[Det] = field(default_factory=list)


@dataclass
class ItemStatus:
    state: str = UNKNOWN  # worn | missing | unknown
    conf: float = 0.0  # confidence of the deciding evidence
    evidence: list[Det] = field(default_factory=list)


@dataclass
class PersonStatus:
    person: Person
    head: "Region"
    torso: Box
    items: dict[str, ItemStatus]
    requirement: Requirement = DEFAULT_REQUIREMENT  # set by Pipeline from the zones

    @property
    def intrusion(self) -> bool:
        return self.requirement.no_entry_zone is not None

    def missing(self, item: str) -> bool:
        """Missing *and* required here."""
        return self.items[item].state == MISSING and item in self.requirement.items

    @property
    def violating(self) -> bool:
        return self.intrusion or any(self.missing(item) for item in ITEMS)


@dataclass
class Episode:
    """One violation: one track, one rule, from first violating frame to last."""

    type: str  # no_helmet | no_vest | zone_intrusion
    track_id: int | None
    start_s: float  # first missing frame of the run
    alert_s: float  # when the window was satisfied and the alert raised
    end_s: float  # last missing frame
    confidence: float
    box: Box  # person box at alert time
    snapshot: bytes | None = None  # annotated JPEG at alert time (people blurred if the pipeline redacts)
    zone_id: str | None = None  # zone that required the item / was entered (None = camera default)
    original: bytes | None = None  # unblurred annotated JPEG, only when the pipeline redacts


@dataclass
class Observation:
    """How one tracked person did on one item over the whole time they were seen."""

    track_id: int | None
    item: str
    outcome: str  # compliant | violation | unknown
    frames_worn: int
    frames_missing: int
    frames_unknown: int
    first_s: float
    last_s: float


@dataclass
class PipelineConfig:
    window_s: float = 2.0  # missing this long before an alert (0 = alert on first frame)
    clear_s: float = 1.0  # not missing this long before an episode closes
    track_timeout_s: float = 2.0  # forget a track not seen for this long


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------
def _area(b: Box) -> float:
    return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])


def frac_inside(a: Box, b: Box) -> float:
    """Fraction of a's area that lies inside b."""
    iw = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    ih = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    return iw * ih / _area(a) if _area(a) > 0 else 0.0


def _center(b: Box) -> tuple[float, float]:
    return (b[0] + b[2]) / 2, (b[1] + b[3]) / 2


def _center_in(b: Box, r: Box, margin: float = 0.0) -> bool:
    cx, cy = _center(b)
    mx, my = (r[2] - r[0]) * margin, (r[3] - r[1]) * margin
    return r[0] - mx <= cx <= r[2] + mx and r[1] - my <= cy <= r[3] + my


# ---------------------------------------------------------------------------
# Head and torso regions
# ---------------------------------------------------------------------------
@dataclass
class Region:
    box: Box  # a worn helmet's centre must be inside this
    min_bottom: float  # its bottom edge must reach at least this low (onto the head)
    max_bottom: float  # ... and no lower than this (not over the face / chest)
    from_pose: bool


def _kp(p: Person, i: int):
    k = p.keypoints
    if k is None or i >= len(k) or k[i][2] < KP_CONF:
        return None
    return float(k[i][0]), float(k[i][1])


def head_region(p: Person) -> Region:
    x1, y1, x2, y2 = p.box
    w, h = x2 - x1, y2 - y1
    face = [pt for i in (NOSE, L_EYE, R_EYE, L_EAR, R_EAR) if (pt := _kp(p, i))]
    if len(face) >= 2:
        cx = sum(x for x, _ in face) / len(face)
        cy = sum(y for _, y in face) / len(face)
        ears, eyes = (_kp(p, L_EAR), _kp(p, R_EAR)), (_kp(p, L_EYE), _kp(p, R_EYE))
        if all(ears):
            hw = abs(ears[0][0] - ears[1][0]) * 0.6
        elif all(eyes):
            hw = abs(eyes[0][0] - eyes[1][0]) * 1.0
        else:
            hw = 0.13 * w
        hw = max(hw, 0.05 * w, 4.0)
        # Shell extends above the face; a worn helmet ends around the brow.
        return Region((cx - 1.4 * hw, cy - 2.4 * hw, cx + 1.4 * hw, cy + 0.6 * hw), cy - 1.4 * hw, cy + 0.8 * hw, True)
    # Box geometry: head = top 30 % of the box, middle 60 % of its width.
    return Region((x1 + 0.2 * w, y1, x2 - 0.2 * w, y1 + 0.30 * h), y1 + 0.10 * h, y1 + 0.42 * h, False)


def torso_region(p: Person) -> Box:
    x1, y1, x2, y2 = p.box
    w, h = x2 - x1, y2 - y1
    sho = [pt for i in (L_SHO, R_SHO) if (pt := _kp(p, i))]
    hips = [pt for i in (L_HIP, R_HIP) if (pt := _kp(p, i))]
    if len(sho) == 2:
        sw = abs(sho[0][0] - sho[1][0])
        xs = [x for x, _ in sho + hips]
        top = min(y for _, y in sho)
        bottom = sum(y for _, y in hips) / len(hips) if hips else top + 1.5 * sw
        return (min(xs) - 0.15 * sw, top, max(xs) + 0.15 * sw, bottom)
    return (x1 + 0.15 * w, y1 + 0.20 * h, x2 - 0.15 * w, y1 + 0.65 * h)


def helmet_on_head(h: Det, p: Person, head: Region) -> bool:
    """A helmet counts as worn only if it sits on this person's head."""
    pw = p.box[2] - p.box[0]
    return (
        _center_in(h.box, head.box)
        and head.min_bottom <= h.box[3] <= head.max_bottom
        and (h.box[2] - h.box[0]) <= 0.85 * pw  # not a body-sized box
    )


def vest_on_torso(v: Det, p: Person, torso: Box) -> bool:
    """A vest counts as worn only if it covers this person's torso."""
    vcx, vcy = _center(v.box)
    tw, th = torso[2] - torso[0], torso[3] - torso[1]
    return (
        _center_in(v.box, p.box)
        and torso[1] <= vcy <= torso[3] + 0.15 * th  # not up at the face, not down at the legs
        and torso[0] - 0.15 * tw <= vcx <= torso[2] + 0.15 * tw
        and max(frac_inside(torso, v.box), frac_inside(v.box, torso)) >= 0.4
        and frac_inside(v.box, p.box) >= 0.6
    )


# ---------------------------------------------------------------------------
# Association
# ---------------------------------------------------------------------------
def _best(box: Box, persons: list[Person], region_of, min_overlap: float):
    """Index of the person a negative/held box belongs to, or None.

    Needs at least `min_overlap` of the box inside the person; prefers a person
    whose head/torso region contains the box centre, then the largest overlap.
    """
    best, best_score = None, 0.0
    for i, p in enumerate(persons):
        overlap = frac_inside(box, p.box)
        if overlap < min_overlap:
            continue
        score = overlap + (1.0 if _center_in(box, region_of(i), margin=0.25) else 0.0)
        if score > best_score:
            best, best_score = i, score
    return best


def associate(dets: FrameDets) -> tuple[list[PersonStatus], list[tuple[int, Det]]]:
    """
    Decide each person's helmet and vest state from one frame's boxes.

    Returns (statuses, labelled) where `labelled` is every box with the class id
    to show it as: a helmet or vest held by a person (not worn) is shown as
    no_helmet / no_vest. Boxes that belong to nobody never become violations.
    """
    persons = dets.persons
    heads = [head_region(p) for p in persons]
    torsos = [torso_region(p) for p in persons]
    statuses = [PersonStatus(p, heads[i], torsos[i], {k: ItemStatus() for k in ITEMS}) for i, p in enumerate(persons)]
    labelled = [(PERSON_ID, Det(p.box, p.conf)) for p in persons]

    def give(i: int, item: str, state: str, d: Det):
        s = statuses[i].items[item]
        s.evidence.append(d)
        if state == WORN:
            if s.state != WORN:
                s.state, s.conf = WORN, d.conf
            else:
                s.conf = max(s.conf, d.conf)
        elif s.state != WORN:  # worn wins over missing evidence for the same person
            s.state, s.conf = MISSING, max(s.conf if s.state == MISSING else 0.0, d.conf)

    def place(item, positives, negatives, worn_test, region_of, held_overlap, neg_overlap, ids):
        pos_id, neg_id = ids
        worn_boxes = []
        for d in positives:
            wearers = [i for i, p in enumerate(persons) if worn_test(d, p, i)]
            if wearers:
                i = max(wearers, key=lambda i: frac_inside(d.box, region_of(i)))
                give(i, item, WORN, d)
                worn_boxes.append(d.box)
                labelled.append((pos_id, d))
            elif (i := _best(d.box, persons, region_of, held_overlap)) is not None:
                give(i, item, MISSING, d)  # held, carried or hanging: not worn
                labelled.append((neg_id, d))
            else:
                labelled.append((pos_id, d))  # lying around, belongs to nobody
        for d in negatives:
            # The model often fires both classes on one head; a negative box that
            # mostly sits on a worn item is a duplicate, not evidence.
            if any(frac_inside(d.box, wb) >= 0.5 for wb in worn_boxes):
                continue
            labelled.append((neg_id, d))
            if (i := _best(d.box, persons, region_of, neg_overlap)) is not None:
                give(i, item, MISSING, d)

    place(
        "helmet", dets.helmet, dets.no_helmet,
        lambda d, p, i: helmet_on_head(d, p, heads[i]), lambda i: heads[i].box,
        0.15, 0.2, (HELMET_ID, NO_HELMET_ID),
    )
    place(
        "vest", dets.vest, dets.no_vest,
        lambda d, p, i: vest_on_torso(d, p, torsos[i]), lambda i: torsos[i],
        0.2, 0.2, (VEST_ID, NO_VEST_ID),
    )
    return statuses, labelled


def summarize(statuses: list[PersonStatus]) -> dict:
    """Per-frame counts in the shape the API has always returned."""
    def worn(item):
        return sum(s.items[item].state == WORN for s in statuses)

    return {
        "total_persons": len(statuses),
        "helmet_worn": worn("helmet"),
        "no_helmet": sum(s.missing("helmet") for s in statuses),
        "vest_worn": worn("vest"),
        "no_vest": sum(s.missing("vest") for s in statuses),
        "zone_intrusions": sum(s.intrusion for s in statuses),
    }


def detections_for_api(labelled: list[tuple[int, Det]]) -> list[dict]:
    return [
        {"class_id": cid, "confidence": round(d.conf, 3), "box": [round(float(v), 1) for v in d.box]}
        for cid, d in labelled
    ]


# ---------------------------------------------------------------------------
# Time window, episodes and observations
# ---------------------------------------------------------------------------
@dataclass
class _ItemState:
    since: float | None = None  # first missing frame of the current run
    last_missing: float | None = None
    conf: float = 0.0  # highest missing confidence in the current run
    episode: Episode | None = None
    had_episode: bool = False
    frames: dict = field(default_factory=lambda: {WORN: 0, MISSING: 0, UNKNOWN: 0, EXEMPT: 0})


@dataclass
class _Track:
    first_s: float
    last_s: float
    items: dict = field(default_factory=lambda: {k: _ItemState() for k in RULES})


@dataclass
class FrameResult:
    t: float
    statuses: list[PersonStatus]
    labelled: list[tuple[int, Det]]
    opened: list[Episode]  # alerts raised on this frame
    closed: list[Episode]  # episodes that ended (now complete)
    observations: list[Observation]  # tracks that left the scene

    @property
    def summary(self) -> dict:
        return summarize(self.statuses)


class Pipeline:
    """
    Stateful per video / stream. `detect` turns a frame into FrameDets (a
    Detector, or any callable); `tracker` assigns track IDs (None = each person
    in the frame is its own track, which is what a single image needs);
    `zones` (a ZoneMap) sets what each person must wear, by where they stand.
    `zones` may be replaced between frames (e.g. after an admin edits them).
    `redact(frame, statuses) -> frame` (e.g. privacy.blur_people) is applied
    to evidence screenshots before they are annotated; the unblurred one is
    then kept separately as Episode.original.
    """

    def __init__(self, detect=None, config: PipelineConfig | None = None, tracker=None, zones: ZoneMap | None = None,
                 redact=None):
        self.detect = detect
        self.cfg = config or PipelineConfig()
        self.tracker = tracker
        self.zones = zones
        self.redact = redact
        self.frame_size: tuple[int, int] | None = None  # (w, h), needed to place people in zones
        self.tracks: dict[int, _Track] = {}

    def process(self, frame: np.ndarray, t: float) -> FrameResult:
        dets = self.detect(frame)
        if self.tracker is not None:
            self.tracker.update(dets.persons, frame)
        return self.step(dets, t, frame)

    def step(self, dets: FrameDets, t: float, frame: np.ndarray | None = None) -> FrameResult:
        """Apply the rules to one frame of (already tracked) detections at time t (seconds)."""
        if self.tracker is None:
            for i, p in enumerate(dets.persons, start=1):
                p.track_id = i
        statuses, labelled = associate(dets)
        result = FrameResult(t, statuses, labelled, [], [], [])
        cfg = self.cfg
        if frame is not None:
            self.frame_size = (frame.shape[1], frame.shape[0])
        if self.zones is not None:
            if self.frame_size is None:
                raise ValueError("zones need the frame size: pass the frame or set Pipeline.frame_size")
            w, h = self.frame_size
            for st in statuses:
                st.requirement = self.zones.requirement(ground_point(st.person.box, w, h))

        for st in statuses:
            tid = st.person.track_id
            if tid is None:  # not confirmed by the tracker yet
                continue
            track = self.tracks.setdefault(tid, _Track(t, t))
            track.last_s = t
            req = st.requirement
            for rule in RULES:
                state = track.items[rule]
                if rule == "entry":
                    eff = MISSING if st.intrusion else WORN
                    conf, zone_id = st.person.conf, req.no_entry_zone
                elif rule in req.items:
                    eff, conf, zone_id = st.items[rule].state, st.items[rule].conf, req.item_zone.get(rule)
                else:
                    eff, conf, zone_id = EXEMPT, 0.0, None  # e.g. a bare head in a "none" zone
                state.frames[eff] += 1
                if eff == MISSING:
                    if state.since is not None and t - state.last_missing > cfg.clear_s:
                        self._end_run(state, result.closed)  # person was out of view: a new run
                    if state.since is None:
                        state.since, state.conf = t, 0.0
                    state.last_missing = t
                    state.conf = max(state.conf, conf)
                    if state.episode is None and t - state.since >= cfg.window_s:
                        shot, original = (_snapshot(frame, result, st, self.zones, self.redact)
                                          if frame is not None else (None, None))
                        state.episode = Episode(
                            VIOLATION_TYPE[rule], tid, state.since, t, t, state.conf, st.person.box,
                            shot, zone_id, original,
                        )
                        state.had_episode = True
                        result.opened.append(state.episode)
                    elif state.episode is not None:
                        state.episode.end_s = t
                        state.episode.confidence = max(state.episode.confidence, conf)
                elif state.since is not None and t - state.last_missing >= cfg.clear_s:
                    self._end_run(state, result.closed)

        for tid in [tid for tid, tr in self.tracks.items() if t - tr.last_s > cfg.track_timeout_s]:
            self._drop(tid, result.closed, result.observations)
        return result

    def finish(self) -> tuple[list[Episode], list[Observation]]:
        """End of video / stream: close every open episode and report every track."""
        closed, observations = [], []
        for tid in list(self.tracks):
            self._drop(tid, closed, observations)
        return closed, observations

    @staticmethod
    def _end_run(state: _ItemState, closed: list[Episode]) -> None:
        if state.episode is not None:
            state.episode.end_s = state.last_missing
            closed.append(state.episode)
        state.since, state.episode = None, None

    def _drop(self, tid: int, closed: list[Episode], observations: list[Observation]) -> None:
        track = self.tracks.pop(tid)
        for rule, state in track.items.items():
            self._end_run(state, closed)
            f = state.frames
            if rule not in ITEMS or not (f[WORN] or f[MISSING] or f[UNKNOWN]):
                continue  # compliance is about PPE that was required at some point
            outcome = "violation" if state.had_episode else "compliant" if f[WORN] else "unknown"
            observations.append(
                Observation(tid, rule, outcome, f[WORN], f[MISSING], f[UNKNOWN], track.first_s, track.last_s)
            )


def compliance(observations: list[Observation]) -> dict:
    """Per item: counts and rate = compliant / (compliant + violation); unknown is excluded."""
    out = {}
    for item in ITEMS:
        n = {k: sum(o.item == item and o.outcome == k for o in observations)
             for k in ("compliant", "violation", "unknown")}
        decided = n["compliant"] + n["violation"]
        out[item] = {**n, "rate": round(n["compliant"] / decided, 4) if decided else None}
    return out


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
# Normalised class names that mean each role, across our 5-class and the
# 17-class construction-safety weights.
ROLE_NAMES = {
    "person": {"person"},
    "helmet": {"helmet", "hardhat", "hard_hat"},
    "no_helmet": {"no_helmet", "no_hardhat", "no_hard_hat"},
    "vest": {"vest", "safety_vest"},
    "no_vest": {"no_vest", "no_safety_vest"},
}


def _norm(name: str) -> str:
    return re.sub(r"[^a-z]+", "_", name.lower()).strip("_")


def class_ids(names: dict, roles) -> dict[str, int]:
    """{role: class id} looked up by class name. Raises ValueError if a role is missing."""
    by_name = {_norm(n): int(i) for i, n in names.items()}
    out = {}
    for role in roles:
        found = [by_name[n] for n in ROLE_NAMES[role] if n in by_name]
        if not found:
            raise ValueError(f"model has no {role!r} class (classes: {sorted(by_name)})")
        out[role] = found[0]
    return out


def drop_group_boxes(persons: list[Person]) -> list[Person]:
    """Remove person boxes that span two or more other people (the detector's 'group' box).

    Such a box would be tracked as an extra person and duplicate the alerts of
    the people inside it.
    """
    def inside(inner: Person, outer: Person) -> bool:
        return inner is not outer and frac_inside(inner.box, outer.box) >= 0.8 and _area(inner.box) < _area(outer.box)

    return [p for p in persons if sum(inside(q, p) for q in persons) < 2]


def load_yolo(path):
    """
    Load .pt or exported .onnx weights. For ONNX, the task (detect / pose) is read
    from the metadata Ultralytics writes at export, instead of being guessed from
    the file name, so a renamed pose model still yields keypoints.
    """
    from ultralytics import YOLO

    task = None
    if str(path).lower().endswith(".onnx"):
        import onnxruntime  # needed to run ONNX weights anyway

        session = onnxruntime.InferenceSession(str(path), providers=["CPUExecutionProvider"])
        task = session.get_modelmeta().custom_metadata_map.get("task")
    return YOLO(str(path), task=task)


class Detector:
    """Runs the person, helmet and vest models on a frame. Shared weights run once."""

    def __init__(self, ppe_model, helmet_model, person_model, ppe_conf: float = 0.4, person_conf: float = 0.4):
        self.roles = [
            (person_model, class_ids(person_model.names, ["person"]), person_conf),
            (helmet_model, class_ids(helmet_model.names, ["helmet", "no_helmet"]), ppe_conf),
            (ppe_model, class_ids(ppe_model.names, ["vest", "no_vest"]), ppe_conf),
        ]
        self.uses_pose = getattr(person_model, "task", None) == "pose"

    def __call__(self, frame: np.ndarray) -> FrameDets:
        out = FrameDets()
        cache = {}
        for model, roles, conf in self.roles:
            key = (id(model), conf)
            if key not in cache:
                cache[key] = model.predict(frame, conf=conf, verbose=False)[0]
            r = cache[key]
            if r.boxes is None:
                continue
            cls = r.boxes.cls.cpu().numpy().astype(int)
            xyxy = r.boxes.xyxy.cpu().numpy()
            confs = r.boxes.conf.cpu().numpy()
            kps = r.keypoints.data.cpu().numpy() if getattr(r, "keypoints", None) is not None else None
            for role, cid in roles.items():
                for j in np.flatnonzero(cls == cid):
                    box = tuple(float(v) for v in xyxy[j])
                    if role == "person":
                        out.persons.append(Person(box, float(confs[j]), kps[j] if kps is not None else None))
                    else:
                        getattr(out, role).append(Det(box, float(confs[j])))
        out.persons = drop_group_boxes(out.persons)
        return out


def model_version(*paths: Path) -> str:
    """Training-run folder names (or file names), e.g. 'safevision_yolov8n_5class_v2+safevision_yolov8n_v1'."""
    names = []
    for p in paths:
        p = Path(p)
        name = p.parent.parent.name if p.parent.name == "weights" else p.stem
        if name not in names:
            names.append(name)
    return "+".join(names)


# ---------------------------------------------------------------------------
# Drawing and video
# ---------------------------------------------------------------------------
GREEN, RED, GREY, AMBER = (0, 190, 0), (0, 0, 230), (170, 170, 170), (0, 200, 255)
_CLASS_COLOR = {HELMET_ID: GREEN, VEST_ID: GREEN, NO_HELMET_ID: RED, NO_VEST_ID: RED}
_MARK = {WORN: "ok", MISSING: "NO", UNKNOWN: "?"}
_ZONE_COLOR = {"no_entry": RED, "none": GREY}


def draw_zones(img: np.ndarray, zones: ZoneMap) -> None:
    h, w = img.shape[:2]
    for z in zones.zones:
        pts = np.array([[int(x * w), int(y * h)] for x, y in z.polygon], np.int32)
        color = _ZONE_COLOR.get(z.policy, AMBER)
        cv2.polylines(img, [pts], True, color, 2)
        x, y = (int(v) for v in pts[0])  # label just inside the first vertex, kept on screen
        cv2.putText(img, f"{z.name} [{z.policy}]", (min(max(x + 4, 4), w - 120), min(max(y + 16, 16), h - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)


def draw(frame: np.ndarray, result: FrameResult, highlight: PersonStatus | None = None,
         zones: ZoneMap | None = None) -> np.ndarray:
    """Annotated copy of the frame: zones, PPE boxes, and each person with ID and helmet/vest state.

    '-' means the item is not required where the person stands; ZONE marks a no-entry intrusion.
    """
    img = frame.copy()
    if zones is not None:
        draw_zones(img, zones)
    for cid, d in result.labelled:
        if cid != PERSON_ID:
            x1, y1, x2, y2 = map(int, d.box)
            cv2.rectangle(img, (x1, y1), (x2, y2), _CLASS_COLOR[cid], 1)
    for st in result.statuses:
        x1, y1, x2, y2 = map(int, st.person.box)
        required = st.requirement.items
        color = AMBER if st is highlight else RED if st.violating else GREEN if all(
            st.items[i].state == WORN for i in required) else GREY
        cv2.rectangle(img, (x1, y1), (x2, y2), color, 3 if st is highlight else 2)
        tid = "" if st.person.track_id is None else f"#{st.person.track_id} "
        mark = {i: _MARK[st.items[i].state] if i in required else "-" for i in ITEMS}
        label = f"{tid}H:{mark['helmet']} V:{mark['vest']}" + (" ZONE" if st.intrusion else "")
        cv2.putText(img, label, (x1, max(12, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
    return img


def _snapshot(frame: np.ndarray, result: FrameResult, st: PersonStatus, zones: ZoneMap | None = None,
              redact=None) -> tuple[bytes | None, bytes | None]:
    """(evidence JPEG, unblurred JPEG or None). Annotations are drawn after redacting, so they stay readable."""
    def jpeg(img):
        ok, buf = cv2.imencode(".jpg", draw(img, result, highlight=st, zones=zones))
        return buf.tobytes() if ok else None

    if redact is None:
        return jpeg(frame), None
    return jpeg(redact(frame, result.statuses)), jpeg(frame)


class VideoDecodeError(ValueError):
    pass


FALLBACK_FPS = 30.0


def video_frames(cap):
    """Yield (time_s, frame) using the container's timestamps (frame index / fps as fallback)."""
    fps = cap.get(cv2.CAP_PROP_FPS)
    if not 0 < fps < 240:  # webm from MediaRecorder often reports 0 or 1000
        fps = FALLBACK_FPS
    n = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            return
        pos_ms = cap.get(cv2.CAP_PROP_POS_MSEC)
        yield (pos_ms / 1000.0 if pos_ms > 0 else n / fps), frame
        n += 1


@dataclass
class VideoRun:
    episodes: list[Episode]
    observations: list[Observation]
    frames: int
    duration_s: float


def probe_video(path) -> None:
    """Raise VideoDecodeError unless at least one frame decodes (checked before loading models)."""
    cap = cv2.VideoCapture(str(path))
    try:
        if not cap.isOpened() or not cap.read()[0]:
            raise VideoDecodeError("No frames could be decoded from the video.")
    finally:
        cap.release()


def run_video(path, pipeline: Pipeline, on_frame=None) -> VideoRun:
    """Run the pipeline over a whole video file. Raises VideoDecodeError if nothing decodes."""
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise VideoDecodeError("Could not open the video file.")
    episodes, observations, frames, last_t = [], [], 0, 0.0
    try:
        for t, frame in video_frames(cap):
            result = pipeline.process(frame, t)
            episodes += result.closed
            observations += result.observations
            frames, last_t = frames + 1, t
            if on_frame:
                on_frame(frame, result)
    finally:
        cap.release()
    if frames == 0:
        raise VideoDecodeError("No frames could be decoded from the video.")
    closed, obs = pipeline.finish()
    episodes = sorted(episodes + closed, key=lambda e: e.alert_s)
    return VideoRun(episodes, observations + obs, frames, last_t)

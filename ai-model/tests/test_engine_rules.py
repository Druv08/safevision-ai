"""
Per-worker PPE rules of the shared engine on synthetic model outputs (no weights).

Model results are faked with the attributes the camera's helpers read
(boxes.xyxy/conf/cls, keypoints.xy/conf), so these run in CI. They check the
decision rules, not the model: real-image behaviour is covered by
test_engine_parity.py against the live camera.
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "inference"))

import safevision_engine as se  # noqa: E402

HELMET, NO_HELMET, VEST, NO_VEST = 1, 2, 3, 4
H, W = 800, 640


class _T:
    def __init__(self, a):
        self.a = np.asarray(a, dtype=float)

    def cpu(self):
        return self

    def numpy(self):
        return self.a


class _Boxes:
    def __init__(self, rows):  # rows: (box, conf, cls)
        self.xyxy = _T([r[0] for r in rows] or np.zeros((0, 4)))
        self.conf = _T([r[1] for r in rows])
        self.cls = _T([r[2] for r in rows])

    def __len__(self):
        return len(self.conf.a)


class _Kps:
    def __init__(self, kps):
        self.xy = _T([k[:, :2] for k in kps] or np.zeros((0, 17, 2)))
        self.conf = _T([k[:, 2] for k in kps] or np.zeros((0, 17)))


class _Result:
    def __init__(self, rows=(), kps=None):
        self.boxes = _Boxes(list(rows))
        self.keypoints = _Kps(kps) if kps is not None else None


def person(x0=200, wrists_at=None):
    """A standing worker box with front-facing pose keypoints, offset by x0."""
    k = np.zeros((17, 3))
    pts = {0: (100, 170), 1: (90, 160), 2: (110, 160), 3: (75, 165), 4: (125, 165),
           5: (50, 250), 6: (150, 250), 7: (35, 350), 8: (165, 350), 9: (20, 450), 10: (180, 450),
           11: (65, 450), 12: (135, 450), 13: (65, 580), 14: (135, 580), 15: (65, 690), 16: (135, 690)}
    for i, (x, y) in pts.items():
        k[i] = (x0 + x, y, 0.95)
    if wrists_at is not None:
        k[9, :2] = wrists_at[0]
        k[10, :2] = wrists_at[1]
    return (x0, 100, x0 + 200, 700), k


def run(frame, people, ppe_rows=(), state=None, argv=None):
    args = se.engine_args(argv)
    pose = _Result([(b, 0.9, 0) for b, _ in people], [k for _, k in people])
    smoother = (state or se.StreamState(se.vd.HelmetSmoother(hold_frames=args.helmet_hold_frames))).smoother
    # no COCO fallback in these tests: workers come from the pose model only
    return se.evaluate(frame, _Result(ppe_rows), pose, None, smoother, args)


def blank():
    return np.full((H, W, 3), 90, np.uint8)


def counts(r):
    c = r.counts
    assert c["helmet"] + c["no_helmet"] == c["workers"] == c["vest"] + c["no_vest"]
    return (c["workers"], c["helmet"], c["no_helmet"], c["vest"], c["no_vest"])


def test_empty_frame_counts_nothing():
    assert counts(run(blank(), [])) == (0, 0, 0, 0, 0)


def test_ppe_without_a_worker_counts_nothing():
    rows = [((300, 100, 360, 150), 0.9, HELMET), ((260, 260, 360, 420), 0.9, VEST)]
    assert counts(run(blank(), [], rows)) == (0, 0, 0, 0, 0)


def test_worker_without_any_ppe_box_is_no_helmet_and_no_vest():
    r = run(blank(), [person()])
    assert counts(r) == (1, 0, 1, 0, 1)
    assert r.to_dict()["workers"][0]["violations"] == ["no_helmet", "no_vest"]


def test_worn_vest_on_torso_counts_vest():
    f = blank()
    f[260:440, 240:360] = (0, 255, 170)  # hi-vis green-yellow
    r = run(f, [person()], [((240, 260, 360, 440), 0.9, VEST)])
    assert counts(r) == (1, 0, 1, 1, 0)


def test_hard_hat_held_at_chest_is_not_a_vest():
    f = blank()
    f[280:380, 250:350] = (0, 190, 255)  # hard-hat yellow/orange, square box
    p = person(wrists_at=((255, 330), (345, 330)))  # both hands on it
    r = run(f, [p], [((250, 280, 350, 380), 0.9, VEST)])
    assert counts(r) == (1, 0, 1, 0, 1)


def test_helmet_held_away_from_head_is_not_worn():
    p = person(wrists_at=((180, 450), (180, 450)))
    r = run(blank(), [p], [((150, 420, 230, 480), 0.9, HELMET)])
    assert counts(r)[1:3] == (0, 1)


def test_two_workers_are_judged_separately():
    f = blank()
    a, b = person(0), person(420)
    f[260:440, 40:160] = (0, 255, 170)
    r = run(f, [a, b], [((40, 260, 160, 440), 0.9, VEST)])
    assert counts(r) == (2, 0, 2, 1, 1)
    assert [w["vest"] for w in r.to_dict()["workers"]] == ["worn", "missing"]


def test_helmet_on_head_counts_and_is_smoothed_per_stream():
    state = se.StreamState(se.vd.HelmetSmoother(hold_frames=8))
    on_head = [((255, 105, 345, 165), 0.9, HELMET)]
    assert counts(run(blank(), [person()], on_head, state=state)) == (1, 1, 0, 0, 1)
    # Helmet box drops out for one frame: the same stream keeps it, a fresh stream does not.
    assert run(blank(), [person()], [], state=state).counts["helmet"] == 1
    assert run(blank(), [person()], []).counts["helmet"] == 0

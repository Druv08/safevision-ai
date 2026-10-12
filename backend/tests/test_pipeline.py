"""Association and time-window rules, on synthetic detections (no model weights)."""

import numpy as np
import pytest

from services.pipeline import (
    MISSING,
    UNKNOWN,
    WORN,
    Det,
    FrameDets,
    Person,
    Pipeline,
    PipelineConfig,
    associate,
    class_ids,
    compliance,
)

PERSON = (100, 100, 200, 400)  # 100 wide, 300 tall
WORN_HELMET = Det((130, 95, 170, 140), 0.8)  # on PERSON's head
NO_HELMET_ON_HEAD = Det((130, 95, 170, 140), 0.7)
VEST_ON_TORSO = Det((110, 150, 190, 300), 0.9)
NO_VEST_ON_TORSO = Det((110, 150, 190, 300), 0.6)


def person(box=PERSON, conf=0.9, keypoints=None, track_id=None):
    return Person(box, conf, keypoints, track_id)


def status(dets):
    statuses, _ = associate(dets)
    return [{k: s.state for k, s in st.items.items()} for st in statuses]


# ---------------------------------------------------------------------------
# Association
# ---------------------------------------------------------------------------
def test_worn_helmet_and_vest():
    assert status(FrameDets([person()], helmet=[WORN_HELMET], vest=[VEST_ON_TORSO])) == [
        {"helmet": WORN, "vest": WORN}
    ]


def test_nothing_detected_is_unknown_not_a_violation():
    assert status(FrameDets([person()])) == [{"helmet": UNKNOWN, "vest": UNKNOWN}]


def test_duplicate_no_helmet_on_worn_helmet_is_ignored():
    dup = Det((132, 97, 168, 138), 0.6)
    statuses, labelled = associate(FrameDets([person()], helmet=[WORN_HELMET], no_helmet=[dup]))
    assert statuses[0].items["helmet"].state == WORN
    assert {cid for cid, _ in labelled} == {0, 1}  # the duplicate is not shown as No Helmet


def test_no_helmet_on_head_is_missing_with_best_confidence():
    second = Det((128, 96, 172, 150), 0.55)
    statuses, _ = associate(FrameDets([person()], no_helmet=[NO_HELMET_ON_HEAD, second]))
    assert statuses[0].items["helmet"].state == MISSING
    assert statuses[0].items["helmet"].conf == 0.7


def test_helmet_held_in_hand_is_missing():
    held = Det((185, 250, 230, 290), 0.8)  # at the person's side, waist height
    statuses, labelled = associate(FrameDets([person()], helmet=[held]))
    assert statuses[0].items["helmet"].state == MISSING
    assert (2, held) in labelled  # shown as No Helmet


def test_vest_held_at_side_is_missing_and_no_vest_suppressed_by_worn_vest():
    held = Det((150, 300, 230, 390), 0.8)  # low and to the side: not on the torso
    assert status(FrameDets([person()], vest=[held]))[0]["vest"] == MISSING
    assert status(FrameDets([person()], vest=[VEST_ON_TORSO], no_vest=[NO_VEST_ON_TORSO]))[0]["vest"] == WORN


def test_ppe_with_no_person_is_never_assigned():
    statuses, labelled = associate(FrameDets([], helmet=[WORN_HELMET], no_vest=[NO_VEST_ON_TORSO]))
    assert statuses == []
    assert {cid for cid, _ in labelled} == {1, 4}  # still reported for the overlay


def test_one_negative_box_goes_to_one_person_only():
    left, right = person((100, 100, 200, 400)), person((180, 100, 280, 400))
    no_vest = Det((150, 160, 215, 300), 0.7)  # straddles both, centre in the left torso
    assert status(FrameDets([left, right], no_vest=[no_vest])) == [
        {"helmet": UNKNOWN, "vest": MISSING},
        {"helmet": UNKNOWN, "vest": UNKNOWN},
    ]


def keypoints(face_x, face_y, shoulders_y=170, hips_y=290, sx=(120, 180)):
    k = np.zeros((17, 3), np.float32)
    for i, dx in ((0, 0), (1, -6), (2, 6), (3, -14), (4, 14)):  # nose, eyes, ears
        k[i] = (face_x + dx, face_y, 0.9)
    k[5], k[6] = (sx[0], shoulders_y, 0.9), (sx[1], shoulders_y, 0.9)
    k[11], k[12] = (sx[0] + 5, hips_y, 0.9), (sx[1] - 5, hips_y, 0.9)
    return k


def test_pose_head_region_overrides_box_geometry():
    # Face is at the right edge of the box (leaning). A helmet over the left part
    # of the box top passes the box-geometry rule but is not on the actual head.
    helmet_left = Det((115, 95, 145, 135), 0.8)
    assert status(FrameDets([person()], helmet=[helmet_left]))[0]["helmet"] == WORN  # box only
    kp = keypoints(face_x=180, face_y=135)
    assert status(FrameDets([person(keypoints=kp)], helmet=[helmet_left]))[0]["helmet"] == MISSING
    on_face = Det((165, 105, 195, 132), 0.8)
    assert status(FrameDets([person(keypoints=kp)], helmet=[on_face]))[0]["helmet"] == WORN


def test_pose_torso_region_used_for_vests():
    kp = keypoints(face_x=150, face_y=130, shoulders_y=200, hips_y=330)
    high_vest = Det((115, 140, 185, 230), 0.8)  # chest band of the box, above the real shoulders
    assert status(FrameDets([person()], vest=[high_vest]))[0]["vest"] == WORN
    assert status(FrameDets([person(keypoints=kp)], vest=[high_vest]))[0]["vest"] == MISSING


def test_class_ids_by_name_for_both_model_families():
    five = {0: "person", 1: "helmet", 2: "no_helmet", 3: "vest", 4: "no_vest"}
    seventeen = {4: "Hardhat", 6: "NO-Hardhat", 8: "NO-Safety Vest", 9: "Person", 12: "Safety Vest"}
    assert class_ids(five, ["helmet", "no_helmet"]) == {"helmet": 1, "no_helmet": 2}
    assert class_ids(seventeen, ["helmet", "no_helmet", "vest", "no_vest"]) == {
        "helmet": 4, "no_helmet": 6, "vest": 12, "no_vest": 8,
    }
    with pytest.raises(ValueError, match="no 'vest' class"):
        class_ids({0: "person"}, ["vest"])


# ---------------------------------------------------------------------------
# Time window and episodes
# ---------------------------------------------------------------------------
FPS = 10


def run(frames, config=None, frame=None):
    """frames: list of FrameDets, one per 1/FPS s, with track_id already set."""
    pipe = Pipeline(config=config or PipelineConfig(window_s=2.0, clear_s=1.0), tracker=object())
    opened, closed, obs = [], [], []
    for n, dets in enumerate(frames):
        r = pipe.step(dets, n / FPS, frame)
        opened += r.opened
        closed += r.closed
        obs += r.observations
    c, o = pipe.finish()
    return opened, closed + c, obs + o


def tracked(tid, box=PERSON):
    return person(box, track_id=tid)


def bare(tid=1, box=PERSON):
    """Person `tid` with a no_helmet box on the head and a vest worn."""
    x1, y1 = box[0], box[1]
    no_helmet = Det((x1 + 30, y1 - 5, x1 + 70, y1 + 40), 0.7)
    vest = Det((x1 + 10, y1 + 50, x1 + 90, y1 + 200), 0.9)
    return [tracked(tid, box)], no_helmet, vest


def frame_bare(*tids_boxes):
    dets = FrameDets()
    for tid, box in tids_boxes:
        persons, nh, vest = bare(tid, box)
        dets.persons += persons
        dets.no_helmet.append(nh)
        dets.vest.append(vest)
    return dets


def frame_ok(tid=1):
    return FrameDets([tracked(tid)], helmet=[WORN_HELMET], vest=[VEST_ON_TORSO])


def test_short_violation_below_window_raises_nothing():
    opened, closed, obs = run([frame_bare((1, PERSON))] * 15 + [frame_ok()] * 20)  # 1.5 s bare
    assert opened == [] and closed == []
    assert {o.item: o.outcome for o in obs} == {"helmet": "compliant", "vest": "compliant"}


def test_one_episode_per_continuous_violation():
    frames = [frame_ok()] * 5 + [frame_bare((1, PERSON))] * 40 + [frame_ok()] * 20  # bare from 0.5 s to 4.4 s
    opened, closed, obs = run(frames)
    assert len(opened) == 1 and len(closed) == 1
    ep = closed[0]
    assert (ep.type, ep.track_id) == ("no_helmet", 1)
    assert ep.start_s == pytest.approx(0.5)
    assert ep.alert_s == pytest.approx(2.5)  # start + 2 s window
    assert ep.end_s == pytest.approx(4.4)
    assert ep.confidence == 0.7
    assert {o.item: o.outcome for o in obs} == {"helmet": "violation", "vest": "compliant"}


def test_brief_dropout_does_not_split_the_episode():
    gap = [FrameDets([tracked(1)], vest=[VEST_ON_TORSO])] * 5  # 0.5 s with no helmet evidence
    frames = [frame_bare((1, PERSON))] * 30 + gap + [frame_bare((1, PERSON))] * 30
    opened, closed, _ = run(frames)
    assert len(opened) == 1 and len(closed) == 1
    assert closed[0].end_s == pytest.approx(6.4)


def test_new_episode_after_the_violation_clears():
    frames = [frame_bare((1, PERSON))] * 25 + [frame_ok()] * 15 + [frame_bare((1, PERSON))] * 25
    opened, closed, _ = run(frames)
    assert len(opened) == 2
    assert [e.start_s for e in closed] == pytest.approx([0.0, 4.0])


def test_two_people_violating_at_once_get_their_own_episodes():
    other = (300, 100, 400, 400)
    opened, closed, _ = run([frame_bare((1, PERSON), (2, other))] * 30)
    assert sorted(e.track_id for e in opened) == [1, 2]
    assert len(closed) == 2


def test_person_out_of_view_longer_than_clear_starts_a_new_run():
    empty = [FrameDets()] * 15  # 1.5 s with nobody in view (< track timeout)
    frames = [frame_bare((1, PERSON))] * 15 + empty + [frame_bare((1, PERSON))] * 15
    opened, _, _ = run(frames)
    assert opened == []  # two 1.5 s runs, never 2 s continuous


def test_track_timeout_closes_episode_and_reports_observation():
    pipe = Pipeline(config=PipelineConfig(window_s=1.0, clear_s=1.0, track_timeout_s=2.0), tracker=object())
    for n in range(20):
        pipe.step(frame_bare((1, PERSON)), n / FPS)
    r = pipe.step(FrameDets(), 4.5)  # gone for 2.6 s
    assert [e.type for e in r.closed] == ["no_helmet"]
    assert {o.item: o.outcome for o in r.observations} == {"helmet": "violation", "vest": "compliant"}
    assert pipe.tracks == {}


def test_untracked_people_are_ignored_by_the_time_window():
    dets = frame_bare((None, PERSON))
    opened, closed, obs = run([dets] * 40)
    assert opened == [] and obs == []


def test_single_image_mode_alerts_immediately_per_person():
    pipe = Pipeline(config=PipelineConfig(window_s=0.0))  # no tracker: one track per person
    dets = frame_bare((None, PERSON), (None, (300, 100, 400, 400)))
    frame = np.zeros((500, 500, 3), np.uint8)
    r = pipe.step(dets, 0.0, frame)
    assert [e.track_id for e in r.opened] == [1, 2]
    assert all(e.snapshot.startswith(b"\xff\xd8") for e in r.opened)  # annotated JPEG
    closed, obs = pipe.finish()
    assert [(e.start_s, e.end_s) for e in closed] == [(0.0, 0.0), (0.0, 0.0)]
    assert compliance(obs)["helmet"] == {"compliant": 0, "violation": 2, "unknown": 0, "rate": 0.0}
    assert compliance(obs)["vest"]["rate"] == 1.0


def test_real_bytetrack_keeps_one_id_for_a_walking_person():
    from services.tracker import PersonTracker

    tracker = PersonTracker("bytetrack")
    pipe = Pipeline(config=PipelineConfig(window_s=2.0), tracker=tracker)
    frame = np.zeros((480, 640, 3), np.uint8)
    for n in range(40):  # walks right 3 px per frame for 4 s
        box = (100 + 3 * n, 100, 200 + 3 * n, 400)
        dets = frame_bare((None, box))
        tracker.update(dets.persons, frame)
        pipe.step(dets, n / FPS, frame)
    closed, _ = pipe.finish()
    assert len(closed) == 1
    assert closed[0].track_id is not None


def test_group_box_spanning_two_people_is_dropped():
    from services.pipeline import drop_group_boxes

    a, b = person((0, 100, 300, 480)), person((320, 120, 620, 480))
    group = person((0, 20, 630, 480))  # covers both
    big_single = person((0, 0, 640, 480))  # contains only `a` and `b`... also a group
    kept = drop_group_boxes([a, b, group])
    assert kept == [a, b]
    assert drop_group_boxes([a, person((50, 150, 250, 470))]) == [a, person((50, 150, 250, 470))]  # one inside: kept
    assert big_single not in drop_group_boxes([a, b, big_single])


def test_load_yolo_reads_the_onnx_task_from_metadata(monkeypatch):
    """A pose model exported under a name without '-pose' must still load as pose."""
    import sys
    from types import SimpleNamespace

    from services.pipeline import load_yolo

    calls = []
    meta = SimpleNamespace(custom_metadata_map={"task": "pose", "names": "{0: 'person'}"})
    fake_ort = SimpleNamespace(InferenceSession=lambda path, providers: SimpleNamespace(get_modelmeta=lambda: meta))
    fake_ultra = SimpleNamespace(YOLO=lambda path, task=None: calls.append((path, task)) or "model")
    monkeypatch.setitem(sys.modules, "onnxruntime", fake_ort)
    monkeypatch.setitem(sys.modules, "ultralytics", fake_ultra)

    assert load_yolo("people.onnx") == "model"
    load_yolo("helmet.pt")
    assert calls == [("people.onnx", "pose"), ("helmet.pt", None)]

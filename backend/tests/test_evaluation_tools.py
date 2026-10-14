"""ai-model/training/evaluate.py event scoring and split_by_camera.py grouping (no weights)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ai-model" / "training"))

from evaluate import GTEpisode, score_events  # noqa: E402
from split_by_camera import assign_groups, group_key  # noqa: E402


def test_event_scoring_tp_fp_duplicates_and_time_to_alert():
    gt = [
        GTEpisode("no_helmet", 10.0, 20.0),
        GTEpisode("no_helmet", 40.0, 41.0),  # 1 s: too short for a 2 s window
        GTEpisode("no_vest", 5.0, 30.0),
    ]
    alerts = [
        ("no_helmet", 12.5),  # TP, 2.5 s after start
        ("no_helmet", 16.0),  # duplicate on the same episode (e.g. ID switch)
        ("no_vest", 7.0),     # TP, 2.0 s
        ("no_vest", 60.0),    # FP
    ]
    s = score_events(alerts, gt, window_s=2.0, tolerance_s=1.0)
    assert (s["true_positives"], s["false_positives"], s["duplicate_alerts"]) == (2, 1, 1)
    assert s["precision"] == 0.5 and s["precision_ignoring_duplicates"] == 0.75
    assert s["recall"] == pytest.approx(2 / 3, abs=1e-4)
    assert s["recall_alertable"] == 1.0  # the 1 s episode is excluded
    assert s["duplicates_per_detected_episode"] == 0.5
    assert s["time_to_alert_s"] == {"mean": 2.25, "median": 2.25, "max": 2.5}


def test_simultaneous_episodes_are_each_matched_once():
    gt = [GTEpisode("no_vest", 0.0, 10.0), GTEpisode("no_vest", 1.0, 10.0)]  # two people at once
    s = score_events([("no_vest", 2.0), ("no_vest", 3.0)], gt, window_s=2.0)
    assert (s["true_positives"], s["duplicate_alerts"], s["false_positives"]) == (2, 0, 0)


def test_wrong_type_alert_is_a_false_positive():
    s = score_events([("no_vest", 5.0)], [GTEpisode("no_helmet", 0.0, 10.0)], window_s=2.0)
    assert (s["true_positives"], s["false_positives"], s["recall"]) == (0, 1, 0.0)


def test_group_key_strips_frame_numbers_and_roboflow_suffix():
    assert group_key("webcam_s03_000417.jpg") == "webcam_s03"
    assert group_key("frame_0012_jpg.rf.9f3c2a.jpg") == "frame"
    assert group_key("site-cam2-0001.png") == "site-cam2"
    assert group_key("IMG_2041.jpg", r"^(?P<group>IMG)") == "IMG"
    assert group_key("no_digits.jpg") == "no_digits"


def test_assign_groups_never_splits_a_group_and_is_seeded():
    sizes = {f"cam{i}": 10 + i for i in range(20)}
    a = assign_groups(sizes, test_frac=0.2, val_frac=0.1, seed=42)
    assert a == assign_groups(sizes, test_frac=0.2, val_frac=0.1, seed=42)
    assert set(a) == set(sizes) and set(a.values()) == {"train", "val", "test"}
    total = sum(sizes.values())
    test_images = sum(n for g, n in sizes.items() if a[g] == "test")
    assert 0.2 * total <= test_images < 0.2 * total + max(sizes.values())
    assert a != assign_groups(sizes, test_frac=0.2, val_frac=0.1, seed=7)

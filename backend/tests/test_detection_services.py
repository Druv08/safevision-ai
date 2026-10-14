"""Backend image and video paths through the shared pipeline, with a fake detector (no weights)."""

import cv2
import numpy as np
from fake_supabase import VIEWER

from services import detection_service, video_detection_service
from services.pipeline import Det, FrameDets, Person


def bare_head_person(x=100):
    """A person with a no_helmet box on the head and a vest on the torso."""
    return (
        Person((x, 100, x + 100, 400), 0.9),
        Det((x + 30, 95, x + 70, 140), 0.7),
        Det((x + 10, 150, x + 90, 300), 0.9),
    )


def fake_detector(n_bare=1, n_ok=0, move=0):
    """Callable like services.pipeline.Detector; people move `move` px per call."""
    calls = {"n": 0}

    def detect(frame):
        dets = FrameDets()
        shift = move * calls["n"]
        calls["n"] += 1
        for k in range(n_bare + n_ok):
            p, nh, vest = bare_head_person(50 + 200 * k + shift)
            dets.persons.append(p)
            dets.vest.append(vest)
            if k < n_bare:
                dets.no_helmet.append(nh)
            else:
                x = p.box[0]
                dets.helmet.append(Det((x + 30, 95, x + 70, 140), 0.85))
        return dets

    return detect


def test_image_logs_one_row_per_violating_person_and_records_compliant_ones(sb, monkeypatch):
    monkeypatch.setattr(detection_service, "get_detector", lambda: fake_detector(n_bare=1, n_ok=1))
    detections, summary = detection_service.detect_image(np.zeros((480, 640, 3), np.uint8), "camera")

    assert summary == {"total_persons": 2, "helmet_worn": 1, "no_helmet": 1, "vest_worn": 2, "no_vest": 0,
                       "zone_intrusions": 0}
    assert all(len(d["box"]) == 4 for d in detections)
    rows = sb.tables["violations"]
    assert [(r["type"], r["source"], r["track_id"]) for r in rows] == [("no_helmet", "camera", None)]
    assert (rows[0]["episode_start_s"], rows[0]["episode_end_s"]) == (0.0, 0.0)
    assert rows[0]["screenshot_path"] in sb.objects  # one annotated screenshot
    outcomes = sorted((o["item"], o["outcome"]) for o in sb.tables["observations"])
    assert outcomes == [("helmet", "compliant"), ("helmet", "violation"), ("vest", "compliant"), ("vest", "compliant")]


def write_video(path, seconds, fps=10):
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), fps, (640, 480))
    for _ in range(seconds * fps):
        writer.write(np.zeros((480, 640, 3), np.uint8))
    writer.release()


def test_video_logs_one_episode_per_tracked_person(sb, monkeypatch, tmp_path):
    path = tmp_path / "clip.avi"
    write_video(path, seconds=5)
    # Two bare-headed people walking for the whole clip: two episodes, not one per frame.
    monkeypatch.setattr(video_detection_service, "get_detector", lambda: fake_detector(n_bare=2, move=2))

    result = video_detection_service.detect_video(path, "video")

    assert result["frames_processed"] == 50
    assert result["helmet_violations"] == 2 and result["vest_violations"] == 0
    assert result["people_tracked"] == 2
    assert result["compliance"]["helmet"]["violation"] == 2 and result["compliance"]["vest"]["rate"] == 1.0
    rows = sb.tables["violations"]
    assert len(rows) == 2
    assert len({r["track_id"] for r in rows}) == 2 and None not in {r["track_id"] for r in rows}
    for r in rows:
        assert r["episode_start_s"] < 0.3
        assert r["episode_end_s"] > 4.5
        assert r["screenshot_path"] in sb.objects
    for ev in result["events"]:
        assert ev["time"] - ev["start"] >= 2.0  # alert only after the 2 s window


def test_short_violation_in_video_logs_nothing(sb, monkeypatch, tmp_path):
    path = tmp_path / "clip.avi"
    write_video(path, seconds=1)  # 1 s < 2 s window
    monkeypatch.setattr(video_detection_service, "get_detector", lambda: fake_detector(n_bare=1))
    result = video_detection_service.detect_video(path, "video")
    assert result["total_violations"] == 0
    assert sb.tables.get("violations", []) == []
    assert [o["outcome"] for o in sb.tables["observations"] if o["item"] == "helmet"] == ["unknown"]


def test_dashboard_reports_compliance_rate(client, sb, monkeypatch):
    monkeypatch.setattr(detection_service, "get_detector", lambda: fake_detector(n_bare=1, n_ok=3))
    detection_service.detect_image(np.zeros((480, 900, 3), np.uint8))
    body = client.get("/dashboard-stats", headers=VIEWER).json()
    assert body["compliance"]["helmet"] == {"compliant": 3, "violation": 1, "unknown": 0, "rate": 0.75}
    assert body["compliance"]["vest"]["rate"] == 1.0

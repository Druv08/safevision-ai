import cv2
import numpy as np

from services import detection_service, video_detection_service
from services.detection_service import evaluate

PERSON = ([100, 100, 200, 400], 0.9)
WORN_HELMET = ([130, 95, 170, 140], 0.8)  # on the head of PERSON


def test_duplicate_no_helmet_box_on_worn_helmet_is_not_logged():
    # Helmet model also fires "NO-Hardhat" over the same head: a duplicate.
    duplicate = ([132, 97, 168, 138], 0.6)
    detections, summary, violations = evaluate([WORN_HELMET], [duplicate], [], [], [PERSON])
    assert violations == []
    assert summary["helmet_worn"] == 1 and summary["no_helmet"] == 0
    assert all(d["class_id"] != 2 for d in detections)


def test_no_helmet_with_person_is_logged_once():
    no_helmet = ([130, 95, 170, 140], 0.7)
    second = ([128, 96, 172, 150], 0.55)
    _, _, violations = evaluate([], [no_helmet, second], [], [], [PERSON])
    assert violations == [("no_helmet", 0.7)]


def test_detections_without_a_person_are_not_logged():
    no_helmet = ([130, 95, 170, 140], 0.7)
    no_vest = ([110, 150, 190, 300], 0.8)
    _, _, violations = evaluate([], [no_helmet], [], [no_vest], [])
    assert violations == []


def test_helmet_held_in_hand_is_a_violation():
    held = ([185, 250, 230, 290], 0.8)  # at the person's side, waist height
    _, summary, violations = evaluate([held], [], [], [], [PERSON])
    assert violations == [("no_helmet", 0.8)]
    assert summary["no_helmet"] == 1


def test_no_vest_suppressed_by_vest():
    vest = ([110, 150, 190, 300], 0.9)
    no_vest = ([110, 150, 190, 300], 0.5)
    _, _, violations = evaluate([WORN_HELMET], [], [vest], [no_vest], [PERSON])
    assert violations == []


def write_video(path, frames, fps):
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), fps, (64, 48))
    for _ in range(frames):
        writer.write(np.zeros((48, 64, 3), np.uint8))
    writer.release()


def test_video_cooldown_uses_video_time(tmp_path, monkeypatch):
    # 6 s of video at 10 fps, processed in milliseconds. A wall-clock cooldown
    # would log once; video-time cooldown of 2 s logs at t=0, 2, 4.
    path = tmp_path / "clip.avi"
    write_video(path, frames=60, fps=10)

    saved = []
    monkeypatch.setattr(video_detection_service, "analyze_frame", lambda f: ([], {}, [("no_vest", 0.8)]))
    monkeypatch.setattr(video_detection_service, "save_violation", lambda *a: saved.append(a))
    monkeypatch.setattr(video_detection_service, "model_version", lambda: "test")
    monkeypatch.setattr(
        video_detection_service,
        "settings",
        type("S", (), {"video_cooldown_seconds": 2.0})(),
    )

    result = video_detection_service.detect_video(path)
    assert result["vest_violations"] == 3
    assert result["frames_processed"] == 60
    assert len(saved) == 3


def test_image_saves_one_row_per_violation(monkeypatch):
    saved = []
    monkeypatch.setattr(detection_service, "analyze_frame", lambda f: ([], {}, [("no_vest", 0.8), ("no_helmet", 0.7)]))
    monkeypatch.setattr(detection_service, "save_violation", lambda *a: saved.append(a[1:]))
    monkeypatch.setattr(detection_service, "model_version", lambda: "test")
    detection_service.detect_image(np.zeros((8, 8, 3), np.uint8), "camera")
    assert saved == [("no_vest", 0.8, "camera", "test"), ("no_helmet", 0.7, "camera", "test")]


def test_detections_carry_pixel_boxes_for_overlays():
    detections, _, _ = evaluate([WORN_HELMET], [], [], [], [PERSON])
    assert all(len(d["box"]) == 4 for d in detections)
    assert {d["class_id"] for d in detections} == {0, 1}

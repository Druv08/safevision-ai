import dataclasses

import cv2
import numpy as np
from fake_supabase import VIEWER

from config import settings


def jpeg_bytes():
    return cv2.imencode(".jpg", np.zeros((32, 32, 3), np.uint8))[1].tobytes()


def upload_dir_files():
    return list(settings.upload_dir.glob("*")) if settings.upload_dir.exists() else []


def test_rejects_wrong_extension(client):
    r = client.post("/detect-image", files={"image": ("notes.txt", b"hello", "text/plain")}, headers=VIEWER)
    assert r.status_code == 400
    assert "Unsupported file type" in r.json()["detail"]


def test_rejects_video_extension_on_image_route(client):
    r = client.post("/detect-image", files={"image": ("clip.mp4", b"\x00" * 32, "video/mp4")}, headers=VIEWER)
    assert r.status_code == 400


def test_rejects_fake_extension(client):
    # A text/script file renamed to .jpg must be caught by the magic-byte check.
    r = client.post("/detect-image", files={"image": ("photo.jpg", b"<?php echo 1; ?>", "image/jpeg")}, headers=VIEWER)
    assert r.status_code == 400
    assert "does not match" in r.json()["detail"]


def test_rejects_fake_video(client):
    r = client.post("/detect-video", files={"video": ("clip.webm", jpeg_bytes(), "video/webm")}, headers=VIEWER)
    assert r.status_code == 400


def test_rejects_too_large(client):
    big = b"\xff\xd8\xff" + b"\x00" * (settings.max_upload_mb * 1024 * 1024 + 1)
    r = client.post("/detect-image", files={"image": ("big.jpg", big, "image/jpeg")}, headers=VIEWER)
    assert r.status_code == 413
    assert upload_dir_files() == []  # partial file removed


def test_valid_image_without_weights_returns_503(client, sb):
    r = client.post("/detect-image", files={"image": ("ok.jpg", jpeg_bytes(), "image/jpeg")}, headers=VIEWER)
    assert r.status_code == 503
    assert "weights not found" in r.json()["detail"]
    assert upload_dir_files() == []  # temp upload deleted even on failure
    assert sb.tables.get("violations", []) == []


def test_undecodable_video_is_an_error_not_zero_violations(client):
    # Valid WebM magic bytes, garbage body: must not report "0 violations".
    r = client.post(
        "/detect-video",
        files={"video": ("clip.webm", b"\x1a\x45\xdf\xa3" + b"\x00" * 64, "video/webm")},
        headers=VIEWER,
    )
    assert r.status_code == 422
    assert upload_dir_files() == []


def test_rate_limit(client, monkeypatch):
    from routes import detection

    monkeypatch.setattr(detection, "settings", dataclasses.replace(settings, rate_limit_per_minute=2))
    detection._recent_requests.clear()
    codes = [
        client.post("/detect-image", files={"image": ("a.txt", b"x", "text/plain")}, headers=VIEWER).status_code
        for _ in range(3)
    ]
    assert codes == [400, 400, 429]
    detection._recent_requests.clear()

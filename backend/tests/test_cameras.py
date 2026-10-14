"""Camera and zone API: roles, write-only credentials, URL rules, zone validation (no real streams)."""

import dataclasses

import numpy as np
import pytest
from fake_supabase import ADMIN, VIEWER

from config import settings
from services import cameras_service, stream_service

CREDS_URL = "rtsp://bob:s3cr%2Fet@10.0.0.5:554/stream1?channel=2"
SQUARE = [[0.1, 0.1], [0.5, 0.1], [0.5, 0.5], [0.1, 0.5]]


class FakeWorker:
    """Stands in for StreamWorker: records what it was started with, no threads."""

    started = []

    def __init__(self, camera_id, url, sample_fps, zones, **kw):
        self.camera_id, self.url, self.sample_fps, self.zones = camera_id, url, sample_fps, zones
        self.status = stream_service.CameraStatus(state="running")
        self.alive = False
        FakeWorker.started.append(self)

    def start(self):
        self.alive = True

    def stop(self):
        self.alive = False

    def set_zones(self, zones):
        self.zones = zones

    def latest_frame(self):
        return np.zeros((48, 64, 3), np.uint8)


@pytest.fixture
def workers(monkeypatch):
    FakeWorker.started = []
    manager = stream_service.StreamManager(worker_cls=FakeWorker)
    monkeypatch.setattr("routes.cameras.manager", manager)
    return manager


def create(client, **body):
    return client.post("/cameras", json={"name": "Gate", "url": CREDS_URL, **body}, headers=ADMIN)


def test_credentials_are_encrypted_and_never_returned(client, sb, workers):
    r = create(client)
    assert r.status_code == 201
    cam = r.json()
    assert cam["url"] == "rtsp://10.0.0.5:554/stream1?channel=2"
    assert cam["has_credentials"] is True
    pages = [client.get(path, headers=VIEWER).text for path in ("/cameras", f"/cameras/{cam['id']}")]
    for text in [r.text, *pages]:
        assert "bob" not in text and "s3cr" not in text and "credentials" not in text.replace("has_credentials", "")

    row = sb.tables["cameras"][0]
    assert row["url"] == cam["url"] and "s3cr" not in row["credentials_enc"]
    assert cameras_service.decrypt_credentials(row["credentials_enc"]) == ("bob", "s3cr/et")
    # The worker gets the full URL back, with the password re-encoded.
    assert cameras_service.stream_url(row) == CREDS_URL
    assert "bob" not in str(sb.tables["audit_log"])


def test_separate_username_and_password_fields(client, sb, workers):
    cam = create(client, url="rtsp://cam.local/live", username="op", password="p@ss:word").json()
    row = cameras_service.get_camera(cam["id"])
    assert cameras_service.stream_url(row) == "rtsp://op:p%40ss%3Aword@cam.local/live"


@pytest.mark.parametrize("url", [
    "file:///etc/passwd", "http://cam.local/mjpeg", "/dev/video0", "rtsp:///no-host", "rtsp://cam/x y",
])
def test_rejected_urls(client, workers, url):
    r = create(client, url=url)
    assert r.status_code == 422


def test_allowed_schemes_are_configurable(client, sb, workers, monkeypatch):
    monkeypatch.setattr(cameras_service, "settings", dataclasses.replace(settings, stream_allowed_schemes=("http",)))
    assert create(client, url="http://cam.local/mjpeg").status_code == 201


def test_viewer_can_read_but_not_change(client, sb, workers):
    cam = create(client).json()
    assert client.get("/cameras", headers=VIEWER).status_code == 200
    assert client.post("/cameras", json={"name": "x", "url": "rtsp://a/b"}, headers=VIEWER).status_code == 403
    assert client.patch(f"/cameras/{cam['id']}", json={"name": "x"}, headers=VIEWER).status_code == 403
    assert client.delete(f"/cameras/{cam['id']}", headers=VIEWER).status_code == 403
    assert client.post(f"/cameras/{cam['id']}/start", headers=VIEWER).status_code == 403
    assert client.put(f"/cameras/{cam['id']}/zones", json={"zones": []}, headers=VIEWER).status_code == 403
    assert client.get("/cameras").status_code == 401


def test_editing_keeps_or_replaces_credentials(client, sb, workers):
    cam = create(client).json()
    url = lambda: cameras_service.stream_url(cameras_service.get_camera(cam["id"]))  # noqa: E731
    client.patch(f"/cameras/{cam['id']}", json={"name": "North gate"}, headers=ADMIN)
    assert url() == CREDS_URL  # untouched
    client.patch(f"/cameras/{cam['id']}", json={"password": "new"}, headers=ADMIN)
    assert url() == "rtsp://bob:new@10.0.0.5:554/stream1?channel=2"  # username kept
    r = client.patch(f"/cameras/{cam['id']}", json={"clear_credentials": True}, headers=ADMIN)
    assert r.json()["has_credentials"] is False and url() == "rtsp://10.0.0.5:554/stream1?channel=2"
    assert "new" not in str(sb.tables["audit_log"])  # the audit records that the password changed, not its value


def test_missing_secret_key_blocks_credentials_only(client, sb, workers, monkeypatch):
    monkeypatch.setattr(cameras_service, "settings", dataclasses.replace(settings, camera_secret_key=""))
    r = create(client)
    assert r.status_code == 503 and "CAMERA_SECRET_KEY" in r.json()["detail"]
    assert create(client, url="rtsp://cam.local/live").status_code == 201


def test_start_stop_and_delete(client, sb, workers):
    cam = create(client).json()
    r = client.post(f"/cameras/{cam['id']}/start", headers=ADMIN)
    assert r.status_code == 200 and r.json()["enabled"] is True
    worker = FakeWorker.started[-1]
    assert worker.url == CREDS_URL and worker.sample_fps == 5 and worker.alive
    assert r.json()["status"]["state"] == "running"

    client.post(f"/cameras/{cam['id']}/stop", headers=ADMIN)
    assert not worker.alive and cameras_service.get_camera(cam["id"])["enabled"] is False

    client.put(f"/cameras/{cam['id']}/zones", json={"zones": [{"name": "a", "policy": "none", "polygon": SQUARE}]},
               headers=ADMIN)
    assert client.delete(f"/cameras/{cam['id']}", headers=ADMIN).status_code == 200
    assert sb.tables["cameras"] == [] and sb.tables["zones"] == []
    actions = [a["action"] for a in sb.tables["audit_log"]]
    assert actions == ["camera_create", "camera_start", "camera_stop", "zones_update", "camera_delete"]


def test_enabled_on_create_starts_and_edit_restarts(client, sb, workers):
    cam = create(client, enabled=True, sample_fps=2).json()
    assert len(FakeWorker.started) == 1 and FakeWorker.started[0].sample_fps == 2
    client.patch(f"/cameras/{cam['id']}", json={"sample_fps": 4}, headers=ADMIN)
    assert len(FakeWorker.started) == 2 and FakeWorker.started[1].sample_fps == 4
    assert not FakeWorker.started[0].alive


def test_zones_are_validated_saved_and_applied_live(client, sb, workers):
    cam = create(client).json()
    client.post(f"/cameras/{cam['id']}/start", headers=ADMIN)
    zones = [
        {"name": "Loading bay", "policy": "both", "polygon": SQUARE},
        {"name": "Crane", "policy": "no_entry", "polygon": [[0.6, 0.6], [0.9, 0.6], [0.9, 0.9]]},
    ]
    r = client.put(f"/cameras/{cam['id']}/zones", json={"zones": zones}, headers=ADMIN)
    assert r.status_code == 200
    assert [(z["name"], z["policy"]) for z in client.get(f"/cameras/{cam['id']}/zones", headers=VIEWER).json()] == [
        ("Loading bay", "both"), ("Crane", "no_entry")]
    live = FakeWorker.started[-1].zones
    assert live.requirement((0.7, 0.7)).no_entry_zone is not None

    bad = [{"name": "bow tie", "policy": "vest", "polygon": [[0.1, 0.1], [0.6, 0.6], [0.6, 0.1], [0.1, 0.6]]}]
    r = client.put(f"/cameras/{cam['id']}/zones", json={"zones": bad}, headers=ADMIN)
    assert r.status_code == 422 and "cross" in r.json()["detail"]
    assert len(client.get(f"/cameras/{cam['id']}/zones", headers=VIEWER).json()) == 2  # unchanged

    for body in ({"zones": [{"name": "x", "policy": "hardhat", "polygon": SQUARE}]},
                 {"zones": [{"name": "x", "policy": "vest", "polygon": [[0.1, 0.1], [2, 0.1], [0.5, 0.5]]}]}):
        assert client.put(f"/cameras/{cam['id']}/zones", json=body, headers=ADMIN).status_code == 422


def test_snapshot_from_running_worker_or_unreachable_camera(client, sb, workers, monkeypatch):
    cam = create(client).json()
    monkeypatch.setattr("routes.cameras.grab_frame", lambda camera: None)
    assert client.get(f"/cameras/{cam['id']}/snapshot", headers=VIEWER).status_code == 503
    client.post(f"/cameras/{cam['id']}/start", headers=ADMIN)
    r = client.get(f"/cameras/{cam['id']}/snapshot", headers=VIEWER)
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg" and r.content[:2] == b"\xff\xd8"


def test_unknown_camera_is_404(client, sb, workers):
    missing = "00000000-0000-0000-0000-000000000000"
    assert client.get(f"/cameras/{missing}", headers=VIEWER).status_code == 404
    assert client.put(f"/cameras/{missing}/zones", json={"zones": []}, headers=ADMIN).status_code == 404


def test_redact_hides_credentials_in_messages():
    assert cameras_service.redact("failed to open rtsp://bob:pw@cam/x") == "failed to open rtsp://***@cam/x"


def test_start_failure_is_reported_in_status(client, sb, workers, monkeypatch):
    cam = create(client).json()
    monkeypatch.setattr(cameras_service, "settings", dataclasses.replace(settings, camera_secret_key=""))
    r = client.post(f"/cameras/{cam['id']}/start", headers=ADMIN)
    assert r.status_code == 503
    status = client.get(f"/cameras/{cam['id']}", headers=VIEWER).json()["status"]
    assert status["state"] == "error" and "CAMERA_SECRET_KEY" in status["last_error"]


def test_new_credentials_replace_ones_that_no_longer_decrypt(client, sb, workers, monkeypatch):
    cam = create(client).json()
    from cryptography.fernet import Fernet

    rotated = dataclasses.replace(settings, camera_secret_key=Fernet.generate_key().decode())
    monkeypatch.setattr(cameras_service, "settings", rotated)
    r = client.patch(f"/cameras/{cam['id']}", json={"password": "only-half"}, headers=ADMIN)
    assert r.status_code == 503  # keeping the old username needs the old key
    r = client.patch(f"/cameras/{cam['id']}", json={"username": "bob", "password": "fresh"}, headers=ADMIN)
    assert r.status_code == 200
    assert cameras_service.stream_url(cameras_service.get_camera(cam["id"])).startswith("rtsp://bob:fresh@")

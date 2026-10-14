import pytest
from fake_supabase import ADMIN, VIEWER

from services.violations_service import create_violation

PROTECTED = [
    ("get", "/"),
    ("get", "/violations"),
    ("get", "/dashboard-stats"),
    ("get", "/download-violations"),
    ("post", "/detect-image"),
    ("post", "/detect-video"),
    ("get", "/violations/00000000-0000-0000-0000-000000000000/evidence"),
    ("patch", "/violations/00000000-0000-0000-0000-000000000000"),
    ("delete", "/violations/00000000-0000-0000-0000-000000000000"),
]


@pytest.mark.parametrize("method,path", PROTECTED)
def test_rejects_missing_token(client, method, path):
    assert client.request(method, path).status_code == 401


@pytest.mark.parametrize("method,path", PROTECTED)
def test_rejects_invalid_token(client, method, path):
    r = client.request(method, path, headers={"Authorization": "Bearer forged"})
    assert r.status_code == 401


def test_rejects_user_without_profile(client, sb):
    sb.add_user("orphan-token", role=None)
    r = client.get("/violations", headers={"Authorization": "Bearer orphan-token"})
    assert r.status_code == 403


def test_health_needs_no_token(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["model"]["loaded"] is False  # no weights in the test env
    assert body["database"]["connected"] is True
    assert "free_mb" in body["disk"]
    assert body["status"] == "degraded"


def test_viewer_can_read(client):
    assert client.get("/violations", headers=VIEWER).status_code == 200


def test_viewer_cannot_change_or_delete(client, sb):
    v = create_violation("no_vest", 0.8, "image", None, "test")
    assert client.patch(f"/violations/{v['id']}", json={"status": "closed"}, headers=VIEWER).status_code == 403
    assert client.delete(f"/violations/{v['id']}", headers=VIEWER).status_code == 403
    assert sb.tables["violations"][0]["status"] == "new"


def test_admin_can_delete_and_it_is_audited(client, sb):
    from services.storage_service import upload_screenshot

    key = upload_screenshot(b"\xff\xd8\xff fake jpeg")
    v = create_violation("no_vest", 0.8, "image", key, "test")
    r = client.delete(f"/violations/{v['id']}", headers=ADMIN)
    assert r.status_code == 200
    assert sb.tables["violations"] == []
    assert key not in sb.objects
    assert sb.tables["audit_log"][-1]["action"] == "delete"
    assert sb.tables["audit_log"][-1]["user_id"] == sb.admin_id

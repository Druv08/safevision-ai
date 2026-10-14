from datetime import datetime, timedelta, timezone

from fake_supabase import ADMIN, VIEWER

from services.storage_service import upload_screenshot
from services.violations_service import create_violation


def test_create_and_list_with_legacy_keys(client):
    create_violation("no_helmet", 0.91, "image", None, "v-test")
    r = client.get("/violations", headers=VIEWER)
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 1
    v = body["violations"][0]
    assert v["type"] == "no_helmet" and v["status"] == "new"
    # keys the frontend has always relied on
    assert v["violation_type"] == "Helmet Missing"
    assert v["severity"] == "High"
    assert v["violation_id"] == v["id"]
    assert v["timestamp"] == v["created_at"]


def test_create_rejects_bad_values():
    import pytest

    with pytest.raises(ValueError):
        create_violation("no_gloves", 0.5, "image", None, "v")
    with pytest.raises(ValueError):
        create_violation("no_vest", 0.5, "/etc/passwd", None, "v")


def test_list_filters_search_and_pagination(client, sb):
    now = datetime.now(timezone.utc)
    for i in range(5):
        create_violation("no_vest", 0.5, "video", None, "v", created_at=now - timedelta(days=i))
    create_violation("no_helmet", 0.7, "image", None, "v", note="gate three")

    assert client.get("/violations?type=no_helmet", headers=VIEWER).json()["count"] == 1
    assert client.get("/violations?q=gate", headers=VIEWER).json()["count"] == 1

    since = (now - timedelta(days=1, hours=1)).isoformat()
    r = client.get("/violations", params={"type": "no_vest", "date_from": since}, headers=VIEWER)
    assert r.json()["count"] == 2

    page = client.get("/violations?page=2&page_size=4", headers=VIEWER).json()
    assert page["count"] == 6 and len(page["violations"]) == 2

    # newest first by default, oldest first on request
    rows = client.get("/violations", headers=VIEWER).json()["violations"]
    assert rows == sorted(rows, key=lambda v: v["created_at"], reverse=True)
    rows = client.get("/violations?sort=oldest", headers=VIEWER).json()["violations"]
    assert rows == sorted(rows, key=lambda v: v["created_at"])


def test_acknowledge_and_close(client, sb):
    v = create_violation("no_vest", 0.6, "camera", None, "v")
    body = {"status": "acknowledged", "note": "spoke to worker"}
    r = client.patch(f"/violations/{v['id']}", json=body, headers=ADMIN)
    assert r.status_code == 200
    assert r.json()["status"] == "acknowledged"
    assert r.json()["acknowledged_by"] == sb.admin_id
    assert r.json()["note"] == "spoke to worker"

    r = client.patch(f"/violations/{v['id']}", json={"status": "closed"}, headers=ADMIN)
    assert r.json()["status"] == "closed" and r.json()["closed_by"] == sb.admin_id
    assert [a["action"] for a in sb.tables["audit_log"]] == ["acknowledged", "closed"]


def test_status_validation_and_missing_row(client):
    v = create_violation("no_vest", 0.6, "camera", None, "v")
    assert client.patch(f"/violations/{v['id']}", json={"status": "new"}, headers=ADMIN).status_code == 422
    missing = "00000000-0000-0000-0000-000000000000"
    assert client.patch(f"/violations/{missing}", json={"status": "closed"}, headers=ADMIN).status_code == 404


def test_evidence_returns_signed_url_and_audits(client, sb):
    key = upload_screenshot(b"\xff\xd8\xff jpeg")
    assert not key.startswith("/") and ":" not in key  # server-generated object key, not a path
    v = create_violation("no_helmet", 0.9, "image", key, "v")

    r = client.get(f"/violations/{v['id']}/evidence", headers=VIEWER)
    assert r.status_code == 200
    assert key in r.json()["url"] and r.json()["expires_in"] == 300
    log = sb.tables["audit_log"][-1]
    assert (log["action"], log["user_id"], log["target_id"]) == ("view_evidence", sb.viewer_id, v["id"])


def test_evidence_404_without_screenshot(client):
    v = create_violation("no_helmet", 0.9, "image", None, "v")
    assert client.get(f"/violations/{v['id']}/evidence", headers=VIEWER).status_code == 404


def test_no_public_screenshot_mount(client):
    assert client.get("/screenshots/anything.jpg").status_code == 404


def test_export_404_when_empty(client, sb):
    r = client.get("/download-violations", headers=VIEWER)
    assert r.status_code == 404
    assert r.json()["detail"] == "There are no violations to export."


def test_export_csv_is_audited(client, sb):
    create_violation("no_vest", 0.6, "camera", None, "v")
    r = client.get("/download-violations", headers=VIEWER)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    lines = r.text.strip().splitlines()
    assert lines[0].startswith("id,created_at,type") and len(lines) == 2
    assert sb.tables["audit_log"][-1]["action"] == "export"


def test_dashboard_stats(client):
    create_violation("no_vest", 0.6, "camera", None, "v")
    create_violation("no_vest", 0.6, "camera", None, "v")
    create_violation("no_helmet", 0.6, "camera", None, "v")
    body = client.get("/dashboard-stats", headers=VIEWER).json()
    assert body["total_violations"] == 3
    assert body["no_vest_cases"] == 2 and body["no_helmet_cases"] == 1
    assert body["system_status"] == "Model unavailable"


def test_list_filters_by_status_and_source(client, sb):
    a = create_violation("no_vest", 0.6, "camera", None, "v")
    create_violation("no_vest", 0.6, "image", None, "v")
    client.patch(f"/violations/{a['id']}", json={"status": "closed"}, headers=ADMIN)

    assert client.get("/violations?status=closed", headers=VIEWER).json()["count"] == 1
    assert client.get("/violations?status=new&source=image", headers=VIEWER).json()["count"] == 1
    assert client.get("/violations?source=video", headers=VIEWER).json()["count"] == 0
    assert client.get("/violations?status=bogus", headers=VIEWER).status_code == 422

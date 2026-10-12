"""Hash at capture, verification, the evidence export and the append-only audit log."""

import hashlib
import io
import json
import sqlite3
import zipfile

import cv2
import numpy as np
import pytest
from fake_supabase import ADMIN, VIEWER, FakeAPIError

from services import db, evidence
from services import violations_service as vs
from services.pipeline import Episode


def jpeg(seed=1) -> bytes:
    img = np.random.default_rng(seed).integers(0, 255, (40, 60, 3), dtype=np.uint8)
    return cv2.imencode(".jpg", img)[1].tobytes()


def episode(shot=None, original=None):
    return Episode("no_helmet", 7, 1.0, 3.0, 4.0, 0.88, (0, 0, 8, 8), shot or jpeg(), None, original)


def test_hash_and_model_version_are_recorded_at_capture(sb):
    shot = jpeg()
    row = vs.save_episode(episode(shot), "video", "safevision_yolov8n_5class_v2+yolov8n")
    assert row["screenshot_sha256"] == hashlib.sha256(shot).hexdigest()
    assert row["model_version"] == "safevision_yolov8n_5class_v2+yolov8n"
    assert hashlib.sha256(sb.objects[row["screenshot_path"]]).hexdigest() == row["screenshot_sha256"]


def test_verify_detects_a_changed_or_missing_screenshot(client, sb):
    row = vs.save_episode(episode(), "video", "m1")
    url = f"/violations/{row['id']}/verify"
    assert client.get(url, headers=VIEWER).json()["status"] == "ok"

    sb.objects[row["screenshot_path"]] = jpeg(seed=2)  # someone replaced the file in the bucket
    body = client.get(url, headers=VIEWER).json()
    assert body["status"] == "mismatch" and body["expected"] == row["screenshot_sha256"] != body["actual"]

    del sb.objects[row["screenshot_path"]]
    assert client.get(url, headers=VIEWER).json()["status"] == "missing"


def test_verify_reports_retention_deletion_and_old_records():
    assert evidence.verify({"screenshot_path": None, "screenshot_deleted_at": "2026-01-01"})["status"] == \
        "deleted_by_retention"
    assert evidence.verify({"screenshot_path": None})["status"] == "no_screenshot"


def test_export_zip_has_image_metadata_hashes_and_audit_trail(client, sb):
    shot = jpeg()
    row = vs.save_episode(episode(shot, original=jpeg(3)), "video", "m1")
    client.patch(f"/violations/{row['id']}", json={"status": "action_taken", "note": "Helmet issued at gate",
                                                   "cause": "ppe_not_issued"}, headers=ADMIN)
    assert client.get(f"/violations/{row['id']}/export", headers=VIEWER).status_code == 403

    r = client.get(f"/violations/{row['id']}/export", headers=ADMIN)
    assert r.status_code == 200 and r.headers["content-type"] == "application/zip"
    assert f"evidence-{row['id']}.zip" in r.headers["content-disposition"]
    z = zipfile.ZipFile(io.BytesIO(r.content))
    assert sorted(z.namelist()) == ["README.txt", "SHA256SUMS", "audit_trail.json", "metadata.json", "screenshot.jpg"]

    assert z.read("screenshot.jpg") == shot
    meta = json.loads(z.read("metadata.json"))
    assert meta["screenshot"] == {"file": "screenshot.jpg", "sha256_at_capture": row["screenshot_sha256"],
                                  "sha256_at_export": row["screenshot_sha256"], "integrity": "ok"}
    assert meta["record"]["model_version"] == "m1" and meta["record"]["cause"] == "ppe_not_issued"
    assert "original_path" not in meta["record"]  # the unblurred original never leaves in an export
    assert meta["exported_by"]["id"] == sb.admin_id

    for line in z.read("SHA256SUMS").decode().splitlines():  # what `sha256sum -c` would check
        digest, name = line.split("  ")
        assert hashlib.sha256(z.read(name)).hexdigest() == digest

    trail = json.loads(z.read("audit_trail.json"))
    assert [a["action"] for a in trail] == ["action_taken", "export_evidence"]  # includes this export
    assert trail[0]["detail"] == {"note": "Helmet issued at gate", "cause": "ppe_not_issued"}


def test_export_of_a_record_whose_screenshot_was_deleted(client, sb):
    row = vs.save_episode(episode(), "video", "m1")
    db.update("violations", row["id"], {"screenshot_path": None, "screenshot_deleted_at": "2026-10-01T00:00:00+00:00"})
    z = zipfile.ZipFile(io.BytesIO(client.get(f"/violations/{row['id']}/export", headers=ADMIN).content))
    assert "screenshot.jpg" not in z.namelist()
    assert json.loads(z.read("metadata.json"))["screenshot"]["integrity"] == "deleted_by_retention"


def test_audit_log_is_append_only_in_sqlite(local_mode):
    db.log_audit("u1", "view_evidence", "t1", {"a": 1})
    conn = local_mode._db()
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("update audit_log set action = 'nothing'")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("delete from audit_log")
    assert db.audit_trail("t1")[0]["detail"] == {"a": 1}


def test_audit_log_is_append_only_in_supabase(sb):
    """The fake mirrors migration 0004's trigger; this checks the backend never tries."""
    db.log_audit(None, "export")
    with pytest.raises(FakeAPIError):
        sb.table("audit_log").delete().eq("action", "export").execute()
    with pytest.raises(FakeAPIError):
        sb.table("audit_log").update({"action": "x"}).eq("action", "export").execute()


def test_migration_0004_blocks_every_role_including_service_role():
    from config import PROJECT_ROOT

    sql = (PROJECT_ROOT / "supabase" / "migrations" / "0004_privacy_alerts_evidence.sql").read_text().lower()
    fn = sql.split("create or replace function public.audit_log_block_changes()")[1].split("$$;")[0]
    assert "raise exception" in fn and "service_role" not in fn and "if " not in fn  # no exemption
    assert "before truncate on public.audit_log" in sql

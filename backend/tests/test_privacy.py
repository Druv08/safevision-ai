"""Blurring, encrypted originals, retention deletion and legal hold."""

import os
import time
import uuid
from datetime import datetime, timedelta, timezone

import cv2
import numpy as np
import pytest
from fake_supabase import ADMIN, VIEWER

from services import privacy, storage_service
from services import violations_service as vs
from services.evidence import sha256
from services.pipeline import Det, Episode, FrameDets, Person, Pipeline, PipelineConfig, associate

NOW = datetime(2026, 10, 12, 12, 0, tzinfo=timezone.utc)


def jpeg(seed: int) -> bytes:
    img = np.random.default_rng(seed).integers(0, 255, (60, 80, 3), dtype=np.uint8)
    return cv2.imencode(".jpg", img)[1].tobytes()


def make(created_at, *, hold=False, original=True, original_expires_at=None):
    """A violation with a stored screenshot (and an encrypted original) created at `created_at`."""
    shot = jpeg(1)
    extra = privacy.store_original(jpeg(2), now=created_at) if original else {}
    if original_expires_at:
        extra["original_expires_at"] = original_expires_at
    row = vs.create_violation("no_helmet", 0.9, "camera", storage_service.upload_screenshot(shot), "m1",
                              created_at=created_at, screenshot_sha256=sha256(shot), **extra)
    if hold:
        vs.set_legal_hold(row["id"], True, "insurance claim")
    return vs.get_violation(row["id"])


# ---------------------------------------------------------------------------
# Blurring
# ---------------------------------------------------------------------------
def test_blur_pixelates_people_and_leaves_the_rest():
    frame = np.random.default_rng(0).integers(0, 255, (480, 640, 3), dtype=np.uint8)
    statuses, _ = associate(FrameDets([Person((100, 100, 200, 400), 0.9)]))
    out = privacy.blur_people(frame, statuses)

    assert np.array_equal(out[:, 260:], frame[:, 260:])  # nobody there: unchanged
    body = out[150:390, 110:190]
    assert len(np.unique(body.reshape(-1, 3), axis=0)) < 0.05 * body.shape[0] * body.shape[1]  # a coarse grid
    assert not np.array_equal(out[100:400, 100:200], frame[100:400, 100:200])
    assert np.array_equal(frame, np.random.default_rng(0).integers(0, 255, (480, 640, 3), dtype=np.uint8))  # copy


def test_pipeline_blurs_the_evidence_and_keeps_the_original_separately():
    frame = np.random.default_rng(1).integers(0, 255, (480, 640, 3), dtype=np.uint8)
    dets = FrameDets([Person((100, 100, 200, 400), 0.9)], no_helmet=[Det((130, 95, 170, 140), 0.8)])
    blurred = Pipeline(None, PipelineConfig(window_s=0), redact=privacy.blur_people).step(dets, 0.0, frame).opened[0]
    plain = Pipeline(None, PipelineConfig(window_s=0)).step(dets, 0.0, frame).opened[0]

    assert plain.original is None and blurred.original is not None
    assert blurred.original == plain.snapshot  # the original is the usual annotated frame
    assert blurred.snapshot != blurred.original
    img = cv2.imdecode(np.frombuffer(blurred.snapshot, np.uint8), cv2.IMREAD_COLOR)
    assert img.shape == frame.shape


# ---------------------------------------------------------------------------
# Encrypted originals (Supabase path, fake client)
# ---------------------------------------------------------------------------
def test_original_is_stored_encrypted_and_only_admins_can_view_it(client, sb):
    original = jpeg(2)
    row = vs.save_episode(Episode("no_helmet", 1, 0, 2, 3, 0.9, (0, 0, 8, 8), jpeg(1), None, original), "video", "m1")

    stored = sb.objects[row["original_path"]]
    assert stored != original and original[:3] not in stored  # encrypted at rest, not a JPEG
    assert row["original_sha256"] == sha256(original)

    api = client.get("/violations", headers=VIEWER).json()["violations"][0]
    assert api["has_original"] is True and "original_path" not in api  # storage key stays on the server

    assert client.get(f"/violations/{row['id']}/original", headers=VIEWER).status_code == 403
    r = client.get(f"/violations/{row['id']}/original", headers=ADMIN)
    assert r.status_code == 200 and r.content == original
    assert r.headers["content-type"] == "image/jpeg" and r.headers["cache-control"] == "no-store"
    log = sb.tables["audit_log"][-1]
    assert (log["action"], log["user_id"], log["target_id"]) == ("view_original", sb.admin_id, row["id"])


def test_expired_original_is_gone_and_viewing_it_is_not_logged(client, sb):
    row = make(NOW - timedelta(days=5))  # kept 72 h: expired two days ago
    assert vs.to_api(row)["has_original"] is False
    r = client.get(f"/violations/{row['id']}/original", headers=ADMIN)
    assert r.status_code == 410 and "expired" in r.json()["detail"]
    assert not [a for a in sb.tables.get("audit_log", []) if a["action"] == "view_original"]


def test_without_evidence_key_no_original_is_kept(sb, set_settings):
    set_settings(evidence_secret_key="")
    row = vs.save_episode(Episode("no_vest", 1, 0, 2, 3, 0.9, (0, 0, 8, 8), jpeg(1), None, jpeg(2)), "video", "m1")
    assert row.get("original_path") is None and len(sb.objects) == 1  # only the blurred screenshot


# ---------------------------------------------------------------------------
# Retention and legal hold
# ---------------------------------------------------------------------------
def test_retention_deletes_old_screenshots_except_on_legal_hold(local_mode, tmp_path):
    old = make(NOW - timedelta(days=31))
    held = make(NOW - timedelta(days=200), hold=True)
    recent = make(NOW - timedelta(days=29))

    assert privacy.run_retention(NOW) == {"screenshots": 1, "originals": 1, "uploads": 0, "errors": 0}

    gone = vs.get_violation(old["id"])
    assert gone["screenshot_path"] is None and gone["original_path"] is None
    assert gone["screenshot_deleted_at"] and gone["screenshot_sha256"] == old["screenshot_sha256"]  # hash kept
    assert not (tmp_path / "shots" / old["screenshot_path"]).exists()
    assert not (tmp_path / "shots" / old["original_path"]).exists()
    # on hold: screenshot AND original kept, however old
    assert vs.get_violation(held["id"])["screenshot_path"] == held["screenshot_path"]
    assert (tmp_path / "shots" / held["original_path"]).exists()
    assert privacy.read_original(vs.get_violation(held["id"]), NOW) == jpeg(2)  # viewable past expiry on hold
    # recent: screenshot kept, its original (72 h) already expired and purged
    kept = vs.get_violation(recent["id"])
    assert kept["screenshot_path"] == recent["screenshot_path"] and kept["original_path"] is None

    trail = local_mode.select("audit_log", order="id")
    assert [(a["action"], a["target_id"]) for a in trail if a["action"].startswith(("retention", "original"))] == [
        ("retention_delete", old["id"]), ("original_expired", recent["id"])]
    assert privacy.run_retention(NOW) == {"screenshots": 0, "originals": 0, "uploads": 0, "errors": 0}  # idempotent


def test_lifting_legal_hold_lets_retention_delete(local_mode):
    held = make(NOW - timedelta(days=60), hold=True)
    assert privacy.run_retention(NOW)["screenshots"] == 0
    vs.set_legal_hold(held["id"], False)
    assert privacy.run_retention(NOW)["screenshots"] == 1
    assert vs.get_violation(held["id"])["screenshot_path"] is None


def test_retention_on_supabase_uses_the_same_rules(sb):
    old, held = make(NOW - timedelta(days=40)), make(NOW - timedelta(days=40), hold=True)
    assert privacy.run_retention(NOW)["screenshots"] == 1
    assert old["screenshot_path"] not in sb.objects and held["screenshot_path"] in sb.objects
    row = vs.get_violation(old["id"])
    assert row["screenshot_path"] is None and row["screenshot_deleted_at"].startswith("2026-10-12")


def test_retention_cleans_only_old_server_named_uploads(local_mode, set_settings, tmp_path):
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    set_settings(upload_dir=uploads, db_disabled=True, auth_disabled=True)
    old_server = uploads / f"{uuid.uuid4().hex}.mp4"
    new_server = uploads / f"{uuid.uuid4().hex}.jpg"
    old_user = uploads / "site-walkthrough.mp4"  # not a name save_upload() generates: never touched
    for p in (old_server, new_server, old_user):
        p.write_bytes(b"x")
    month_ago = time.time() - 31 * 86400
    os.utime(old_server, (month_ago, month_ago))
    os.utime(old_user, (month_ago, month_ago))

    assert privacy.run_retention()["uploads"] == 1
    assert not old_server.exists() and new_server.exists() and old_user.exists()


def test_legal_hold_api_requires_reason_blocks_delete_and_is_audited(client, sb):
    row = make(NOW)
    url = f"/violations/{row['id']}/legal-hold"
    assert client.put(url, json={"hold": True}, headers=ADMIN).status_code == 422  # reason required
    assert client.put(url, json={"hold": True, "reason": "x"}, headers=VIEWER).status_code == 403
    r = client.put(url, json={"hold": True, "reason": "claim #42"}, headers=ADMIN)
    assert r.status_code == 200 and r.json()["legal_hold"] is True

    r = client.delete(f"/violations/{row['id']}", headers=ADMIN)
    assert r.status_code == 409 and vs.get_violation(row["id"]) is not None

    client.put(url, json={"hold": False}, headers=ADMIN)
    assert client.delete(f"/violations/{row['id']}", headers=ADMIN).status_code == 200
    assert row["original_path"] not in sb.objects  # the original goes with the record
    assert [a["action"] for a in sb.tables["audit_log"]] == ["legal_hold_on", "legal_hold_off", "delete"]
    assert sb.tables["audit_log"][0]["detail"] == {"reason": "claim #42"}


@pytest.mark.parametrize("bad", ["", "not-a-key"])
def test_bad_or_missing_evidence_key_never_blocks_saving(sb, set_settings, bad):
    set_settings(evidence_secret_key=bad)
    row = vs.save_episode(Episode("no_vest", 1, 0, 2, 3, 0.9, (0, 0, 8, 8), jpeg(1), None, jpeg(2)), "video", "m1")
    assert row["screenshot_path"] and not row.get("original_path")

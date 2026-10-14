"""
Privacy protection for stored evidence.

* Blurring (PRIVACY_BLUR, on by default): every detected person is pixelated
  before the evidence screenshot is annotated: the body in a coarse grid and
  the head region (the face) in a coarser one. Boxes, labels and colours stay
  readable (a hi-vis vest is still a bright block), identities do not.
  People the model did not detect are NOT blurred.
* Originals: the unblurred, annotated frame is kept only encrypted (Fernet,
  EVIDENCE_SECRET_KEY) and only for ORIGINAL_RETENTION_HOURS (default 72), so
  an admin can check a disputed record. Every view is written to audit_log by
  the route. Without EVIDENCE_SECRET_KEY no original is kept at all.
* Retention: run_retention() deletes screenshots older than RETENTION_DAYS
  (default 30), originals past their expiry and stale upload files. Records on
  legal hold keep both. The violation rows themselves stay (with their hash),
  so counts and compliance rates still add up. A background thread runs it
  every RETENTION_INTERVAL_MINUTES (default 60; 0 = off).
"""

import functools
import logging
import re
import threading
from datetime import datetime, timedelta, timezone

import cv2
import numpy as np
from cryptography.fernet import Fernet, InvalidToken

from config import settings
from services import db, local_store, storage_service
from services.db import log_audit
from services.evidence import sha256
from supabase_client import get_supabase

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Blurring
# ---------------------------------------------------------------------------
BODY_CELLS = 12  # a person becomes a grid 12 blocks tall
HEAD_CELLS = 2  # ... and their head region 2 blocks tall


def _pixelate(img: np.ndarray, box, cells: int) -> None:
    h, w = img.shape[:2]
    x1, y1 = max(0, int(box[0])), max(0, int(box[1]))
    x2, y2 = min(w, int(round(box[2]))), min(h, int(round(box[3])))
    if x2 - x1 < 2 or y2 - y1 < 2:
        return
    block = max(4, (y2 - y1) // cells)
    small = cv2.resize(img[y1:y2, x1:x2], (max(1, (x2 - x1) // block), max(1, (y2 - y1) // block)),
                       interpolation=cv2.INTER_AREA)
    img[y1:y2, x1:x2] = cv2.resize(small, (x2 - x1, y2 - y1), interpolation=cv2.INTER_NEAREST)


def blur_people(frame: np.ndarray, statuses) -> np.ndarray:
    """Copy of the frame with every person (PersonStatus) pixelated: body coarse, head coarser."""
    out = frame.copy()
    for st in statuses:
        x1, y1, x2, y2 = st.person.box
        pad = 0.04 * max(x2 - x1, y2 - y1)
        _pixelate(out, (x1 - pad, y1 - pad, x2 + pad, y2 + pad), BODY_CELLS)
        _pixelate(out, st.head.box, HEAD_CELLS)
    return out


def redactor():
    """What the backend passes to Pipeline(redact=...): blur_people, or None when PRIVACY_BLUR=false."""
    return blur_people if settings.privacy_blur else None


# ---------------------------------------------------------------------------
# Encrypted originals
# ---------------------------------------------------------------------------
class OriginalUnavailable(Exception):
    pass


@functools.cache
def _fernet_for(key: str) -> Fernet | None:
    if not key:
        log.warning("EVIDENCE_SECRET_KEY is not set: unblurred originals are not kept")
        return None
    try:
        return Fernet(key.encode())
    except ValueError:
        log.error("EVIDENCE_SECRET_KEY is not a valid Fernet key: unblurred originals are not kept")
        return None


def _fernet() -> Fernet | None:
    return _fernet_for(settings.evidence_secret_key)


def store_original(jpeg: bytes, now: datetime | None = None) -> dict:
    """Encrypt and upload the unblurred original. Returns the violation columns to set ({} if not kept)."""
    f = _fernet()
    if f is None or settings.original_retention_hours <= 0:
        return {}
    now = now or datetime.now(timezone.utc)
    key = storage_service.upload_screenshot(f.encrypt(jpeg), prefix="originals/", ext="bin",
                                            content_type="application/octet-stream")
    return {
        "original_path": key,
        "original_sha256": sha256(jpeg),
        "original_expires_at": now + timedelta(hours=settings.original_retention_hours),
    }


def read_original(row: dict, now: datetime | None = None) -> bytes:
    """The decrypted original JPEG. Raises OriginalUnavailable with the reason."""
    if not row.get("original_path"):
        raise OriginalUnavailable("No unblurred original is kept for this record (expired, deleted or never stored).")
    expires = row.get("original_expires_at")
    if expires and not row.get("legal_hold") and datetime.fromisoformat(expires) <= (now or datetime.now(timezone.utc)):
        raise OriginalUnavailable("The unblurred original has expired.")
    f = _fernet()
    if f is None:
        raise OriginalUnavailable("EVIDENCE_SECRET_KEY is not set, so the original cannot be decrypted.")
    try:
        jpeg = f.decrypt(storage_service.download(row["original_path"]))
    except InvalidToken:
        raise OriginalUnavailable("The original cannot be decrypted (was EVIDENCE_SECRET_KEY changed?).") from None
    if row.get("original_sha256") and sha256(jpeg) != row["original_sha256"]:
        raise OriginalUnavailable("The original does not match the hash recorded at capture.")
    return jpeg


# ---------------------------------------------------------------------------
# Retention
# ---------------------------------------------------------------------------
BATCH = 200
# Only names that save_upload() generates: anything else in the folder is left alone.
_UPLOAD_NAME = re.compile(r"[0-9a-f]{32}\.(jpe?g|png|mp4|mov|avi|webm)")


def _candidates(time_col: str, path_col: str, before: datetime) -> list[dict]:
    """Violations not on legal hold, with `path_col` still set, whose `time_col` is before `before`."""
    if settings.db_disabled:
        return local_store.retention_candidates(time_col, path_col, before, BATCH)
    return (
        get_supabase().table("violations").select("*")
        .lt(time_col, before.isoformat()).eq("legal_hold", False).not_.is_(path_col, "null")
        .order(time_col).limit(BATCH).execute().data
    )


def _purge(time_col: str, before: datetime, keys: tuple[str, ...], now: datetime, action: str) -> tuple[int, int]:
    """Delete the objects in `keys` for every candidate, then clear them on the row. Returns (done, errors)."""
    done = errors = 0
    while True:
        rows = _candidates(time_col, keys[0], before)
        for row in rows:
            try:
                for k in keys:  # object first: a failed row update is retried next run, re-deleting is a no-op
                    if row.get(k):
                        storage_service.delete_object(row[k])
                changes = dict.fromkeys(keys)
                if "screenshot_path" in keys:
                    changes["screenshot_deleted_at"] = now
                db.update("violations", row["id"], changes)
                log_audit(None, action, row["id"], {"created_at": row["created_at"]})
                done += 1
            except Exception:
                errors += 1
                log.exception("retention: could not purge violation %s", row["id"])
        if errors or len(rows) < BATCH:  # stop on errors so a failing row is not retried forever
            return done, errors


def delete_stale_uploads(before: datetime) -> int:
    """Leftover upload files (normally deleted right after detection) older than `before`."""
    n = 0
    if not settings.upload_dir.is_dir():
        return 0
    for p in settings.upload_dir.iterdir():
        if p.is_file() and _UPLOAD_NAME.fullmatch(p.name) and p.stat().st_mtime < before.timestamp():
            p.unlink(missing_ok=True)
            n += 1
    return n


def run_retention(now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=settings.retention_days)
    shots, e1 = _purge("created_at", cutoff, ("screenshot_path", "original_path"), now, "retention_delete")
    originals, e2 = _purge("original_expires_at", now, ("original_path",), now, "original_expired")
    result = {"screenshots": shots, "originals": originals, "uploads": delete_stale_uploads(cutoff),
              "errors": e1 + e2}
    if any(result.values()):
        log.info("retention: %s", result)
    return result


_stop = threading.Event()


def start_retention_job() -> threading.Thread | None:
    """Run retention now and then every RETENTION_INTERVAL_MINUTES, in a daemon thread.

    ponytail: an in-process timer, like the camera workers; one backend process
    only. Use a cron job calling run_retention() if you run several.
    """
    if settings.retention_interval_minutes <= 0:
        return None
    _stop.clear()

    def loop():
        while True:
            try:
                run_retention()
            except Exception:  # DB down, migration 0004 missing, ...
                log.exception("retention run failed")
            if _stop.wait(settings.retention_interval_minutes * 60):
                return

    t = threading.Thread(target=loop, name="retention", daemon=True)
    t.start()
    return t


def stop_retention_job() -> None:
    _stop.set()

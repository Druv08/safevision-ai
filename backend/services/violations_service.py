"""Violation records and the audit log, stored in Supabase Postgres."""

import logging
import re
from datetime import datetime, timezone

from config import settings
from services import alerts, db, local_store, privacy, storage_service
from services.db import log_audit  # noqa: F401  (re-exported: routes import it from here)
from services.evidence import INTERNAL_COLUMNS, sha256
from services.pipeline import TYPE_LABELS
from supabase_client import get_supabase

log = logging.getLogger(__name__)

# DB type -> (label shown in the UI, severity)
TYPE_INFO = TYPE_LABELS
SOURCES = ("image", "video", "camera")
STATUSES = ("new", "acknowledged", "action_taken", "closed")
# Why it happened, recorded when the record is reviewed. "ppe_not_issued" points at
# the site, not the worker: the reason to keep it separate from "ppe_not_worn".
CAUSES = ("ppe_not_issued", "ppe_not_worn", "ppe_damaged", "false_detection", "other")


class LegalHoldError(RuntimeError):
    pass


def original_available(row: dict, now: datetime | None = None) -> bool:
    if not row.get("original_path"):
        return False
    expires = row.get("original_expires_at")
    return bool(row.get("legal_hold")) or not expires or datetime.fromisoformat(expires) > (
        now or datetime.now(timezone.utc))


def to_api(row: dict) -> dict:
    """DB row plus the legacy keys the frontend has always used. The original's storage key stays inside."""
    label, severity = TYPE_INFO.get(row["type"], (row["type"], "Medium"))
    return {
        **{k: v for k, v in row.items() if k not in INTERNAL_COLUMNS},
        "legal_hold": bool(row.get("legal_hold")),
        "has_original": original_available(row),
        "violation_id": row["id"],
        "timestamp": row["created_at"],
        "violation_type": label,
        "severity": severity,
    }


def create_violation(
    vtype: str,
    confidence: float,
    source: str,
    screenshot_path: str | None,
    model_version: str | None,
    created_at: datetime | None = None,
    note: str | None = None,
    track_id: int | None = None,
    episode_start_s: float | None = None,
    episode_end_s: float | None = None,
    **links,
) -> dict:
    """`links`: optional camera_id, zone_id, started_at, ended_at (stream episodes) and the evidence
    columns screenshot_sha256, original_path, original_sha256, original_expires_at."""
    if vtype not in TYPE_INFO:
        raise ValueError(f"unknown violation type {vtype!r}")
    if source not in SOURCES:
        raise ValueError(f"unknown source {source!r}")
    row = {
        "type": vtype,
        "confidence": round(float(confidence), 3),
        "source": source,
        "screenshot_path": screenshot_path,
        "model_version": model_version,
        "note": note,
        "track_id": track_id,
        "episode_start_s": None if episode_start_s is None else round(episode_start_s, 2),
        "episode_end_s": None if episode_end_s is None else round(episode_end_s, 2),
    }
    if created_at is not None:
        row["created_at"] = created_at.isoformat()
    for key in ("camera_id", "zone_id", "started_at", "ended_at", "screenshot_sha256", "original_path",
                "original_sha256", "original_expires_at"):
        value = links.pop(key, None)
        if value is not None:  # only send columns that are used (uploads work without migration 0003)
            row[key] = value.isoformat() if isinstance(value, datetime) else value
    if links:
        raise TypeError(f"unexpected fields {sorted(links)}")
    if settings.db_disabled:
        return local_store.insert(row)
    return get_supabase().table("violations").insert(row).execute().data[0]


def save_episode(episode, source: str, model_version: str, tracked: bool = True, camera_id: str | None = None,
                 started_at: datetime | None = None, ended_at: datetime | None = None) -> dict:
    """
    One pipeline Episode -> one violation row with its one screenshot, the
    screenshot's SHA-256 taken at capture, and (if the pipeline blurred it) the
    encrypted unblurred original. Then alerts go out (alerts.py), at most once.
    """
    key, evidence = None, {}
    if episode.snapshot:
        key = storage_service.upload_screenshot(episode.snapshot)
        evidence["screenshot_sha256"] = sha256(episode.snapshot)
    if episode.original:
        try:
            evidence.update(privacy.store_original(episode.original))
        except Exception:  # keep the blurred record; losing the original is the privacy-safe failure
            log.exception("could not store the unblurred original")
    try:
        row = create_violation(
            episode.type, episode.confidence, source, key, model_version,
            track_id=episode.track_id if tracked else None,
            episode_start_s=episode.start_s, episode_end_s=episode.end_s,
            camera_id=camera_id, zone_id=episode.zone_id, started_at=started_at, ended_at=ended_at, **evidence,
        )
    except Exception:
        for k in (key, evidence.get("original_path")):
            if k:
                storage_service.delete_object(k)  # don't leave orphaned evidence
        raise
    alerts.notify_async(row)
    return row


def set_episode_end(violation_id: str, end_s: float, ended_at: datetime | None = None) -> None:
    """A live episode was saved when its alert fired; record when it ended."""
    changes = {"episode_end_s": round(end_s, 2)}
    if ended_at is not None:
        changes["ended_at"] = ended_at.isoformat()
    if settings.db_disabled:
        local_store.update(violation_id, changes)
    else:
        get_supabase().table("violations").update(changes).eq("id", violation_id).execute()


def record_observations(observations, source: str, model_version: str, tracked: bool = True,
                        camera_id: str | None = None) -> None:
    """Store compliant and violating observations alike (the compliance-rate denominator)."""
    extra = {"camera_id": camera_id} if camera_id else {}
    rows = [
        {
            "source": source,
            "track_id": o.track_id if tracked else None,
            "item": o.item,
            "outcome": o.outcome,
            "frames_worn": o.frames_worn,
            "frames_missing": o.frames_missing,
            "frames_unknown": o.frames_unknown,
            "first_s": round(o.first_s, 2),
            "last_s": round(o.last_s, 2),
            "model_version": model_version,
            **extra,
        }
        for o in observations
    ]
    if not rows:
        return
    if settings.db_disabled:
        local_store.insert_observations(rows)
    else:
        get_supabase().table("observations").insert(rows).execute()


def compliance_stats() -> dict:
    """Per item: compliant / violation / unknown counts and rate = compliant / (compliant + violation)."""
    out = {}
    for item in ("helmet", "vest"):
        n = {}
        for outcome in ("compliant", "violation", "unknown"):
            if settings.db_disabled:
                n[outcome] = local_store.count_observations(item, outcome)
            else:
                res = (
                    get_supabase().table("observations").select("id", count="exact")
                    .eq("item", item).eq("outcome", outcome).limit(1).execute()
                )
                n[outcome] = res.count or 0
        decided = n["compliant"] + n["violation"]
        out[item] = {**n, "rate": round(n["compliant"] / decided, 4) if decided else None}
    return out


def _search_term(q: str) -> str:
    # Strip PostgREST filter syntax characters so user input can't add filters.
    return re.sub(r"[,()*%\\:\"']", " ", q).strip()


def list_violations(
    vtype: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    q: str | None = None,
    page: int = 1,
    page_size: int = 50,
    status: str | None = None,
    source: str | None = None,
    oldest: bool = False,
    camera_id: str | None = None,
    zone_id: str | None = None,
) -> tuple[list[dict], int]:
    """Newest first (oldest first with oldest=True). date_to is exclusive. Returns (rows, total matching)."""
    if settings.db_disabled:
        return local_store.query(
            vtype, date_from, date_to, _search_term(q or ""), page, page_size, status, source, oldest, camera_id,
            zone_id,
        )
    query = get_supabase().table("violations").select("*", count="exact")
    for col, val in (("type", vtype), ("status", status), ("source", source), ("camera_id", camera_id),
                     ("zone_id", zone_id)):
        if val:
            query = query.eq(col, val)
    if date_from:
        query = query.gte("created_at", date_from.isoformat())
    if date_to:
        query = query.lt("created_at", date_to.isoformat())
    term = _search_term(q or "")
    if term:
        query = query.or_(
            ",".join(f"{col}.ilike.*{term}*" for col in ("type", "status", "note", "model_version"))
        )
    start = (page - 1) * page_size
    res = query.order("created_at", desc=not oldest).range(start, start + page_size - 1).execute()
    return res.data, res.count or 0


def all_violations(batch: int = 1000) -> list[dict]:
    """Every row, oldest first (for export)."""
    if settings.db_disabled:
        return local_store.all_rows()
    rows, start = [], 0
    while True:
        res = (
            get_supabase().table("violations").select("*")
            .order("created_at").range(start, start + batch - 1).execute()
        )
        rows += res.data
        if len(res.data) < batch:
            return rows
        start += batch


def count_by_type() -> dict[str, int]:
    if settings.db_disabled:
        return {vtype: local_store.count(vtype) for vtype in TYPE_INFO}
    counts = {}
    for vtype in TYPE_INFO:
        res = (
            get_supabase().table("violations")
            .select("id", count="exact").eq("type", vtype).limit(1).execute()
        )
        counts[vtype] = res.count or 0
    return counts


def get_violation(violation_id: str) -> dict | None:
    if settings.db_disabled:
        return local_store.get(violation_id)
    res = get_supabase().table("violations").select("*").eq("id", violation_id).limit(1).execute()
    return res.data[0] if res.data else None


def set_status(violation_id: str, status: str, user_id: str, note: str | None = None,
               cause: str | None = None) -> dict | None:
    if status not in STATUSES[1:]:
        raise ValueError(f"cannot set status {status!r}")
    if status == "action_taken" and not (note or "").strip():
        raise ValueError("Describe the action taken in the note.")
    if cause is not None and cause not in CAUSES:
        raise ValueError(f"unknown cause {cause!r}")
    changes = {"status": status, f"{status}_by": user_id}
    if note is not None:
        changes["note"] = note
    if cause is not None:
        changes["cause"] = cause
    if settings.db_disabled:
        return local_store.update(violation_id, changes)
    res = get_supabase().table("violations").update(changes).eq("id", violation_id).execute()
    return res.data[0] if res.data else None


def delete_violation(violation_id: str) -> dict | None:
    """Delete the row, its screenshot and original. Returns the deleted row. Refused on legal hold."""
    row = get_violation(violation_id)
    if row is None:
        return None
    if row.get("legal_hold"):
        raise LegalHoldError("This record is on legal hold and cannot be deleted.")
    if settings.db_disabled:
        local_store.delete(violation_id)
    else:
        get_supabase().table("violations").delete().eq("id", violation_id).execute()
    for key in (row.get("screenshot_path"), row.get("original_path")):
        if key:
            try:
                storage_service.delete_object(key)
            except Exception:
                log.exception("Row %s deleted but object %s was not", violation_id, key)
    return row


def set_legal_hold(violation_id: str, hold: bool, reason: str | None = None) -> dict | None:
    """On hold, retention deletes neither the screenshot nor the original, and the record cannot be deleted."""
    return db.update("violations", violation_id, {"legal_hold": hold, "legal_hold_reason": reason if hold else None})

"""Violation records and the audit log, stored in Supabase Postgres."""

import logging
import re
from datetime import datetime

import cv2

from config import settings
from services import local_store, storage_service
from supabase_client import get_supabase

log = logging.getLogger(__name__)

# DB type -> (label shown in the UI, severity)
TYPE_INFO = {
    "no_helmet": ("Helmet Missing", "High"),
    "no_vest": ("Safety Vest Missing", "Medium"),
}
SOURCES = ("image", "video", "camera")
STATUSES = ("new", "acknowledged", "closed")


def to_api(row: dict) -> dict:
    """DB row plus the legacy keys the frontend has always used."""
    label, severity = TYPE_INFO.get(row["type"], (row["type"], "Medium"))
    return {
        **row,
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
) -> dict:
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
    }
    if created_at is not None:
        row["created_at"] = created_at.isoformat()
    if settings.db_disabled:
        return local_store.insert(row)
    return get_supabase().table("violations").insert(row).execute().data[0]


def save_violation(frame, vtype: str, confidence: float, source: str, model_version: str) -> dict:
    """Upload the frame as evidence and insert the violation row."""
    ok, buf = cv2.imencode(".jpg", frame)
    if not ok:
        raise ValueError("could not encode screenshot")
    key = storage_service.upload_screenshot(buf.tobytes())
    try:
        return create_violation(vtype, confidence, source, key, model_version)
    except Exception:
        storage_service.delete_object(key)  # don't leave orphaned evidence
        raise


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
) -> tuple[list[dict], int]:
    """Newest first (oldest first with oldest=True). date_to is exclusive. Returns (rows, total matching)."""
    if settings.db_disabled:
        return local_store.query(
            vtype, date_from, date_to, _search_term(q or ""), page, page_size, status, source, oldest
        )
    query = get_supabase().table("violations").select("*", count="exact")
    for col, val in (("type", vtype), ("status", status), ("source", source)):
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


def set_status(violation_id: str, status: str, user_id: str, note: str | None = None) -> dict | None:
    if status not in ("acknowledged", "closed"):
        raise ValueError(f"cannot set status {status!r}")
    changes = {"status": status, f"{status}_by": user_id}
    if note is not None:
        changes["note"] = note
    if settings.db_disabled:
        return local_store.update(violation_id, changes)
    res = get_supabase().table("violations").update(changes).eq("id", violation_id).execute()
    return res.data[0] if res.data else None


def delete_violation(violation_id: str) -> dict | None:
    """Delete the row and its screenshot. Returns the deleted row."""
    row = get_violation(violation_id)
    if row is None:
        return None
    if settings.db_disabled:
        local_store.delete(violation_id)
    else:
        get_supabase().table("violations").delete().eq("id", violation_id).execute()
    if row.get("screenshot_path"):
        try:
            storage_service.delete_object(row["screenshot_path"])
        except Exception:
            log.exception("Row %s deleted but screenshot %s was not", violation_id, row["screenshot_path"])
    return row


def log_audit(user_id: str | None, action: str, target_id: str | None = None, detail: dict | None = None) -> None:
    if settings.db_disabled:  # ponytail: no audit log in local dev mode
        return
    get_supabase().table("audit_log").insert(
        {"user_id": user_id, "action": action, "target_id": target_id, "detail": detail}
    ).execute()

"""Evidence access. Every screenshot view, original view, export, legal-hold change and delete is audited."""

import csv
import io
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from auth import User, require_admin, require_viewer
from config import settings
from services import evidence, privacy, storage_service
from services.violations_service import (
    LegalHoldError,
    all_violations,
    delete_violation,
    get_violation,
    log_audit,
    set_legal_hold,
    to_api,
)

router = APIRouter()

EXPORT_COLUMNS = [
    "id", "created_at", "type", "confidence", "source", "status", "cause",
    "model_version", "acknowledged_by", "action_taken_by", "closed_by", "note", "screenshot_path",
    "screenshot_sha256", "legal_hold", "track_id", "episode_start_s", "episode_end_s",
    "camera_id", "zone_id", "started_at", "ended_at",
]
NO_STORE = {"Cache-Control": "no-store"}


def _row_or_404(violation_id: UUID) -> dict:
    row = get_violation(str(violation_id))
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Violation not found")
    return row


@router.get("/violations/{violation_id}/evidence")
def get_evidence(violation_id: UUID, user: User = Depends(require_viewer)):
    row = get_violation(str(violation_id))
    if row is None or not row.get("screenshot_path"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No screenshot for this violation")
    url = storage_service.create_signed_url(row["screenshot_path"])
    log_audit(user.id, "view_evidence", str(violation_id))
    return {"url": url, "expires_in": settings.signed_url_ttl_seconds}


@router.get("/violations/{violation_id}/verify")
def verify_evidence(violation_id: UUID, user: User = Depends(require_viewer)):
    """Re-hash the stored screenshot and compare with the hash recorded at capture."""
    return evidence.verify(_row_or_404(violation_id))


@router.get("/violations/{violation_id}/original")
def view_original(violation_id: UUID, user: User = Depends(require_admin)):
    """The unblurred original (admin only, while it is kept). Logged before it is returned: no log, no image."""
    row = _row_or_404(violation_id)
    try:
        jpeg = privacy.read_original(row)
    except privacy.OriginalUnavailable as e:
        raise HTTPException(status.HTTP_410_GONE, str(e)) from None
    log_audit(user.id, "view_original", str(violation_id))
    return Response(jpeg, media_type="image/jpeg", headers=NO_STORE)


@router.get("/violations/{violation_id}/export")
def export_evidence(violation_id: UUID, user: User = Depends(require_admin)):
    """Zip: screenshot, metadata with hashes, audit trail (including this export), SHA256SUMS."""
    row = _row_or_404(violation_id)
    log_audit(user.id, "export_evidence", str(violation_id))
    data = evidence.export_package(row, {"id": user.id, "email": user.email})
    name = f"evidence-{violation_id}.zip"
    return Response(data, media_type="application/zip",
                    headers={**NO_STORE, "Content-Disposition": f'attachment; filename="{name}"'})


class LegalHold(BaseModel):
    hold: bool
    reason: str | None = Field(None, max_length=500)


@router.put("/violations/{violation_id}/legal-hold")
def legal_hold(violation_id: UUID, body: LegalHold, user: User = Depends(require_admin)):
    _row_or_404(violation_id)
    if body.hold and not (body.reason or "").strip():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Give a reason for the legal hold.")
    row = set_legal_hold(str(violation_id), body.hold, body.reason)
    log_audit(user.id, "legal_hold_on" if body.hold else "legal_hold_off", str(violation_id),
              {"reason": body.reason} if body.hold else None)
    return to_api(row)


@router.get("/download-violations")
def download_violations(user: User = Depends(require_viewer)):
    rows = all_violations()
    if not rows:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There are no violations to export.")

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=EXPORT_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)

    log_audit(user.id, "export", detail={"rows": len(rows)})
    return Response(
        buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="violations.csv"'},
    )


@router.delete("/violations/{violation_id}")
def remove_violation(violation_id: UUID, user: User = Depends(require_admin)):
    try:
        row = delete_violation(str(violation_id))
    except LegalHoldError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from None
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Violation not found")
    log_audit(
        user.id,
        "delete",
        str(violation_id),
        {"type": row["type"], "created_at": row["created_at"], "screenshot_path": row.get("screenshot_path"),
         "screenshot_sha256": row.get("screenshot_sha256")},
    )
    return {"deleted": str(violation_id)}

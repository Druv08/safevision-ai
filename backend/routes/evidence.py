"""Evidence access: every screenshot view, export and delete is written to audit_log."""

import csv
import io
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

from auth import User, require_admin, require_viewer
from config import settings
from services import storage_service
from services.violations_service import all_violations, delete_violation, get_violation, log_audit

router = APIRouter()

EXPORT_COLUMNS = [
    "id", "created_at", "type", "confidence", "source", "status",
    "model_version", "acknowledged_by", "closed_by", "note", "screenshot_path",
]


@router.get("/violations/{violation_id}/evidence")
def get_evidence(violation_id: UUID, user: User = Depends(require_viewer)):
    row = get_violation(str(violation_id))
    if row is None or not row.get("screenshot_path"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No screenshot for this violation")
    url = storage_service.create_signed_url(row["screenshot_path"])
    log_audit(user.id, "view_evidence", str(violation_id))
    return {"url": url, "expires_in": settings.signed_url_ttl_seconds}


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
    row = delete_violation(str(violation_id))
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Violation not found")
    log_audit(
        user.id,
        "delete",
        str(violation_id),
        {"type": row["type"], "created_at": row["created_at"], "screenshot_path": row.get("screenshot_path")},
    )
    return {"deleted": str(violation_id)}

"""Alert recipients and delivery log (admin only). Recipient changes and test sends are audited."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from auth import User, require_admin
from services import alerts
from services.violations_service import log_audit

router = APIRouter(prefix="/alerts", tags=["alerts"])

Channel = Literal["whatsapp", "webhook"]
Language = Literal["en", "hi"]


class RecipientIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    channel: Channel
    address: str = Field(min_length=1, max_length=500, description="+E.164 number or https URL")
    language: Language = "en"
    enabled: bool = True


class RecipientPatch(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    channel: Channel | None = None
    address: str | None = Field(None, min_length=1, max_length=500)
    language: Language | None = None
    enabled: bool | None = None


def _or_422(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from None


@router.get("/recipients")
def get_recipients(user: User = Depends(require_admin)):
    return {"recipients": alerts.list_recipients(), "whatsapp_provider": alerts.whatsapp_provider().name}


@router.post("/recipients", status_code=status.HTTP_201_CREATED)
def add_recipient(body: RecipientIn, user: User = Depends(require_admin)):
    row = _or_422(alerts.create_recipient, **body.model_dump())
    log_audit(user.id, "alert_recipient_create", row["id"], {"channel": row["channel"], "language": row["language"]})
    return row


@router.patch("/recipients/{recipient_id}")
def edit_recipient(recipient_id: UUID, body: RecipientPatch, user: User = Depends(require_admin)):
    changes = body.model_dump(exclude_unset=True)
    row = _or_422(alerts.update_recipient, str(recipient_id), **changes)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Recipient not found")
    log_audit(user.id, "alert_recipient_update", str(recipient_id), {"fields": sorted(changes)})
    return row


@router.delete("/recipients/{recipient_id}")
def remove_recipient(recipient_id: UUID, user: User = Depends(require_admin)):
    alerts.delete_recipient(str(recipient_id))
    log_audit(user.id, "alert_recipient_delete", str(recipient_id))
    return {"deleted": str(recipient_id)}


@router.post("/recipients/{recipient_id}/test")
def test_recipient(recipient_id: UUID, user: User = Depends(require_admin)):
    """Send a sample alert now. "logged" means no WhatsApp credentials are configured."""
    rows = [r for r in alerts.list_recipients() if r["id"] == str(recipient_id)]
    if not rows:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Recipient not found")
    result, error = alerts.send_test(rows[0])
    log_audit(user.id, "alert_test", str(recipient_id), {"status": result})
    return {"status": result, "error": error}


@router.get("")
def get_alerts(limit: int = 50, user: User = Depends(require_admin)):
    return {"alerts": alerts.recent_alerts(min(max(limit, 1), 200))}

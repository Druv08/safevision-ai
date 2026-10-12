"""Aggregate views: the dashboard summary and the weekly report (no images, no individual records)."""

from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response

from auth import User, require_viewer
from services import reports
from services.violations_service import log_audit

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/summary")
def get_summary(
    date_from: datetime | None = None,
    date_to: datetime | None = Query(None, description="Exclusive upper bound"),
    bucket: Literal["day", "hour"] = "day",
    user: User = Depends(require_viewer),
):
    return reports.summary(date_from, date_to, bucket)


@router.get("/weekly")
def get_weekly(week_start: date | None = Query(None, description="Monday; default: the last complete week"),
               user: User = Depends(require_viewer)):
    start = week_start or reports.last_week_start()
    body, name = reports.weekly_report(start)
    log_audit(user.id, "weekly_report", detail={"week_start": start.isoformat()})
    return Response(body, media_type="text/html; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})

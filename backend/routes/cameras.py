"""
Network cameras and their zones.

Viewers can list cameras, see their status, a snapshot and the zones. Only
admins can add, edit, delete, start and stop cameras or change zones; every
such change is written to audit_log. Credentials are write-only: requests may
send them, responses never contain them (cameras_service.to_api).
"""

from typing import Literal
from uuid import UUID

import cv2
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from auth import User, require_admin, require_viewer
from services import cameras_service as cams
from services.stream_service import grab_frame, manager
from services.violations_service import log_audit

router = APIRouter(prefix="/cameras", tags=["cameras"])

Policy = Literal["both", "helmet", "vest", "none", "no_entry"]
DefaultPolicy = Literal["both", "helmet", "vest", "none"]


class CameraIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    url: str = Field(min_length=1, max_length=2000, description="rtsp://host:port/path (credentials may be included)")
    username: str | None = Field(None, max_length=200)
    password: str | None = Field(None, max_length=200)
    sample_fps: float | None = Field(None, gt=0, le=30)
    default_policy: DefaultPolicy = "both"
    enabled: bool = False


class CameraPatch(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    url: str | None = Field(None, min_length=1, max_length=2000)
    username: str | None = Field(None, max_length=200)
    password: str | None = Field(None, max_length=200)
    clear_credentials: bool = False
    sample_fps: float | None = Field(None, gt=0, le=30)
    default_policy: DefaultPolicy | None = None


class ZoneIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    policy: Policy
    polygon: list[list[float]] = Field(min_length=3, max_length=64)


class ZonesIn(BaseModel):
    zones: list[ZoneIn] = Field(max_length=50)


def _camera_or_404(camera_id: UUID) -> dict:
    camera = cams.get_camera(str(camera_id))
    if camera is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Camera not found")
    return camera


def _out(camera: dict) -> dict:
    return cams.to_api(camera, manager.status(camera["id"]))


def _guard(fn, *args, **kwargs):
    """Validation problems -> 422, missing/wrong CAMERA_SECRET_KEY -> 503, with the reason."""
    try:
        return fn(*args, **kwargs)
    except cams.CredentialsError as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(e)) from None
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from None


def _start(camera: dict) -> None:
    _guard(manager.start, camera, cams.list_zones(camera["id"]))


@router.get("")
def list_cameras(user: User = Depends(require_viewer)):
    return [_out(c) for c in cams.list_cameras()]


@router.get("/{camera_id}")
def get_camera(camera_id: UUID, user: User = Depends(require_viewer)):
    return _out(_camera_or_404(camera_id))


@router.post("", status_code=status.HTTP_201_CREATED)
def create_camera(body: CameraIn, user: User = Depends(require_admin)):
    camera = _guard(cams.create_camera, **body.model_dump())
    log_audit(user.id, "camera_create", camera["id"], {"name": camera["name"], "url": camera["url"]})
    if camera["enabled"]:
        _start(camera)
    return _out(camera)


@router.patch("/{camera_id}")
def update_camera(camera_id: UUID, body: CameraPatch, user: User = Depends(require_admin)):
    _camera_or_404(camera_id)
    camera = _guard(cams.update_camera, str(camera_id), **body.model_dump())
    changed = sorted(k for k, v in body.model_dump(exclude_unset=True).items() if k != "password")
    log_audit(user.id, "camera_update", camera["id"], {"fields": changed + (["password"] if body.password else [])})
    if manager.running(camera["id"]):
        _start(camera)  # restart with the new URL, credentials, rate or default policy
    return _out(camera)


@router.delete("/{camera_id}")
def delete_camera(camera_id: UUID, user: User = Depends(require_admin)):
    camera = _camera_or_404(camera_id)
    manager.stop(camera["id"])
    cams.delete_camera(camera["id"])
    log_audit(user.id, "camera_delete", camera["id"], {"name": camera["name"]})
    return {"deleted": camera["id"]}


@router.post("/{camera_id}/start")
def start_camera(camera_id: UUID, user: User = Depends(require_admin)):
    _camera_or_404(camera_id)
    camera = cams.update_camera(str(camera_id), enabled=True)  # also restarted after a backend restart
    _start(camera)
    log_audit(user.id, "camera_start", camera["id"])
    return _out(camera)


@router.post("/{camera_id}/stop")
def stop_camera(camera_id: UUID, user: User = Depends(require_admin)):
    _camera_or_404(camera_id)
    manager.stop(str(camera_id))
    camera = cams.update_camera(str(camera_id), enabled=False)
    log_audit(user.id, "camera_stop", camera["id"])
    return _out(camera)


@router.get("/{camera_id}/snapshot")
def snapshot(camera_id: UUID, user: User = Depends(require_viewer)):
    """Latest analysed frame (camera running), else one frame fetched now. Plain frame: no overlays."""
    camera = _camera_or_404(camera_id)
    frame = manager.snapshot(camera["id"])
    if frame is None:
        frame = _guard(grab_frame, camera)
    if frame is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Could not get a frame from the camera")
    ok, buf = cv2.imencode(".jpg", frame)
    if not ok:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Could not encode the frame")
    return Response(buf.tobytes(), media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@router.get("/{camera_id}/zones")
def get_zones(camera_id: UUID, user: User = Depends(require_viewer)):
    _camera_or_404(camera_id)
    return [cams.zone_to_api(z) for z in cams.list_zones(str(camera_id))]


@router.put("/{camera_id}/zones")
def put_zones(camera_id: UUID, body: ZonesIn, user: User = Depends(require_admin)):
    """Replace all zones of a camera. Applies to a running camera from its next frame."""
    camera = _camera_or_404(camera_id)
    rows = _guard(cams.replace_zones, camera["id"], [z.model_dump() for z in body.zones])
    manager.set_zones(camera["id"], rows, camera["default_policy"])
    summary = [{"name": r["name"], "policy": r["policy"]} for r in rows]
    log_audit(user.id, "zones_update", camera["id"], {"zones": summary})
    return [cams.zone_to_api(z) for z in rows]

"""
Evidence integrity.

At capture (violations_service.save_episode) the SHA-256 of the stored
screenshot is saved on the violation row together with the model version.
verify() downloads the stored object again and compares. export_package()
builds one zip per record: the screenshot, its metadata (with both hashes and
the check result), the audit trail for that record and a SHA256SUMS file.

The hash proves the file has not changed since capture; it does not prove the
capture itself was right. audit_log is append-only (migration 0004 and the
SQLite triggers), so the trail in an export cannot have been edited through
the application or its service-role key.
"""

import hashlib
import io
import json
import zipfile
from datetime import datetime, timezone

from services import db, storage_service

INTERNAL_COLUMNS = {"original_path"}  # storage key of the encrypted original: never exported


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _check(row: dict) -> tuple[dict, bytes | None]:
    expected = row.get("screenshot_sha256")
    if not row.get("screenshot_path"):
        status = "deleted_by_retention" if row.get("screenshot_deleted_at") else "no_screenshot"
        return {"status": status, "expected": expected, "actual": None}, None
    try:
        data = storage_service.download(row["screenshot_path"])
    except Exception:
        return {"status": "missing", "expected": expected, "actual": None}, None
    actual = sha256(data)
    status = "no_hash_recorded" if not expected else "ok" if actual == expected else "mismatch"
    return {"status": status, "expected": expected, "actual": actual}, data


def verify(row: dict) -> dict:
    """{"status": ok | mismatch | missing | no_hash_recorded | no_screenshot | deleted_by_retention, ...}"""
    return _check(row)[0]


README = """SafeVision AI evidence package
==============================

screenshot.jpg    the evidence frame as stored (people blurred for privacy)
metadata.json     the violation record, the model version, and the screenshot's
                  SHA-256 recorded at capture next to the one computed at export
audit_trail.json  every audit-log entry about this record, oldest first
                  (views, status changes, legal hold, retention, this export)
SHA256SUMS        hashes of the files in this package

Check that the screenshot is the one captured: its SHA-256 must equal
metadata.json -> screenshot.sha256_at_capture.

    Linux / macOS:  sha256sum -c SHA256SUMS
    Windows:        Get-FileHash screenshot.jpg -Algorithm SHA256

A matching hash shows the image has not changed since capture. It does not
show that the detection was right: PPE presence detection makes mistakes, and
a person should review every record.
"""


def _name(table: str, row_id: str | None) -> str | None:
    if not row_id:
        return None
    rows = db.select(table, id=row_id)
    return rows[0]["name"] if rows else None


def export_package(row: dict, exported_by: dict) -> bytes:
    check, image = _check(row)
    meta = {
        "record": {k: v for k, v in row.items() if k not in INTERNAL_COLUMNS},
        "camera": _name("cameras", row.get("camera_id")),
        "zone": _name("zones", row.get("zone_id")),
        "screenshot": {
            "file": "screenshot.jpg" if image else None,
            "sha256_at_capture": check["expected"],
            "sha256_at_export": check["actual"],
            "integrity": check["status"],
        },
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "exported_by": exported_by,
    }
    files = {
        "metadata.json": json.dumps(meta, indent=2, default=str, ensure_ascii=False).encode(),
        "audit_trail.json": json.dumps(db.audit_trail(row["id"]), indent=2, default=str, ensure_ascii=False).encode(),
    }
    if image:
        files["screenshot.jpg"] = image
    sums = "".join(f"{sha256(data)}  {name}\n" for name, data in sorted(files.items()))

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            z.writestr(name, data)
        z.writestr("SHA256SUMS", sums)
        z.writestr("README.txt", README)
    return buf.getvalue()

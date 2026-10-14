"""
Cameras and their zones.

A camera URL is stored without credentials. If the admin supplies a username
and password (separately, or inside the URL as rtsp://user:pass@host/...), they
are encrypted with Fernet using CAMERA_SECRET_KEY and stored only in
`credentials_enc`. They are decrypted only to open the stream, and `to_api()`
whitelists the fields that leave the server, so they are never returned.
"""

import json
import re
from datetime import datetime, timezone
from urllib.parse import quote, unquote, urlsplit, urlunsplit

from cryptography.fernet import Fernet, InvalidToken

from config import settings
from services import db
from services.zones import DEFAULT_POLICIES, POLICIES, validate_polygon


class CredentialsError(RuntimeError):
    """CAMERA_SECRET_KEY missing or wrong; credentials cannot be stored or read."""


# ---------------------------------------------------------------------------
# Credentials
# ---------------------------------------------------------------------------
def _fernet() -> Fernet:
    if not settings.camera_secret_key:
        raise CredentialsError(
            "CAMERA_SECRET_KEY is not set, so camera credentials cannot be stored or used. Generate one with: "
            'python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
        )
    try:
        return Fernet(settings.camera_secret_key.encode())
    except ValueError:
        raise CredentialsError("CAMERA_SECRET_KEY is not a valid Fernet key (32 url-safe base64 bytes)") from None


def encrypt_credentials(username: str, password: str) -> str:
    return _fernet().encrypt(json.dumps({"u": username, "p": password}).encode()).decode()


def decrypt_credentials(token: str) -> tuple[str, str]:
    try:
        data = json.loads(_fernet().decrypt(token.encode()))
    except InvalidToken:
        raise CredentialsError(
            "stored camera credentials cannot be decrypted with the current CAMERA_SECRET_KEY"
        ) from None
    return data["u"], data["p"]


def split_url(url: str) -> tuple[str, str | None, str | None]:
    """(url without credentials, username, password). Validates the scheme and host."""
    url = url.strip()
    parts = urlsplit(url)
    if parts.scheme.lower() not in settings.stream_allowed_schemes:
        raise ValueError(f"URL scheme must be one of: {', '.join(settings.stream_allowed_schemes)}")
    if not parts.hostname:
        raise ValueError("URL needs a host")
    if any(c in url for c in "\r\n\t "):
        raise ValueError("URL must not contain whitespace")
    netloc = parts.hostname if ":" not in parts.hostname else f"[{parts.hostname}]"
    if parts.port:
        netloc += f":{parts.port}"
    clean = urlunsplit((parts.scheme.lower(), netloc, parts.path, parts.query, ""))
    user = unquote(parts.username) if parts.username else None
    password = unquote(parts.password) if parts.password else None
    return clean, user, password


def stream_url(camera: dict) -> str:
    """The URL to open, with decrypted credentials inserted. Never log or return this."""
    if not camera.get("credentials_enc"):
        return camera["url"]
    user, password = decrypt_credentials(camera["credentials_enc"])
    parts = urlsplit(camera["url"])
    userinfo = quote(user, safe="") + (":" + quote(password, safe="") if password else "")
    return urlunsplit((parts.scheme, f"{userinfo}@{parts.netloc}", parts.path, parts.query, ""))


def redact(text: str) -> str:
    """Remove anything that looks like URL credentials from an error message."""
    return re.sub(r"(\w+://)[^/@\s]*@", r"\1***@", text)


# ---------------------------------------------------------------------------
# Storage (Supabase, or SQLite in DB_DISABLED dev mode)
# ---------------------------------------------------------------------------
_select, _insert, _update, _delete = db.select, db.insert, db.update, db.delete


def list_cameras() -> list[dict]:
    return _select("cameras")


def get_camera(camera_id: str) -> dict | None:
    rows = _select("cameras", id=camera_id)
    return rows[0] if rows else None


def _check(sample_fps, default_policy):
    if sample_fps is not None and not 0 < sample_fps <= 30:
        raise ValueError("sample_fps must be between 0 and 30")
    if default_policy is not None and default_policy not in DEFAULT_POLICIES:
        raise ValueError(f"default_policy must be one of {DEFAULT_POLICIES}")


def create_camera(name: str, url: str, username: str | None = None, password: str | None = None,
                  sample_fps: float | None = None, default_policy: str = "both", enabled: bool = False) -> dict:
    _check(sample_fps, default_policy)
    clean, url_user, url_password = split_url(url)
    username, password = username or url_user, password or url_password
    now = datetime.now(timezone.utc).isoformat()
    row = {
        "name": name.strip(),
        "url": clean,
        "credentials_enc": encrypt_credentials(username, password or "") if username else None,
        "sample_fps": sample_fps or settings.stream_default_fps,
        "default_policy": default_policy,
        "enabled": enabled,
        "updated_at": now,
    }
    return _insert("cameras", row)[0]


def update_camera(camera_id: str, *, name=None, url=None, username=None, password=None,
                  clear_credentials=False, sample_fps=None, default_policy=None, enabled=None) -> dict | None:
    """Change only what is given. Credentials are kept unless new ones are given or cleared."""
    current = get_camera(camera_id)
    if current is None:
        return None
    _check(sample_fps, default_policy)
    changes = {"updated_at": datetime.now(timezone.utc).isoformat()}
    if name is not None:
        changes["name"] = name.strip()
    if url is not None:
        clean, url_user, url_password = split_url(url)
        changes["url"] = clean
        username, password = username or url_user, password or url_password
    if clear_credentials:
        changes["credentials_enc"] = None
    elif username is not None or password is not None:
        # Only read the stored pair when one half is kept, so new credentials can
        # always replace ones that no longer decrypt (e.g. after a key change).
        old_user = old_password = None
        if (username is None or password is None) and current.get("credentials_enc"):
            old_user, old_password = decrypt_credentials(current["credentials_enc"])
        user = username if username is not None else old_user
        if not user:
            raise ValueError("a password needs a username")
        changes["credentials_enc"] = encrypt_credentials(user, password if password is not None else old_password or "")
    for key, value in (("sample_fps", sample_fps), ("default_policy", default_policy), ("enabled", enabled)):
        if value is not None:
            changes[key] = value
    return _update("cameras", camera_id, changes)


def delete_camera(camera_id: str) -> None:
    _delete("zones", camera_id=camera_id)  # the DB cascades too; this covers SQLite
    _delete("cameras", id=camera_id)


def list_zones(camera_id: str) -> list[dict]:
    return _select("zones", camera_id=camera_id)


def replace_zones(camera_id: str, zones: list[dict]) -> list[dict]:
    """Validate, then replace all zones of a camera (the zone editor saves the whole set)."""
    rows = []
    for z in zones:
        name = str(z.get("name", "")).strip()
        if not 1 <= len(name) <= 100:
            raise ValueError("each zone needs a name of 1 to 100 characters")
        if z.get("policy") not in POLICIES:
            raise ValueError(f"zone policy must be one of {POLICIES}")
        polygon = [list(p) for p in validate_polygon(z.get("polygon"))]
        rows.append({"camera_id": camera_id, "name": name, "policy": z["policy"], "polygon": polygon})
    # ponytail: delete + insert is two requests, not one transaction; move to a Postgres
    # function (rpc) if two admins editing the same camera at once becomes real.
    _delete("zones", camera_id=camera_id)
    return _insert("zones", rows) if rows else []


def to_api(camera: dict, status: dict | None = None) -> dict:
    """Only these fields ever leave the server: no credentials, encrypted or not."""
    return {
        "id": camera["id"],
        "name": camera["name"],
        "url": camera["url"],
        "has_credentials": bool(camera.get("credentials_enc")),
        "sample_fps": camera["sample_fps"],
        "default_policy": camera["default_policy"],
        "enabled": bool(camera["enabled"]),
        "created_at": camera["created_at"],
        "updated_at": camera.get("updated_at"),
        "status": status,
    }


def zone_to_api(zone: dict) -> dict:
    return {k: zone[k] for k in ("id", "camera_id", "name", "policy", "polygon", "created_at")}

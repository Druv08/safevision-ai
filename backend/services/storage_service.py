"""Screenshot storage in the private Supabase bucket."""

import uuid
from datetime import datetime, timezone

from config import settings
from services import local_store
from supabase_client import get_supabase


def _bucket():
    return get_supabase().storage.from_(settings.supabase_bucket)


def upload_screenshot(data: bytes, *, prefix: str = "", ext: str = "jpg", content_type: str = "image/jpeg") -> str:
    """Upload one object and return its server-generated key (a JPEG unless told otherwise)."""
    key = f"{prefix}{datetime.now(timezone.utc):%Y/%m/%d}/{uuid.uuid4().hex}.{ext}"
    if settings.db_disabled:
        local_store.save_screenshot(key, data)
    else:
        _bucket().upload(key, data, {"content-type": content_type})
    return key


def download(key: str) -> bytes:
    if settings.db_disabled:
        return local_store.read_screenshot(key)
    return _bucket().download(key)


def create_signed_url(key: str) -> str:
    """Short-lived URL for one object (SIGNED_URL_TTL_SECONDS)."""
    if settings.db_disabled:
        return local_store.screenshot_data_url(key)
    return _bucket().create_signed_url(key, settings.signed_url_ttl_seconds)["signedURL"]


def delete_object(key: str) -> None:
    if settings.db_disabled:
        return local_store.delete_screenshot(key)
    _bucket().remove([key])

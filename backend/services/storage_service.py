"""Screenshot storage in the private Supabase bucket."""

import uuid
from datetime import datetime, timezone

from config import settings
from services import local_store
from supabase_client import get_supabase


def _bucket():
    return get_supabase().storage.from_(settings.supabase_bucket)


def upload_screenshot(jpeg_bytes: bytes) -> str:
    """Upload a JPEG and return its server-generated object key."""
    key = f"{datetime.now(timezone.utc):%Y/%m/%d}/{uuid.uuid4().hex}.jpg"
    if settings.db_disabled:
        local_store.save_screenshot(key, jpeg_bytes)
    else:
        _bucket().upload(key, jpeg_bytes, {"content-type": "image/jpeg"})
    return key


def create_signed_url(key: str) -> str:
    """Short-lived URL for one object (SIGNED_URL_TTL_SECONDS)."""
    if settings.db_disabled:
        return local_store.screenshot_data_url(key)
    return _bucket().create_signed_url(key, settings.signed_url_ttl_seconds)["signedURL"]


def delete_object(key: str) -> None:
    if settings.db_disabled:
        return local_store.delete_screenshot(key)
    _bucket().remove([key])

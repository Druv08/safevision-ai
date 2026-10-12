import dataclasses
import os
import sys
import tempfile
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

# Must be set before `config` is imported. No real Supabase project or weights.
_MISSING = str(BACKEND_DIR / "tests" / "no-such-weights.pt")
os.environ.update(
    ENV="test",
    AUTH_DISABLED="false",
    DB_DISABLED="false",
    SUPABASE_URL="http://supabase.invalid",
    SUPABASE_SERVICE_ROLE_KEY="test-service-role-key",
    PPE_MODEL_PATH=_MISSING,
    HELMET_MODEL_PATH=_MISSING,
    PERSON_MODEL_PATH=_MISSING,
    MAX_UPLOAD_MB="1",
    RATE_LIMIT_PER_MINUTE="1000",
    UPLOAD_DIR=tempfile.mkdtemp(prefix="sv-uploads-"),
    CAMERA_SECRET_KEY="dGVzdC1vbmx5LWtleS1kby1ub3QtdXNlLWFueXdoZXI=",  # test-only Fernet key
    STREAM_AUTOSTART="false",
    EVIDENCE_SECRET_KEY="dGVzdC1vbmx5LWV2aWRlbmNlLWtleS1ub3QtcmVhbCE=",  # test-only Fernet key
    ALERT_SOURCES="",  # tests that need alerts turn them on with set_settings
    RETENTION_INTERVAL_MINUTES="0",
    SITE_TIMEZONE="Asia/Kolkata",
    SHIFTS="A=06:00-14:00,B=14:00-22:00,C=22:00-06:00",
    APP_BASE_URL="https://safevision.example",
)

from fake_supabase import FakeSupabase  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import supabase_client  # noqa: E402


@pytest.fixture
def sb(monkeypatch):
    fake = FakeSupabase()
    monkeypatch.setattr(supabase_client, "create_client", lambda *a, **k: fake)
    supabase_client.get_supabase.cache_clear()

    fake.admin_id = fake.add_user("admin-token", "admin")
    fake.viewer_id = fake.add_user("viewer-token", "viewer")
    yield fake
    supabase_client.get_supabase.cache_clear()


def _modules_with_settings():
    import config

    return [m for name, m in list(sys.modules.items())
            if name.split(".")[0] in ("services", "routes", "auth", "main", "supabase_client")
            and getattr(m, "settings", None) is config.settings]


@pytest.fixture
def set_settings(monkeypatch):
    """set_settings(db_disabled=True, ...): replace settings in every backend module for this test."""
    import config

    def apply(**changes):
        new = dataclasses.replace(config.settings, **changes)
        for m in _modules_with_settings() + [config]:
            monkeypatch.setattr(m, "settings", new)
        return new

    import main  # noqa: F401  (import every module first, so all of them are patched)
    return apply


@pytest.fixture
def local_mode(set_settings, tmp_path, monkeypatch):
    """DB_DISABLED dev mode on a fresh SQLite file and screenshot folder under tmp_path."""
    from services import local_store

    monkeypatch.setattr(local_store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(local_store, "SHOTS_DIR", tmp_path / "shots")
    monkeypatch.setattr(local_store, "_conn", None)
    set_settings(db_disabled=True, auth_disabled=True)
    yield local_store
    if local_store._conn is not None:
        local_store._conn.close()


@pytest.fixture
def client(sb):
    from main import app
    return TestClient(app)

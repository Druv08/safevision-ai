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


@pytest.fixture
def client(sb):
    from main import app
    return TestClient(app)

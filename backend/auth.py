"""
Supabase Auth for the API.

The frontend signs in with supabase-js and sends the access token as
`Authorization: Bearer <token>`. We verify it with Supabase Auth and load the
caller's role from public.profiles.
"""

import logging
from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config import settings
from supabase_client import get_supabase

log = logging.getLogger(__name__)

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class User:
    id: str | None  # None only for the AUTH_DISABLED dev user
    email: str | None
    role: str  # 'admin' | 'viewer'


# No real auth.users row, so id is None (the *_by / audit columns stay null).
_DEV_USER = User(id=None, email="dev@local", role="admin")


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, detail, headers={"WWW-Authenticate": "Bearer"})


def require_viewer(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> User:
    """Any logged-in user with a profile (viewer or admin)."""
    if settings.auth_disabled:
        return _DEV_USER
    if creds is None:
        raise _unauthorized("Not authenticated")

    sb = get_supabase()
    # ponytail: one Auth round-trip per request; cache by token for ~30 s if latency matters.
    try:
        res = sb.auth.get_user(creds.credentials)
    except Exception:
        raise _unauthorized("Invalid or expired token") from None
    if res is None or res.user is None:
        raise _unauthorized("Invalid or expired token")

    profile = sb.table("profiles").select("role").eq("id", res.user.id).limit(1).execute().data
    role = profile[0]["role"] if profile else None
    if role not in ("admin", "viewer"):
        log.warning("User %s has no profile row", res.user.id)
        raise HTTPException(status.HTTP_403_FORBIDDEN, "No profile for this user")

    return User(id=res.user.id, email=res.user.email, role=role)


def require_admin(user: User = Depends(require_viewer)) -> User:
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin role required")
    return user

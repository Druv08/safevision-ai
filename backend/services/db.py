"""Generic table access: Supabase Postgres, or the SQLite dev store when DB_DISABLED=true."""

import sqlite3
from datetime import datetime

from config import settings
from services import local_store
from supabase_client import get_supabase

BATCH = 1000  # PostgREST's default maximum rows per request


def _json(row: dict) -> dict:
    return {k: v.isoformat() if isinstance(v, datetime) else v for k, v in row.items()}


class Conflict(Exception):
    """A unique constraint refused the insert (the row already exists)."""


def select(table: str, order: str = "created_at", desc: bool = False, limit: int | None = None,
           date_from=None, date_to=None, **eq) -> list[dict]:
    """Rows where every `eq` column matches and date_from <= created_at < date_to; all of them unless `limit`."""
    if settings.db_disabled:
        return local_store.select(table, order, desc, limit, date_from, date_to, **eq)
    rows = []
    while True:
        q = get_supabase().table(table).select("*")
        for col, val in eq.items():
            q = q.eq(col, val)
        if date_from is not None:
            q = q.gte("created_at", date_from.isoformat())
        if date_to is not None:
            q = q.lt("created_at", date_to.isoformat())
        n = BATCH if limit is None else min(BATCH, limit - len(rows))
        data = q.order(order, desc=desc).range(len(rows), len(rows) + n - 1).execute().data
        rows += data
        if len(data) < n or (limit is not None and len(rows) >= limit):
            return rows


def insert(table: str, row: dict | list) -> list[dict]:
    """Insert one row or several. Raises Conflict if a unique constraint refuses it."""
    if settings.db_disabled:
        try:
            return [local_store.insert_row(table, r) for r in (row if isinstance(row, list) else [row])]
        except sqlite3.IntegrityError as e:
            raise Conflict(str(e)) from None
    try:
        rows = [_json(r) for r in row] if isinstance(row, list) else _json(row)
        return get_supabase().table(table).insert(rows).execute().data
    except Exception as e:
        if getattr(e, "code", None) == "23505":  # Postgres unique_violation
            raise Conflict(str(e)) from None
        raise


def update(table: str, row_id: str, changes: dict) -> dict | None:
    if settings.db_disabled:
        return local_store.update_row(table, row_id, changes)
    data = get_supabase().table(table).update(_json(changes)).eq("id", row_id).execute().data
    return data[0] if data else None


def delete(table: str, **eq) -> None:
    if settings.db_disabled:
        return local_store.delete_rows(table, **eq)
    q = get_supabase().table(table).delete()
    for col, val in eq.items():
        q = q.eq(col, val)
    q.execute()


def log_audit(user_id: str | None, action: str, target_id: str | None = None, detail: dict | None = None) -> None:
    """Append one row to audit_log (append-only: the database refuses updates and deletes)."""
    insert("audit_log", {"user_id": user_id, "action": action, "target_id": target_id, "detail": detail})


def audit_trail(target_id: str) -> list[dict]:
    """Every audit row about one record, oldest first."""
    return select("audit_log", order="id", target_id=target_id)

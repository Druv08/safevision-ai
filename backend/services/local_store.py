"""
Dev-only local storage used when DB_DISABLED=true: violations in a SQLite file,
screenshots as JPEGs in a folder, both under backend/local-data/.
"""

import base64
import sqlite3
import threading
import uuid
from datetime import datetime, timezone

from config import BACKEND_DIR

DATA_DIR = BACKEND_DIR / "local-data"
SHOTS_DIR = DATA_DIR / "screenshots"

# ponytail: one connection behind a global lock; fine for a single dev user.
_lock = threading.Lock()
_conn = None


def _db() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(DATA_DIR / "violations.db", check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute(
            """create table if not exists violations (
                id text primary key, created_at text not null, type text not null,
                confidence real not null, source text not null, screenshot_path text,
                model_version text, status text not null default 'new',
                acknowledged_by text, closed_by text, note text)"""
        )
    return _conn


def _iso(value) -> str:
    """UTC ISO string with fixed precision, so text comparison matches time order."""
    dt = datetime.fromisoformat(value) if isinstance(value, str) else value
    dt = dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
    return dt.isoformat(timespec="microseconds")


def _one(sql: str, args=()) -> dict | None:
    row = _db().execute(sql, args).fetchone()
    return dict(row) if row else None


def insert(row: dict) -> dict:
    row = {
        "id": str(uuid.uuid4()),
        **row,
        "created_at": _iso(row.get("created_at") or datetime.now(timezone.utc)),
    }
    cols = ", ".join(row)
    with _lock:
        _db().execute(f"insert into violations ({cols}) values ({', '.join('?' * len(row))})", list(row.values()))
        _db().commit()
        return _one("select * from violations where id = ?", (row["id"],))


def query(
    vtype, date_from, date_to, term, page, page_size, status=None, source=None, oldest=False
) -> tuple[list[dict], int]:
    where, args = [], []
    for col, val in (("type", vtype), ("status", status), ("source", source)):
        if val:
            where.append(f"{col} = ?")
            args.append(val)
    if date_from:
        where.append("created_at >= ?")
        args.append(_iso(date_from))
    if date_to:
        where.append("created_at < ?")
        args.append(_iso(date_to))
    if term:
        where.append("(" + " or ".join(f"{c} like ?" for c in ("type", "status", "note", "model_version")) + ")")
        args += [f"%{term}%"] * 4
    sql_where = f" where {' and '.join(where)}" if where else ""
    with _lock:
        total = _db().execute(f"select count(*) from violations{sql_where}", args).fetchone()[0]
        rows = _db().execute(
            f"select * from violations{sql_where} order by created_at {'asc' if oldest else 'desc'} limit ? offset ?",
            [*args, page_size, (page - 1) * page_size],
        ).fetchall()
    return [dict(r) for r in rows], total


def all_rows() -> list[dict]:
    with _lock:
        return [dict(r) for r in _db().execute("select * from violations order by created_at").fetchall()]


def count(vtype: str) -> int:
    with _lock:
        return _db().execute("select count(*) from violations where type = ?", (vtype,)).fetchone()[0]


def get(violation_id: str) -> dict | None:
    with _lock:
        return _one("select * from violations where id = ?", (violation_id,))


def update(violation_id: str, changes: dict) -> dict | None:
    sets = ", ".join(f"{c} = ?" for c in changes)
    with _lock:
        _db().execute(f"update violations set {sets} where id = ?", [*changes.values(), violation_id])
        _db().commit()
        return _one("select * from violations where id = ?", (violation_id,))


def delete(violation_id: str) -> None:
    with _lock:
        _db().execute("delete from violations where id = ?", (violation_id,))
        _db().commit()


# --- screenshots ---------------------------------------------------------------

def save_screenshot(key: str, jpeg_bytes: bytes) -> None:
    path = SHOTS_DIR / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(jpeg_bytes)


def screenshot_data_url(key: str) -> str:
    """Inline data: URL, so the browser needs no extra route to show it."""
    return "data:image/jpeg;base64," + base64.b64encode((SHOTS_DIR / key).read_bytes()).decode()


def delete_screenshot(key: str) -> None:
    (SHOTS_DIR / key).unlink(missing_ok=True)

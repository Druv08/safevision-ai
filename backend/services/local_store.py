"""
Dev-only local storage used when DB_DISABLED=true: violations in a SQLite file,
screenshots as JPEGs in a folder, both under backend/local-data/.
"""

import base64
import json
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
                acknowledged_by text, closed_by text, note text,
                track_id integer, episode_start_s real, episode_end_s real)"""
        )
        # Local DBs created by older versions: add the newer columns.
        for table, cols in (
            ("violations", (("track_id", "integer"), ("episode_start_s", "real"), ("episode_end_s", "real"),
                            ("camera_id", "text"), ("zone_id", "text"), ("started_at", "text"), ("ended_at", "text"),
                            ("action_taken_by", "text"), ("cause", "text"), ("screenshot_sha256", "text"),
                            ("original_path", "text"), ("original_sha256", "text"), ("original_expires_at", "text"),
                            ("screenshot_deleted_at", "text"), ("legal_hold", "integer not null default 0"),
                            ("legal_hold_reason", "text"))),
        ):
            have = {r["name"] for r in _conn.execute(f"pragma table_info({table})")}
            for col, kind in cols:
                if col not in have:
                    _conn.execute(f"alter table {table} add column {col} {kind}")
        _conn.execute(
            """create table if not exists observations (
                id integer primary key autoincrement, created_at text not null, source text not null,
                track_id integer, item text not null, outcome text not null,
                frames_worn integer, frames_missing integer, frames_unknown integer,
                first_s real, last_s real, model_version text, camera_id text)"""
        )
        if "camera_id" not in {r["name"] for r in _conn.execute("pragma table_info(observations)")}:
            _conn.execute("alter table observations add column camera_id text")
        _conn.execute(
            """create table if not exists cameras (
                id text primary key, created_at text not null, updated_at text not null, name text not null,
                url text not null, credentials_enc text, sample_fps real not null,
                default_policy text not null, enabled integer not null default 0)"""
        )
        _conn.execute(
            """create table if not exists zones (
                id text primary key, created_at text not null, camera_id text not null,
                name text not null, policy text not null, polygon text not null)"""
        )
        # Append-only, as in Postgres (migration 0004): the triggers refuse every update and delete.
        _conn.executescript(
            """create table if not exists audit_log (
                id integer primary key autoincrement, created_at text not null, user_id text,
                action text not null, target_id text, detail text);
            create trigger if not exists audit_log_no_update before update on audit_log
                begin select raise(abort, 'audit_log is append-only'); end;
            create trigger if not exists audit_log_no_delete before delete on audit_log
                begin select raise(abort, 'audit_log is append-only'); end;
            create table if not exists alert_recipients (
                id text primary key, created_at text not null, name text not null, channel text not null,
                address text not null, language text not null, enabled integer not null default 1);
            create table if not exists alerts (
                id text primary key, created_at text not null, violation_id text not null,
                recipient_id text not null, recipient_name text, channel text not null, status text not null,
                error text,
                sent_at text, unique (violation_id, recipient_id));"""
        )
    return _conn


def _iso(value) -> str:
    """UTC ISO string with fixed precision, so text comparison matches time order."""
    dt = datetime.fromisoformat(value) if isinstance(value, str) else value
    dt = dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
    return dt.isoformat(timespec="microseconds")


_TIME_COLS = {"created_at", "started_at", "ended_at", "original_expires_at", "screenshot_deleted_at", "sent_at"}


def _times(row: dict) -> dict:
    return {k: _iso(v) if k in _TIME_COLS and v is not None else v for k, v in row.items()}


def _one(sql: str, args=()) -> dict | None:
    row = _db().execute(sql, args).fetchone()
    return dict(row) if row else None


def insert(row: dict) -> dict:
    row = _times({
        "id": str(uuid.uuid4()),
        **row,
        "created_at": row.get("created_at") or datetime.now(timezone.utc),
    })
    cols = ", ".join(row)
    with _lock:
        _db().execute(f"insert into violations ({cols}) values ({', '.join('?' * len(row))})", list(row.values()))
        _db().commit()
        return _one("select * from violations where id = ?", (row["id"],))


def query(
    vtype, date_from, date_to, term, page, page_size, status=None, source=None, oldest=False, camera_id=None,
    zone_id=None,
) -> tuple[list[dict], int]:
    where, args = [], []
    for col, val in (("type", vtype), ("status", status), ("source", source), ("camera_id", camera_id),
                     ("zone_id", zone_id)):
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
    changes = _times(changes)
    sets = ", ".join(f"{c} = ?" for c in changes)
    with _lock:
        _db().execute(f"update violations set {sets} where id = ?", [*changes.values(), violation_id])
        _db().commit()
        return _one("select * from violations where id = ?", (violation_id,))


def delete(violation_id: str) -> None:
    with _lock:
        _db().execute("delete from violations where id = ?", (violation_id,))
        _db().commit()


# --- cameras and zones (generic rows) ---------------------------------------------
# Zone polygons are stored as JSON text; cameras.enabled as 0/1.
_JSON_COLS = {"polygon", "detail"}
_BOOL_COLS = {"enabled", "legal_hold"}


def _decode(row) -> dict:
    d = dict(row)
    for c in _JSON_COLS & d.keys():
        d[c] = None if d[c] is None else json.loads(d[c])
    for c in _BOOL_COLS & d.keys():
        d[c] = bool(d[c])
    return d


def _encode(row: dict) -> dict:
    return _times({k: json.dumps(v) if k in _JSON_COLS and v is not None else v for k, v in row.items()})


def select(table: str, order: str = "created_at", desc: bool = False, limit: int | None = None,
           date_from=None, date_to=None, **eq) -> list[dict]:
    """Rows where every `eq` column matches and date_from <= created_at < date_to."""
    where, args = [f"{c} = ?" for c in eq], list(eq.values())
    if date_from is not None:
        where.append("created_at >= ?")
        args.append(_iso(date_from))
    if date_to is not None:
        where.append("created_at < ?")
        args.append(_iso(date_to))
    sql = f"select * from {table}{' where ' + ' and '.join(where) if where else ''} order by {order}"
    sql += f"{' desc' if desc else ''}{f' limit {int(limit)}' if limit else ''}"
    with _lock:
        return [_decode(r) for r in _db().execute(sql, args).fetchall()]


def retention_candidates(time_col: str, path_col: str, before, limit: int) -> list[dict]:
    """Violations not on legal hold whose `time_col` is before `before` and that still have `path_col`."""
    assert time_col in _TIME_COLS and path_col in ("screenshot_path", "original_path")
    sql = (f"select * from violations where {time_col} < ? and legal_hold = 0 and {path_col} is not null "
           f"order by {time_col} limit ?")
    with _lock:
        return [dict(r) for r in _db().execute(sql, (_iso(before), limit)).fetchall()]


def insert_row(table: str, row: dict) -> dict:
    """Insert one row. Raises sqlite3.IntegrityError on a unique-constraint conflict."""
    now = _iso(datetime.now(timezone.utc))
    row = _encode({"id": str(uuid.uuid4()), "created_at": now, **row})
    if table == "audit_log":
        del row["id"]  # autoincrement
    with _lock:
        sql = f"insert into {table} ({', '.join(row)}) values ({', '.join('?' * len(row))})"
        try:
            cur = _db().execute(sql, list(row.values()))
            _db().commit()
        except sqlite3.Error:
            _db().rollback()
            raise
        return _decode(_db().execute(f"select * from {table} where rowid = ?", (cur.lastrowid,)).fetchone())


def update_row(table: str, row_id: str, changes: dict) -> dict | None:
    changes = _encode(changes)
    with _lock:
        _db().execute(f"update {table} set {', '.join(f'{c} = ?' for c in changes)} where id = ?",
                      [*changes.values(), row_id])
        _db().commit()
        row = _db().execute(f"select * from {table} where id = ?", (row_id,)).fetchone()
        return _decode(row) if row else None


def delete_rows(table: str, **eq) -> None:
    with _lock:
        _db().execute(f"delete from {table} where {' and '.join(f'{c} = ?' for c in eq)}", list(eq.values()))
        _db().commit()


# --- observations ---------------------------------------------------------------

def insert_observations(rows: list[dict]) -> None:
    now = _iso(datetime.now(timezone.utc))
    with _lock:
        for row in rows:
            row = {"created_at": now, **row}
            cols = ", ".join(row)
            _db().execute(f"insert into observations ({cols}) values ({', '.join('?' * len(row))})", list(row.values()))
        _db().commit()


def count_observations(item: str, outcome: str) -> int:
    with _lock:
        sql = "select count(*) from observations where item = ? and outcome = ?"
        return _db().execute(sql, (item, outcome)).fetchone()[0]


# --- screenshots ---------------------------------------------------------------

def save_screenshot(key: str, jpeg_bytes: bytes) -> None:
    path = SHOTS_DIR / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(jpeg_bytes)


def read_screenshot(key: str) -> bytes:
    return (SHOTS_DIR / key).read_bytes()


def screenshot_data_url(key: str) -> str:
    """Inline data: URL, so the browser needs no extra route to show it."""
    return "data:image/jpeg;base64," + base64.b64encode((SHOTS_DIR / key).read_bytes()).decode()


def delete_screenshot(key: str) -> None:
    (SHOTS_DIR / key).unlink(missing_ok=True)

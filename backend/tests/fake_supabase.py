"""
Minimal in-memory stand-in for the supabase-py client.

Implements only the query-builder calls the backend uses. Not a general fake.
"""

import itertools
import json
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

# Mirrors of database rules the backend relies on.
UNIQUE = {"alerts": ("violation_id", "recipient_id")}
APPEND_ONLY = {"audit_log"}  # migration 0004 trigger


class FakeAPIError(Exception):
    def __init__(self, message, code):
        super().__init__(message)
        self.code = code


def _cmp_value(v):
    if isinstance(v, str):
        try:
            return datetime.fromisoformat(v)
        except ValueError:
            return v
    return v


class _Query:
    def __init__(self, db, table):
        self.db, self.table = db, table
        self.op, self.payload = "select", None
        self.filters, self.count, self.order_by, self.slice = [], None, None, None
        self._negate = False

    # builders
    def select(self, *cols, count=None):
        self.count = count
        return self

    def insert(self, row):
        json.dumps(row)  # like supabase-py: a datetime here is a TypeError
        self.op, self.payload = "insert", row
        return self

    def update(self, changes):
        json.dumps(changes)
        self.op, self.payload = "update", changes
        return self

    def delete(self):
        self.op = "delete"
        return self

    def eq(self, col, val):
        self.filters.append(lambda r: str(r.get(col)) == str(val))
        return self

    # SQL: a comparison with null is never true
    def gte(self, col, val):
        self.filters.append(lambda r: r.get(col) is not None and _cmp_value(r[col]) >= _cmp_value(val))
        return self

    def lt(self, col, val):
        self.filters.append(lambda r: r.get(col) is not None and _cmp_value(r[col]) < _cmp_value(val))
        return self

    @property
    def not_(self):
        self._negate = True
        return self

    def is_(self, col, val):
        assert val == "null"
        negate, self._negate = self._negate, False
        self.filters.append(lambda r: (r.get(col) is None) != negate)
        return self

    def like(self, col, pattern):
        prefix = pattern.rstrip("%")
        self.filters.append(lambda r: (r.get(col) or "").startswith(prefix))
        return self

    def or_(self, expr):
        clauses = []
        for part in expr.split(","):
            col, op, pat = part.split(".", 2)
            assert op == "ilike"
            clauses.append((col, pat.strip("*").lower()))
        self.filters.append(lambda r: any(p in (r.get(c) or "").lower() for c, p in clauses))
        return self

    def order(self, col, desc=False):
        self.order_by = (col, desc)
        return self

    def range(self, start, end):
        self.slice = (start, end + 1)
        return self

    def limit(self, n):
        self.slice = (0, n)
        return self

    def execute(self):
        rows = self.db.tables.setdefault(self.table, [])
        if self.table in APPEND_ONLY and self.op in ("update", "delete"):
            raise FakeAPIError(f"{self.table} is append-only", "P0001")
        if self.op == "insert":
            inserted = []
            for payload in self.payload if isinstance(self.payload, list) else [self.payload]:
                row_id = next(self.db.ids) if self.table == "audit_log" else str(uuid.uuid4())
                row = {"id": row_id, "created_at": datetime.now(timezone.utc).isoformat()}
                if self.table == "violations":
                    row.update(status="new", acknowledged_by=None, closed_by=None, legal_hold=False)
                row.update(payload)
                cols = UNIQUE.get(self.table)
                if cols and any(all(r.get(c) == row.get(c) for c in cols) for r in rows):
                    raise FakeAPIError("duplicate key value violates unique constraint", "23505")
                rows.append(row)
                inserted.append(dict(row))
            return SimpleNamespace(data=inserted, count=None)

        matched = [r for r in rows if all(f(r) for f in self.filters)]
        if self.op == "update":
            for r in matched:
                r.update(self.payload)
            return SimpleNamespace(data=[dict(r) for r in matched], count=None)
        if self.op == "delete":
            self.db.tables[self.table] = [r for r in rows if r not in matched]
            return SimpleNamespace(data=[dict(r) for r in matched], count=None)

        if self.order_by:
            col, desc = self.order_by
            matched.sort(key=lambda r: _cmp_value(r[col]), reverse=desc)
        total = len(matched)
        if self.slice:
            matched = matched[self.slice[0]:self.slice[1]]
        return SimpleNamespace(data=[dict(r) for r in matched], count=total if self.count else None)


class _Bucket:
    def __init__(self, objects):
        self.objects = objects

    def upload(self, path, data, options=None):
        assert path not in self.objects, "fake storage: object exists"
        self.objects[path] = data
        return SimpleNamespace(path=path)

    def download(self, path):
        if path not in self.objects:
            raise RuntimeError("Object not found")
        return self.objects[path]

    def create_signed_url(self, path, expires_in):
        if path not in self.objects:
            raise RuntimeError("Object not found")
        url = f"https://fake.supabase.co/storage/v1/object/sign/{path}?expires={expires_in}"
        return {"signedURL": url, "signedUrl": url}

    def remove(self, paths):
        for p in paths:
            self.objects.pop(p, None)
        return []


class _Auth:
    def __init__(self, users):
        self.users = users  # token -> (id, email)

    def get_user(self, jwt=None):
        if jwt not in self.users:
            raise RuntimeError("invalid JWT")
        uid, email = self.users[jwt]
        return SimpleNamespace(user=SimpleNamespace(id=uid, email=email))


class FakeSupabase:
    def __init__(self):
        self.tables = {}
        self.objects = {}
        self.ids = itertools.count(1)
        self.tokens = {}
        self.auth = _Auth(self.tokens)
        self.storage = SimpleNamespace(from_=lambda bucket: _Bucket(self.objects))

    def table(self, name):
        return _Query(self, name)

    def add_user(self, token, role, email=None):
        uid = str(uuid.uuid4())
        self.tokens[token] = (uid, email or f"{token}@example.com")
        if role is not None:
            self.tables.setdefault("profiles", []).append({"id": uid, "full_name": None, "role": role})
        return uid


ADMIN = {"Authorization": "Bearer admin-token"}
VIEWER = {"Authorization": "Bearer viewer-token"}

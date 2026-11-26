"""Direct psycopg2 access for the DSS action log (no ORM)."""

from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime, timezone

import psycopg2
from psycopg2.extras import RealDictCursor

from .config import postgres_settings

COLUMNS = (
    "id",
    "created_at",
    "action",
    "route",
    "level",
    "detail",
    "status",
    "updated_at",
)


@contextmanager
def connection(config: dict | None = None):
    conn = psycopg2.connect(**postgres_settings(config))
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def fetch_all(
    sql: str, params: dict | None = None, config: dict | None = None
) -> list[dict]:
    """Run a read query and return every row as a plain dict."""
    with connection(config) as conn, conn.cursor(
        cursor_factory=RealDictCursor
    ) as cur:
        cur.execute(sql, params or {})
        return [dict(row) for row in cur.fetchall()]


def fetch_one(
    sql: str, params: dict | None = None, config: dict | None = None
) -> dict | None:
    """Run a read query and return the first row as a plain dict."""
    with connection(config) as conn, conn.cursor(
        cursor_factory=RealDictCursor
    ) as cur:
        cur.execute(sql, params or {})
        row = cur.fetchone()
        return dict(row) if row is not None else None


def execute(
    sql: str, params: dict | None = None, config: dict | None = None
) -> int:
    """Run a write statement and return the affected row count."""
    with connection(config) as conn, conn.cursor() as cur:
        cur.execute(sql, params or {})
        return cur.rowcount


def _iso_utc(value: datetime) -> str:
    """Match Django's JSON datetime shape: UTC, milliseconds, trailing Z."""
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc)
    return value.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _action_dict(row) -> dict:
    """Map an action-log row (with status columns) to the JSON payload."""
    return {
        "id": int(row[0]),
        "created_at": _iso_utc(row[1]),
        "action": row[2],
        "route": row[3],
        "level": row[4],
        "detail": row[5],
        "status": row[6],
        "updated_at": _iso_utc(row[7]) if row[7] is not None else None,
    }


ACTION_COLUMNS = (
    "id, created_at, action, route, level, detail, status, updated_at"
)


def insert_action(body: dict, config: dict | None = None) -> None:
    """Insert exactly the fields the Django model stored."""
    now = datetime.now(timezone.utc)
    row = {
        "created_at": now,
        "action": str(body.get("action", ""))[:40],
        "route": str(body.get("route", ""))[:20],
        "level": str(body.get("level", ""))[:10],
        "detail": json.dumps(body, ensure_ascii=False),
    }
    with connection(config) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO dss_action_log "
            "(created_at, action, route, level, detail, status, updated_at) "
            "VALUES (%s, %s, %s, %s, %s, 'recorded', %s)",
            (
                row["created_at"],
                row["action"],
                row["route"],
                row["level"],
                row["detail"],
                now,
            ),
        )


def list_actions(config: dict | None = None) -> list[dict]:
    with connection(config) as conn, conn.cursor() as cur:
        cur.execute(
            f"SELECT {ACTION_COLUMNS} FROM dss_action_log "
            "ORDER BY created_at DESC, id DESC LIMIT 50"
        )
        rows = cur.fetchall()
    return [_action_dict(row) for row in rows]


def update_action_status(
    action_id: int, status: str, config: dict | None = None
) -> dict | None:
    """Cập nhật trạng thái theo dõi thủ công; trả None nếu không tìm thấy id."""
    with connection(config) as conn, conn.cursor() as cur:
        cur.execute(
            f"UPDATE dss_action_log SET status = %s, updated_at = %s "
            f"WHERE id = %s RETURNING {ACTION_COLUMNS}",
            (status, datetime.now(timezone.utc), action_id),
        )
        row = cur.fetchone()
    return _action_dict(row) if row is not None else None


def clear_actions(config: dict | None = None) -> None:
    with connection(config) as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM dss_action_log")


def count_actions(config: dict | None = None) -> int:
    with connection(config) as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM dss_action_log")
        return int(cur.fetchone()[0])

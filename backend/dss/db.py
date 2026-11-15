"""Direct psycopg2 access for the DSS action log (no ORM)."""

from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime, timezone

import psycopg2
from psycopg2.extras import RealDictCursor

from .config import postgres_settings

COLUMNS = ("created_at", "action", "route", "level", "detail")


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


def insert_action(body: dict, config: dict | None = None) -> None:
    """Insert exactly the fields the Django model stored."""
    row = {
        "created_at": datetime.now(timezone.utc),
        "action": str(body.get("action", ""))[:40],
        "route": str(body.get("route", ""))[:20],
        "level": str(body.get("level", ""))[:10],
        "detail": json.dumps(body, ensure_ascii=False),
    }
    with connection(config) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO dss_action_log (created_at, action, route, level, detail) "
            "VALUES (%s, %s, %s, %s, %s)",
            (
                row["created_at"],
                row["action"],
                row["route"],
                row["level"],
                row["detail"],
            ),
        )


def list_actions(config: dict | None = None) -> list[dict]:
    with connection(config) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT created_at, action, route, level, detail "
            "FROM dss_action_log ORDER BY created_at DESC LIMIT 50"
        )
        rows = cur.fetchall()
    return [
        {
            "created_at": _iso_utc(row[0]),
            "action": row[1],
            "route": row[2],
            "level": row[3],
            "detail": row[4],
        }
        for row in rows
    ]


def clear_actions(config: dict | None = None) -> None:
    with connection(config) as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM dss_action_log")


def count_actions(config: dict | None = None) -> int:
    with connection(config) as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM dss_action_log")
        return int(cur.fetchone()[0])

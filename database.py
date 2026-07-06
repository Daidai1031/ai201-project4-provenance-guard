"""
SQLite storage.

Milestone 3 scope: just the audit log (append-only). The `decisions` table
(needed for the appeal lookup) gets added in Milestone 5 once the appeal
endpoint exists - no point building storage for a feature that isn't there
yet.
"""

import json
import os
import sqlite3
from contextlib import contextmanager

DB_PATH = os.environ.get("TEAGUARD_DB_PATH", os.path.join(os.path.dirname(__file__), "teaguard.db"))


@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                content_id TEXT NOT NULL,
                creator_id TEXT,
                timestamp TEXT NOT NULL,
                data TEXT NOT NULL
            )
        """)


def append_log_entry(event_type: str, content_id: str, creator_id: str, timestamp: str, data: dict):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO audit_log (event_type, content_id, creator_id, timestamp, data) "
            "VALUES (?, ?, ?, ?, ?)",
            (event_type, content_id, creator_id, timestamp, json.dumps(data)),
        )


def get_log_entries(limit: int = 100):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT data FROM audit_log ORDER BY id ASC LIMIT ?", (limit,)
        ).fetchall()
        return [json.loads(row["data"]) for row in rows]
"""
SQLite storage: decision records (for appeal lookups) and the structured
audit log (for GET /log).

Two tables:
  - decisions: one row per content_id, holding the CURRENT state of that
    piece of content (status, scores, whether it has been appealed). This
    is what the /appeal endpoint reads and updates. Added in Milestone 5.
  - audit_log: one row per EVENT (a submission or an appeal). Append-only,
    never updated in place, so it is a true audit trail. Existed since
    Milestone 3.
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
            CREATE TABLE IF NOT EXISTS decisions (
                content_id TEXT PRIMARY KEY,
                creator_id TEXT NOT NULL,
                text TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                attribution TEXT NOT NULL,
                confidence REAL NOT NULL,
                privacy_risk_score REAL NOT NULL,
                defamation_risk_score REAL NOT NULL,
                ai_generated_score REAL NOT NULL,
                overall_risk TEXT NOT NULL,
                recommended_action TEXT NOT NULL,
                status TEXT NOT NULL,
                transparency_label TEXT NOT NULL,
                signals_used TEXT NOT NULL,
                appeal_filed INTEGER NOT NULL DEFAULT 0
            )
        """)
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


def save_decision(record: dict):
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO decisions (
                content_id, creator_id, text, timestamp, attribution, confidence,
                privacy_risk_score, defamation_risk_score, ai_generated_score,
                overall_risk, recommended_action, status, transparency_label,
                signals_used, appeal_filed
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            record["content_id"], record["creator_id"], record["text"],
            record["timestamp"], record["attribution"], record["confidence"],
            record["privacy_risk_score"], record["defamation_risk_score"],
            record["ai_generated_score"], record["overall_risk"],
            record["recommended_action"], record["status"],
            record["transparency_label"], json.dumps(record["signals_used"]),
            int(record.get("appeal_filed", False)),
        ))


def get_decision(content_id: str):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM decisions WHERE content_id = ?", (content_id,)
        ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["signals_used"] = json.loads(result["signals_used"])
        result["appeal_filed"] = bool(result["appeal_filed"])
        return result


def mark_under_review(content_id: str):
    with get_connection() as conn:
        conn.execute(
            "UPDATE decisions SET status = 'under_review', appeal_filed = 1 "
            "WHERE content_id = ?",
            (content_id,),
        )


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
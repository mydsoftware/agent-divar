# -*- coding: utf-8 -*-
"""لایه ذخیره‌سازی محلی و مهاجرت نسخه‌پذیر پایگاه‌داده Agent Divar."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "data" / "leads.sqlite3"
CURRENT_SCHEMA_VERSION = 5


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class ClosingConnection(sqlite3.Connection):
    """اتصال SQLite که پس از خروج از بلوک with حتماً بسته می‌شود."""

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


def connect(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """اتصال SQLite با تنظیمات یکسان؛ ساخت و مهاجرت با initialize انجام می‌شود."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path), timeout=15, factory=ClosingConnection)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA busy_timeout=15000")
    return con


def initialize(db_path: str | Path = DEFAULT_DB_PATH) -> None:
    """ساخت جداول پایه و اجرای مهاجرت‌های افزایشی بدون حذف داده‌های قبلی."""
    with connect(db_path) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS campaigns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT '',
                city TEXT NOT NULL DEFAULT '',
                keywords TEXT NOT NULL DEFAULT '',
                message_template TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                published_within_hours INTEGER NOT NULL DEFAULT 168
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id INTEGER,
                ad_url TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL DEFAULT '',
                category TEXT NOT NULL DEFAULT '',
                city TEXT NOT NULL DEFAULT '',
                public_contact TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '',
                consent_status TEXT NOT NULL DEFAULT 'نامشخص',
                stage TEXT NOT NULL DEFAULT 'جدید',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(campaign_id) REFERENCES campaigns(id)
            )
        """)

        lead_columns = {
            row["name"] for row in con.execute("PRAGMA table_info(leads)")
        }
        lead_additions = {
            "price": "INTEGER",
            "area": "REAL",
            "rooms": "INTEGER",
            "location": "TEXT NOT NULL DEFAULT ''",
            "features_json": "TEXT NOT NULL DEFAULT '[]'",
        }
        for column, definition in lead_additions.items():
            if column not in lead_columns:
                con.execute(f"ALTER TABLE leads ADD COLUMN {column} {definition}")

        campaign_columns = {
            row["name"] for row in con.execute("PRAGMA table_info(campaigns)")
        }
        if "published_within_hours" not in campaign_columns:
            con.execute(
                "ALTER TABLE campaigns ADD COLUMN published_within_hours "
                "INTEGER NOT NULL DEFAULT 168"
            )

        con.execute("""
            CREATE TABLE IF NOT EXISTS buyer_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                public_contact TEXT NOT NULL DEFAULT '',
                max_budget INTEGER,
                min_area REAL,
                max_area REAL,
                rooms INTEGER,
                location TEXT NOT NULL DEFAULT '',
                required_features_json TEXT NOT NULL DEFAULT '[]',
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        con.execute("CREATE INDEX IF NOT EXISTS idx_buyer_profiles_updated ON buyer_profiles(updated_at)")

        con.execute("""
            CREATE TABLE IF NOT EXISTS interaction_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                buyer_id INTEGER,
                lead_id INTEGER,
                interaction_type TEXT NOT NULL,
                summary TEXT NOT NULL,
                outcome TEXT NOT NULL DEFAULT '',
                occurred_at TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(buyer_id) REFERENCES buyer_profiles(id) ON DELETE CASCADE,
                FOREIGN KEY(lead_id) REFERENCES leads(id) ON DELETE CASCADE,
                CHECK (buyer_id IS NOT NULL OR lead_id IS NOT NULL)
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                buyer_id INTEGER,
                lead_id INTEGER,
                title TEXT NOT NULL,
                due_at TEXT NOT NULL,
                priority TEXT NOT NULL DEFAULT 'normal',
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                completed_at TEXT,
                FOREIGN KEY(buyer_id) REFERENCES buyer_profiles(id) ON DELETE CASCADE,
                FOREIGN KEY(lead_id) REFERENCES leads(id) ON DELETE CASCADE,
                CHECK (buyer_id IS NOT NULL OR lead_id IS NOT NULL),
                CHECK (priority IN ('low','normal','high')),
                CHECK (status IN ('pending','done','cancelled'))
            )
        """)
        con.execute("CREATE INDEX IF NOT EXISTS idx_interactions_buyer_time ON interaction_logs(buyer_id, occurred_at DESC)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_interactions_lead_time ON interaction_logs(lead_id, occurred_at DESC)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_reminders_due_status ON reminders(status, due_at)")

        con.execute("""
            CREATE TABLE IF NOT EXISTS event_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                entity_type TEXT NOT NULL DEFAULT '',
                entity_id INTEGER,
                message TEXT NOT NULL DEFAULT '',
                details_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS task_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_type TEXT NOT NULL,
                status TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                error TEXT NOT NULL DEFAULT '',
                metadata_json TEXT NOT NULL DEFAULT '{}'
            )
        """)
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_leads_campaign_stage "
            "ON leads(campaign_id, stage)"
        )
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_leads_created_at ON leads(created_at)"
        )
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_created_at "
            "ON event_logs(created_at)"
        )
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_task_runs_status "
            "ON task_runs(status, started_at)"
        )
        con.execute(f"PRAGMA user_version={CURRENT_SCHEMA_VERSION}")


def record_event(
    db_path: str | Path,
    event_type: str,
    *,
    entity_type: str = "",
    entity_id: int | None = None,
    message: str = "",
    details: dict[str, Any] | None = None,
) -> int:
    """ثبت رویداد عملیاتی؛ جزئیات باید فاقد رمز و اطلاعات حساس غیرضروری باشد."""
    if not event_type.strip():
        raise ValueError("event_type نباید خالی باشد.")
    payload = json.dumps(details or {}, ensure_ascii=False, sort_keys=True)
    with connect(db_path) as con:
        cur = con.execute(
            """INSERT INTO event_logs
               (event_type, entity_type, entity_id, message, details_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (event_type.strip(), entity_type, entity_id, message, payload, _utc_now()),
        )
        return int(cur.lastrowid)


def start_task(
    db_path: str | Path, task_type: str, metadata: dict[str, Any] | None = None
) -> int:
    if not task_type.strip():
        raise ValueError("task_type نباید خالی باشد.")
    with connect(db_path) as con:
        cur = con.execute(
            """INSERT INTO task_runs
               (task_type, status, started_at, metadata_json)
               VALUES (?, 'running', ?, ?)""",
            (
                task_type.strip(),
                _utc_now(),
                json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True),
            ),
        )
        return int(cur.lastrowid)


def finish_task(
    db_path: str | Path,
    task_id: int,
    *,
    status: str = "completed",
    error: str = "",
) -> None:
    if status not in {"completed", "failed", "cancelled"}:
        raise ValueError("وضعیت پایان وظیفه نامعتبر است.")
    with connect(db_path) as con:
        cur = con.execute(
            """UPDATE task_runs SET status=?, finished_at=?, error=?
               WHERE id=? AND status='running'""",
            (status, _utc_now(), error, task_id),
        )
        if cur.rowcount != 1:
            raise ValueError("وظیفه وجود ندارد یا قبلاً بسته شده است.")

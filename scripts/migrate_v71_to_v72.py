#!/usr/bin/env python3
"""Idempotent migration from Mnemosyne v7.1 to v7.2 draft."""

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "graph.db"
META_PATH = ROOT / "meta.json"
VERSION = "7.2.0-draft"


def _columns(cur, table: str) -> set:
    return {row[1] for row in cur.execute(f"PRAGMA table_info({table})").fetchall()}


def _add_column(cur, table: str, name: str, ddl: str):
    if name not in _columns(cur, table):
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


def migrate(db_path: str = None, meta_path: str = None) -> dict:
    db = Path(db_path) if db_path else DB_PATH
    meta = Path(meta_path) if meta_path else META_PATH

    conn = sqlite3.connect(str(db))
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS skill_usage_feedback (
                id TEXT PRIMARY KEY,
                skill_id TEXT NOT NULL,
                feedback_node_id TEXT,
                task_context TEXT,
                used_as TEXT NOT NULL,
                outcome TEXT NOT NULL,
                rating TEXT,
                verification_result TEXT,
                note TEXT,
                created_prompt_id TEXT,
                audit_required INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(skill_id) REFERENCES nodes(id),
                FOREIGN KEY(feedback_node_id) REFERENCES nodes(id)
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_skill_usage_feedback_skill ON skill_usage_feedback(skill_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_skill_usage_feedback_outcome ON skill_usage_feedback(outcome)")
        _add_column(cur, "skill_test_prompts", "metadata", "TEXT DEFAULT '{}'")
        cur.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
        cur.execute("INSERT OR REPLACE INTO meta(key, value) VALUES('version', ?)", (VERSION,))
        cur.execute("INSERT OR REPLACE INTO meta(key, value) VALUES('migrated_v72_skill_evidence_flow', 'done')")
        cur.execute("INSERT OR REPLACE INTO meta(key, value) VALUES('last_migration', ?)", (datetime.now(timezone.utc).isoformat(),))
        conn.commit()
    finally:
        conn.close()

    data = {}
    if meta.exists():
        try:
            data = json.loads(meta.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
    data["version"] = VERSION
    data["last_migration"] = datetime.now(timezone.utc).isoformat()
    meta.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return {"db_path": str(db), "meta_path": str(meta), "version": VERSION}


if __name__ == "__main__":
    db_arg = sys.argv[1] if len(sys.argv) > 1 else None
    result = migrate(db_arg)
    print(f"[migrate_v71_to_v72] migrated {result['db_path']} to {result['version']}")

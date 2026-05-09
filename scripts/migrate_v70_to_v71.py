#!/usr/bin/env python3
"""Mnemosyne v7.0 -> v7.1 migration.

Adds bilateral Skill Evolution experiment tables and latest decision fields.
The migration is idempotent and never deletes existing v7.0 data.
"""

import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "graph.db"
META_PATH = Path(__file__).resolve().parent.parent / "meta.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _columns(cur, table: str) -> set:
    return {row[1] for row in cur.execute(f"PRAGMA table_info({table})").fetchall()}


def _add_column(cur, table: str, name: str, ddl: str):
    if name not in _columns(cur, table):
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


def step1_backup(db_path: str):
    backup_path = db_path + f".v70.bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(db_path, backup_path)
    size_kb = Path(backup_path).stat().st_size / 1024
    print(f"[step1] backup created: {backup_path} ({size_kb:.0f} KB)")
    return backup_path


def step2_extend_skill_artifacts(cur):
    _add_column(cur, "skill_artifacts", "latest_darwin_score", "REAL")
    _add_column(cur, "skill_artifacts", "latest_mnemosyne_score", "REAL")
    _add_column(cur, "skill_artifacts", "latest_live_test_delta", "REAL")
    _add_column(cur, "skill_artifacts", "latest_eval_mode", "TEXT")
    _add_column(cur, "skill_artifacts", "latest_decision", "TEXT")
    _add_column(cur, "skill_artifacts", "latest_decision_reason", "TEXT")


def step3_create_bilateral_tables(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS skill_test_prompts (
            id TEXT PRIMARY KEY,
            skill_id TEXT NOT NULL,
            prompt_id TEXT NOT NULL,
            prompt TEXT NOT NULL,
            expected TEXT,
            tags TEXT DEFAULT '[]',
            status TEXT DEFAULT 'active',
            approved_by TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(skill_id, prompt_id),
            FOREIGN KEY(skill_id) REFERENCES nodes(id)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS skill_eval_runs (
            id TEXT PRIMARY KEY,
            skill_id TEXT NOT NULL,
            prompt_id TEXT,
            round INTEGER DEFAULT 0,
            eval_mode TEXT NOT NULL,
            baseline_output TEXT,
            with_skill_output TEXT,
            judge_output TEXT,
            baseline_score REAL,
            with_skill_score REAL,
            live_test_delta REAL,
            regression INTEGER DEFAULT 0,
            darwin_score REAL,
            mnemosyne_score REAL,
            decision TEXT,
            decision_reason TEXT,
            file_hash_before TEXT,
            file_hash_after TEXT,
            kept INTEGER DEFAULT 0,
            reverted INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(skill_id) REFERENCES nodes(id)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS skill_mutations (
            id TEXT PRIMARY KEY,
            skill_id TEXT NOT NULL,
            eval_run_id TEXT,
            round INTEGER DEFAULT 0,
            target_dimension TEXT,
            reason TEXT,
            patch_summary TEXT,
            file_hash_before TEXT,
            file_hash_after TEXT,
            status TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(skill_id) REFERENCES nodes(id)
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_skill_test_prompts_skill ON skill_test_prompts(skill_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_skill_eval_runs_skill ON skill_eval_runs(skill_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_skill_mutations_skill ON skill_mutations(skill_id)")


def step4_update_meta(db_path: str, update_meta_json: bool):
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("INSERT OR REPLACE INTO meta(key, value) VALUES('version', '7.1.0-draft')")
        cur.execute("INSERT OR REPLACE INTO meta(key, value) VALUES('migrated_v71_bilateral_skill_evolution', 'done')")
        cur.execute("INSERT OR REPLACE INTO meta(key, value) VALUES('last_migration', ?)", (_now_iso(),))
        conn.commit()
    finally:
        conn.close()

    if update_meta_json and META_PATH.exists():
        import json
        data = json.loads(META_PATH.read_text(encoding="utf-8"))
        data["version"] = "7.1.0-draft"
        data["last_migration"] = _now_iso()
        META_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def migrate(db_path: str = None, backup: bool = True):
    path = str(db_path or DB_PATH)
    if not Path(path).exists():
        raise FileNotFoundError(f"database not found: {path}")
    print(f"[migrate] Mnemosyne v7.0 -> v7.1 bilateral skill evolution: {path}")
    if backup:
        step1_backup(path)
    conn = sqlite3.connect(path)
    try:
        cur = conn.cursor()
        step2_extend_skill_artifacts(cur)
        step3_create_bilateral_tables(cur)
        conn.commit()
    finally:
        conn.close()
    step4_update_meta(path, Path(path).resolve() == DB_PATH.resolve())
    print("[migrate] complete")


if __name__ == "__main__":
    migrate(sys.argv[1] if len(sys.argv) > 1 else None)

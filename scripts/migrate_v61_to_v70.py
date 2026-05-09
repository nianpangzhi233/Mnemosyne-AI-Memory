#!/usr/bin/env python3
"""Mnemosyne v6.1 -> v7.0 migration.

Adds first-class Skill Memory System tables. The script is idempotent:
re-running it keeps existing data and only ensures tables, indexes, and meta
markers exist.
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


def step1_backup(db_path: str):
    backup_path = db_path + f".v61.bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(db_path, backup_path)
    size_kb = Path(backup_path).stat().st_size / 1024
    print(f"[step1] backup created: {backup_path} ({size_kb:.0f} KB)")
    return backup_path


def step2_create_skill_tables(db_path: str):
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS skill_artifacts (
                node_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                slug TEXT UNIQUE,
                status TEXT NOT NULL DEFAULT 'draft',
                version TEXT DEFAULT '0.1.0',

                trigger_patterns TEXT DEFAULT '[]',
                preconditions TEXT DEFAULT '[]',
                procedure TEXT DEFAULT '[]',
                verification TEXT,
                failure_modes TEXT DEFAULT '[]',

                risk_level TEXT DEFAULT 'medium',
                review_status TEXT DEFAULT 'draft',
                approval_mode TEXT,
                inject_enabled INTEGER DEFAULT 0,
                trial_enabled INTEGER DEFAULT 0,
                requires_feedback INTEGER DEFAULT 0,

                mnemosyne_score REAL,
                darwin_score REAL,
                final_score REAL,

                source_node_ids TEXT DEFAULT '[]',
                evidence_node_ids TEXT DEFAULT '[]',

                trial_count INTEGER DEFAULT 0,
                trial_success_count INTEGER DEFAULT 0,
                trial_failure_count INTEGER DEFAULT 0,
                last_trial_at TEXT,
                promotion_candidate INTEGER DEFAULT 0,
                needs_revision INTEGER DEFAULT 0,

                file_path TEXT,
                file_hash TEXT,
                file_synced_at TEXT,

                created_at TEXT NOT NULL,
                updated_at TEXT,
                approved_at TEXT,
                deprecated_at TEXT,

                metadata TEXT DEFAULT '{}',

                FOREIGN KEY(node_id) REFERENCES nodes(id)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS skill_evolution_runs (
                id TEXT PRIMARY KEY,
                skill_node_id TEXT NOT NULL,
                old_score REAL,
                new_score REAL,
                mnemosyne_score REAL,
                darwin_score REAL,
                status TEXT,
                dimension TEXT,
                note TEXT,
                eval_mode TEXT,
                created_at TEXT NOT NULL,
                metadata TEXT DEFAULT '{}',
                FOREIGN KEY(skill_node_id) REFERENCES nodes(id)
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_skill_status ON skill_artifacts(status)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_skill_inject ON skill_artifacts(inject_enabled)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_skill_trial ON skill_artifacts(trial_enabled)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_skill_slug ON skill_artifacts(slug)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_skill_promotion ON skill_artifacts(promotion_candidate)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_skill_evolution_skill ON skill_evolution_runs(skill_node_id)")
        cur.execute(
            "INSERT OR REPLACE INTO meta(key, value) VALUES('migrated_v70_skills', 'done')"
        )
        conn.commit()
        print("[step2] skill tables and indexes ensured")
    finally:
        conn.close()


def step3_verify(db_path: str):
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        tables = {r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        required = {"skill_artifacts", "skill_evolution_runs"}
        missing = sorted(required - tables)
        if missing:
            raise RuntimeError(f"missing tables: {', '.join(missing)}")
        skill_count = cur.execute("SELECT COUNT(*) FROM skill_artifacts").fetchone()[0]
        print(f"[step3] verified skill tables, current artifacts={skill_count}")
    finally:
        conn.close()


def step4_update_meta(db_path: str):
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("INSERT OR REPLACE INTO meta(key, value) VALUES('version', '7.0.0')")
        cur.execute("INSERT OR REPLACE INTO meta(key, value) VALUES('last_migration', ?)", (_now_iso(),))
        conn.commit()
        print("[step4] meta.version set to 7.0.0")
    finally:
        conn.close()

    if META_PATH.exists():
        import json
        data = json.loads(META_PATH.read_text(encoding="utf-8"))
        data["version"] = "7.0.0"
        data["last_migration"] = _now_iso()
        META_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[step4] meta.json updated: {META_PATH}")


def migrate(db_path: str = None):
    path = str(db_path or DB_PATH)
    if not Path(path).exists():
        raise FileNotFoundError(f"database not found: {path}")
    print(f"[migrate] Mnemosyne v6.1 -> v7.0: {path}")
    step1_backup(path)
    step2_create_skill_tables(path)
    step3_verify(path)
    step4_update_meta(path)
    print("[migrate] complete")


if __name__ == "__main__":
    migrate(sys.argv[1] if len(sys.argv) > 1 else None)

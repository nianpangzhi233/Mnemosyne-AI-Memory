#!/usr/bin/env python3
"""Normalize legacy task_type values in graph.db.

Default mode is dry-run. Use --apply to write changes after reviewing output.
"""

import argparse
import json
import shutil
import sqlite3
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
ROOT = SCRIPTS_DIR.parent
DB_PATH = ROOT / "graph.db"

sys.path.insert(0, str(SCRIPTS_DIR))

from core.sqlite_store import _normalize_task_type  # noqa: E402


def _backup_db() -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = ROOT / f"graph.backup-before-task-type-normalize-{stamp}.db"
    shutil.copy2(DB_PATH, backup)
    return backup


def _load_registered(conn: sqlite3.Connection) -> list[str]:
    row = conn.execute("SELECT value FROM meta WHERE key='registered_task_types'").fetchone()
    if not row:
        return []
    try:
        data = json.loads(row[0])
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize task_type values")
    parser.add_argument("--apply", action="store_true", help="Write changes to graph.db")
    parser.add_argument("--no-backup", action="store_true", help="Skip DB backup when applying")
    args = parser.parse_args()

    conn = sqlite3.connect(str(DB_PATH))
    try:
        rows = conn.execute(
            "SELECT id, task_type FROM nodes WHERE task_type IS NOT NULL"
        ).fetchall()
        changes = []
        for node_id, old_type in rows:
            new_type = _normalize_task_type(old_type)
            if new_type and new_type != old_type:
                changes.append((node_id, old_type, new_type))

        registered = _load_registered(conn)
        normalized_registered = sorted({
            normalized for item in registered
            for normalized in [_normalize_task_type(item)]
            if normalized
        })
    finally:
        conn.close()

    print(f"mode: {'APPLY' if args.apply else 'DRY-RUN'}")
    print(f"node_changes: {len(changes)}")
    old_counts = Counter(old for _, old, _ in changes)
    new_counts = Counter(new for _, _, new in changes)
    if old_counts:
        print("old values:")
        for value, count in old_counts.most_common(30):
            print(f"  {value}: {count}")
        print("new values:")
        for value, count in new_counts.most_common(30):
            print(f"  {value}: {count}")
    print(f"registered_types: {len(registered)} -> {len(normalized_registered)}")
    print(", ".join(normalized_registered))

    if not args.apply:
        print("dry-run only; rerun with --apply to write changes")
        return 0

    backup = None if args.no_backup else _backup_db()
    if backup:
        print(f"backup: {backup}")

    conn = sqlite3.connect(str(DB_PATH))
    try:
        for node_id, _old_type, new_type in changes:
            conn.execute(
                "UPDATE nodes SET task_type=?, updated_at=datetime('now') WHERE id=?",
                (new_type, node_id),
            )
        conn.execute(
            "INSERT OR REPLACE INTO meta(key, value) VALUES('registered_task_types', ?)",
            (json.dumps(normalized_registered, ensure_ascii=False),),
        )
        conn.commit()
    finally:
        conn.close()

    print(f"updated_nodes: {len(changes)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

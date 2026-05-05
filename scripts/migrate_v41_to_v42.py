#!/usr/bin/env python3
"""v4.1 → v4.2 数据库迁移

新增 abstract / overview 字段，回填现有节点。
幂等：重复执行不报错、不重复操作。
"""

import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "graph.db"

MAX_ABSTRACT_CHARS = 150
MAX_OVERVIEW_CHARS = 600


def _generate_abstract(content: str, principle: str = None) -> str:
    parts = [content[:MAX_ABSTRACT_CHARS]]
    if principle and len(parts[0]) + len(principle) + 3 <= MAX_ABSTRACT_CHARS:
        parts.append(principle)
    return " | ".join(parts)[:MAX_ABSTRACT_CHARS]


def _generate_overview(content: str, principle: str = None, tags: str = None) -> str:
    parts = [content[:MAX_OVERVIEW_CHARS]]
    if principle:
        parts.append(f"原理: {principle}")
    if tags and tags != "[]":
        parts.append(f"标签: {tags}")
    return "\n".join(parts)[:MAX_OVERVIEW_CHARS]


def migrate(db_path: str = None):
    path = db_path or str(DB_PATH)
    conn = sqlite3.connect(path)
    cur = conn.cursor()

    cols = [r[1] for r in cur.execute("PRAGMA table_info(nodes)").fetchall()]

    added = []
    if "abstract" not in cols:
        cur.execute("ALTER TABLE nodes ADD COLUMN abstract TEXT")
        added.append("abstract")
    if "overview" not in cols:
        cur.execute("ALTER TABLE nodes ADD COLUMN overview TEXT")
        added.append("overview")

    if not added:
        print("[migrate] abstract/overview 已存在，跳过 ALTER TABLE")
    else:
        print(f"[migrate] 新增字段: {', '.join(added)}")

    rows = cur.execute(
        "SELECT id, content, principle, tags FROM nodes WHERE abstract IS NULL"
    ).fetchall()

    count = 0
    for node_id, content, principle, tags in rows:
        abstract = _generate_abstract(content, principle)
        overview = _generate_overview(content, principle, tags)
        cur.execute(
            "UPDATE nodes SET abstract = ?, overview = ? WHERE id = ?",
            (abstract, overview, node_id),
        )
        count += 1

    conn.commit()

    total = cur.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
    with_abs = cur.execute(
        "SELECT COUNT(*) FROM nodes WHERE abstract IS NOT NULL"
    ).fetchone()[0]
    conn.close()

    print(f"[migrate] 回填 {count} 个节点")
    print(f"[migrate] 总计 {total} 节点，{with_abs} 已有 abstract（覆盖率 {with_abs/total*100:.0f}%）")


if __name__ == "__main__":
    migrate()

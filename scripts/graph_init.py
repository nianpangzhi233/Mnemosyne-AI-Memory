#!/usr/bin/env python3
"""Mnemosyne v4.1 — 建库建表脚本

创建 graph.db 及其所有表、索引、触发器。
支持重复运行（IF NOT EXISTS 保护）。
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "graph.db"


def init_db(db_path: str = None):
    """创建 graph.db，建所有表和索引"""
    path = db_path or str(DB_PATH)
    conn = sqlite3.connect(path)
    cur = conn.cursor()

    # ── nodes 表 ──
    cur.execute("""
        CREATE TABLE IF NOT EXISTS nodes (
            id TEXT PRIMARY KEY,
            type TEXT NOT NULL,
            content TEXT NOT NULL,
            principle TEXT,
            vector BLOB,
            tier TEXT DEFAULT 'hot',
            decay_score REAL DEFAULT 0.8,
            base_score REAL DEFAULT 0.8,
            access_count INTEGER DEFAULT 0,
            last_access TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT,
            task_type TEXT,
            project TEXT,
            tags TEXT,
            metadata TEXT
        )
    """)

    # ── edges 表 ──
    cur.execute("""
        CREATE TABLE IF NOT EXISTS edges (
            id TEXT PRIMARY KEY,
            from_id TEXT NOT NULL,
            to_id TEXT NOT NULL,
            relation_type TEXT NOT NULL,
            weight REAL DEFAULT 0.5,
            source TEXT DEFAULT 'auto',
            status TEXT DEFAULT 'active',
            created_at TEXT NOT NULL,
            FOREIGN KEY (from_id) REFERENCES nodes(id),
            FOREIGN KEY (to_id) REFERENCES nodes(id),
            UNIQUE(from_id, to_id, relation_type)
        )
    """)

    # edges 索引
    cur.execute("CREATE INDEX IF NOT EXISTS idx_edges_from ON edges(from_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_edges_to ON edges(to_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_edges_type ON edges(relation_type)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_edges_status ON edges(status)")

    cur.execute("CREATE INDEX IF NOT EXISTS idx_nodes_principle ON nodes(principle)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_nodes_task_type ON nodes(task_type)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_nodes_tier ON nodes(tier)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_nodes_vector ON nodes(vector) WHERE vector IS NOT NULL")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS undo_log (
            id TEXT PRIMARY KEY,
            operation TEXT NOT NULL,
            target_type TEXT NOT NULL,
            target_id TEXT NOT NULL,
            before_data TEXT NOT NULL,
            after_data TEXT,
            created_at TEXT NOT NULL
        )
    """)

    # ── FTS5 全文索引（外部内容表模式） ──
    # 使用 content=nodes 让 FTS5 从 nodes 表读取数据
    cur.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS fts_nodes USING fts5(
            id UNINDEXED,
            content,
            principle,
            tags,
            content='nodes',
            content_rowid='rowid'
        )
    """)

    # FTS5 同步触发器：插入
    cur.execute("""
        CREATE TRIGGER IF NOT EXISTS nodes_ai AFTER INSERT ON nodes BEGIN
            INSERT INTO fts_nodes(rowid, id, content, principle, tags)
            VALUES (new.rowid, new.id, new.content, new.principle, new.tags);
        END
    """)

    # FTS5 同步触发器：删除
    cur.execute("""
        CREATE TRIGGER IF NOT EXISTS nodes_ad AFTER DELETE ON nodes BEGIN
            INSERT INTO fts_nodes(fts_nodes, rowid, id, content, principle, tags)
            VALUES ('delete', old.rowid, old.id, old.content, old.principle, old.tags);
        END
    """)

    # FTS5 同步触发器：更新（先删旧再插新）
    cur.execute("""
        CREATE TRIGGER IF NOT EXISTS nodes_au AFTER UPDATE ON nodes BEGIN
            INSERT INTO fts_nodes(fts_nodes, rowid, id, content, principle, tags)
            VALUES ('delete', old.rowid, old.id, old.content, old.principle, old.tags);
            INSERT INTO fts_nodes(rowid, id, content, principle, tags)
            VALUES (new.rowid, new.id, new.content, new.principle, new.tags);
        END
    """)

    # ── meta 表 ──
    cur.execute("""
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    # meta 初始数据（INSERT OR IGNORE 保证重复运行安全）
    meta_defaults = [
        ('version', '5.0.0'),
        ('embedding_model', 'microsoft/harrier-oss-v1-0.6b'),
        ('embedding_dims', '1024'),
        ('last_dream', ''),
        ('total_nodes', '0'),
        ('total_edges', '0'),
    ]
    for key, value in meta_defaults:
        cur.execute("INSERT OR IGNORE INTO meta(key, value) VALUES (?, ?)", (key, value))

    conn.commit()
    conn.close()
    print(f"[graph_init] 数据库已创建: {path}")


if __name__ == "__main__":
    init_db()

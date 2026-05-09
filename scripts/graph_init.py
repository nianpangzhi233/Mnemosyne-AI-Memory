#!/usr/bin/env python3
"""Mnemosyne v6.0 — 建库建表脚本

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
            metadata TEXT,
            abstract TEXT,
            overview TEXT,
            confidence REAL DEFAULT 1.0,
            verified_at TEXT,
            verified_count INTEGER DEFAULT 0,
            half_life_days REAL DEFAULT 30.0,
            precondition TEXT,
            predicted_outcome TEXT,
            context_tags TEXT DEFAULT '[]',
            precondition_vec BLOB
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
            graph_dim TEXT DEFAULT 'semantic',
            strength TEXT DEFAULT 'strong',
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

    # ── v7.0 Skill artifacts ──
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

            latest_darwin_score REAL,
            latest_mnemosyne_score REAL,
            latest_live_test_delta REAL,
            latest_eval_mode TEXT,
            latest_decision TEXT,
            latest_decision_reason TEXT,

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
        ('version', '6.0.0'),
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

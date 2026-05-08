#!/usr/bin/env python3
"""Mnemosyne v5.0 → v6.0 迁移脚本

流程：备份 → ALTER TABLE → 智能回填 → 验证 → 更新 meta
幂等：重复执行不报错、不重复操作。

nodes 新增 8 字段：
  confidence, verified_at, verified_count, half_life_days,
  precondition, predicted_outcome, context_tags, precondition_vec

edges 新增 2 字段：
  graph_dim, strength
"""

import json
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "graph.db"
META_PATH = Path(__file__).resolve().parent.parent / "meta.json"

HALF_LIFE_BY_TYPE = {
    "experience": 30.0,
    "principle": 90.0,
    "strategy": 60.0,
    "correction": 60.0,
    "raw": 15.0,
}

NODES_NEW_COLS = [
    ("confidence", "REAL DEFAULT 1.0"),
    ("verified_at", "TEXT"),
    ("verified_count", "INTEGER DEFAULT 0"),
    ("half_life_days", "REAL DEFAULT 30.0"),
    ("precondition", "TEXT"),
    ("predicted_outcome", "TEXT"),
    ("context_tags", "TEXT DEFAULT '[]'"),
    ("precondition_vec", "BLOB"),
]

EDGES_NEW_COLS = [
    ("graph_dim", "TEXT DEFAULT 'semantic'"),
    ("strength", "TEXT DEFAULT 'strong'"),
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_existing_cols(cur, table: str) -> set:
    return {r[1] for r in cur.execute(f"PRAGMA table_info({table})").fetchall()}


def step1_backup(db_path: str):
    backup_path = db_path + f".v50.bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(db_path, backup_path)
    size_kb = Path(backup_path).stat().st_size / 1024
    print(f"[step1] 备份完成: {backup_path} ({size_kb:.0f} KB)")
    return backup_path


def step2_alter(db_path: str):
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        nodes_cols = _get_existing_cols(cur, "nodes")
        edges_cols = _get_existing_cols(cur, "edges")

        nodes_added = []
        for col_name, col_def in NODES_NEW_COLS:
            if col_name not in nodes_cols:
                cur.execute(f"ALTER TABLE nodes ADD COLUMN {col_name} {col_def}")
                nodes_added.append(col_name)

        edges_added = []
        for col_name, col_def in EDGES_NEW_COLS:
            if col_name not in edges_cols:
                cur.execute(f"ALTER TABLE edges ADD COLUMN {col_name} {col_def}")
                edges_added.append(col_name)

        conn.commit()

        if not nodes_added and not edges_added:
            print("[step2] 所有字段已存在，跳过 ALTER TABLE")
        else:
            if nodes_added:
                print(f"[step2] nodes 新增: {', '.join(nodes_added)}")
            if edges_added:
                print(f"[step2] edges 新增: {', '.join(edges_added)}")
        return nodes_added, edges_added
    finally:
        conn.close()


def step3_backfill(db_path: str):
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()

        migrated = cur.execute(
            "SELECT value FROM meta WHERE key='migrated_v60'"
        ).fetchone()
        if migrated and migrated[0] == "done":
            print("[step3] 已标记完成，跳过回填")
            return 0

        rows = cur.execute(
            "SELECT id, type, decay_score, access_count, task_type, project, tags FROM nodes"
        ).fetchall()

        if not rows:
            print("[step3] 无需回填")
            return 0

        count = 0
        for node_id, ntype, decay_score, access_count, task_type, project, tags_str in rows:
            confidence = round(min(1.0, max(0.1, decay_score if decay_score else 0.8)), 2)
            verified_count = max(0, (access_count or 0) // 3)
            half_life = HALF_LIFE_BY_TYPE.get(ntype, 30.0)

            _auto_tags = [t for t in [task_type, project] if t]
            try:
                existing_tags = json.loads(tags_str) if tags_str and tags_str != "[]" else []
            except (json.JSONDecodeError, TypeError):
                existing_tags = []
            merged_tags = list(set(_auto_tags + existing_tags))
            context_tags = json.dumps(merged_tags, ensure_ascii=False) if merged_tags else "[]"

            cur.execute(
                "UPDATE nodes SET confidence=?, verified_count=?, half_life_days=?, context_tags=? "
                "WHERE id=?",
                (confidence, verified_count, half_life, context_tags, node_id),
            )
            if cur.rowcount > 0:
                count += 1

        conn.commit()
        cur.execute(
            "INSERT OR REPLACE INTO meta(key, value) VALUES('migrated_v60', 'done')"
        )
        conn.commit()
        print(f"[step3] 回填 {count} 个节点（confidence/verified_count/half_life/context_tags）")
        return count
    finally:
        conn.close()


EDGE_DIM_MAP = {
    "similar_to": "semantic",
    "is_a": "semantic",
    "evolved_from": "semantic",
    "caused": "causal",
    "solves": "causal",
    "contradicts": "causal",
    "transfers_to": "entity",
}


def step3b_backfill_edges(db_path: str):
    """v6.1: Backfill graph_dim and strength from relation_type and weight"""
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()

        migrated = cur.execute(
            "SELECT value FROM meta WHERE key='migrated_v61_edges'"
        ).fetchone()
        if migrated and migrated[0] == "done":
            print("[step3b] 边维度已回填，跳过")
            return 0

        # Backfill graph_dim
        for rt, dim in EDGE_DIM_MAP.items():
            cur.execute(
                "UPDATE edges SET graph_dim=? WHERE relation_type=? AND graph_dim='semantic'",
                (dim, rt)
            )

        # Backfill strength
        cur.execute("UPDATE edges SET strength='strong' WHERE weight >= 0.6 AND strength='strong'")
        cur.execute("UPDATE edges SET strength='weak' WHERE weight < 0.6 AND strength='strong'")

        total = cur.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
        dim_counts = cur.execute(
            "SELECT graph_dim, COUNT(*) FROM edges GROUP BY graph_dim"
        ).fetchall()
        strength_counts = cur.execute(
            "SELECT strength, COUNT(*) FROM edges GROUP BY strength"
        ).fetchall()

        cur.execute(
            "INSERT OR REPLACE INTO meta(key, value) VALUES('migrated_v61_edges', 'done')"
        )
        conn.commit()

        print(f"[step3b] 边维度回填完成: {total} 条边")
        print(f"  graph_dim 分布: {dict(dim_counts)}")
        print(f"  strength 分布: {dict(strength_counts)}")
        return total
    finally:
        conn.close()

def step4_verify(db_path: str):
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()

        total = cur.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        with_confidence = cur.execute(
            "SELECT COUNT(*) FROM nodes WHERE confidence IS NOT NULL"
        ).fetchone()[0]
        with_half_life = cur.execute(
            "SELECT COUNT(*) FROM nodes WHERE half_life_days IS NOT NULL"
        ).fetchone()[0]
        with_context_tags = cur.execute(
            "SELECT COUNT(*) FROM nodes WHERE context_tags IS NOT NULL"
        ).fetchone()[0]

        total_edges = cur.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
        with_dim = cur.execute(
            "SELECT COUNT(*) FROM edges WHERE graph_dim IS NOT NULL"
        ).fetchone()[0]
        with_strength = cur.execute(
            "SELECT COUNT(*) FROM edges WHERE strength IS NOT NULL"
        ).fetchone()[0]

        nodes_cols = _get_existing_cols(cur, "nodes")
        edges_cols = _get_existing_cols(cur, "edges")

        expected_node_cols = {c[0] for c in NODES_NEW_COLS}
        expected_edge_cols = {c[0] for c in EDGES_NEW_COLS}

        missing_nodes = expected_node_cols - nodes_cols
        missing_edges = expected_edge_cols - edges_cols

        print(f"[step4] 验证结果:")
        print(f"  nodes: {total} 总计")
        print(f"    confidence: {with_confidence}/{total} ({with_confidence/total*100:.0f}%)")
        print(f"    half_life_days: {with_half_life}/{total} ({with_half_life/total*100:.0f}%)")
        print(f"    context_tags: {with_context_tags}/{total} ({with_context_tags/total*100:.0f}%)")
        print(f"  edges: {total_edges} 总计")
        print(f"    graph_dim: {with_dim}/{total_edges} ({with_dim/total_edges*100:.0f}%)")
        print(f"    strength: {with_strength}/{total_edges} ({with_strength/total_edges*100:.0f}%)")

        if missing_nodes:
            print(f"  [WARN] nodes 缺少字段: {missing_nodes}")
            return False
        if missing_edges:
            print(f"  [WARN] edges 缺少字段: {missing_edges}")
            return False

        if with_confidence != total:
            print(f"  [WARN] confidence 覆盖不完整")
            return False

        print(f"  [OK] 验证通过")
        return True
    finally:
        conn.close()


def step5_update_meta(db_path: str):
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("UPDATE meta SET value='6.0.0' WHERE key='version'")
        if cur.rowcount == 0:
            cur.execute("INSERT INTO meta(key, value) VALUES('version', '6.0.0')")
        conn.commit()
        ver = cur.execute("SELECT value FROM meta WHERE key='version'").fetchone()[0]
        print(f"[step5] meta 表 version → {ver}")
    finally:
        conn.close()

    if META_PATH.exists():
        with open(META_PATH, "r", encoding="utf-8") as f:
            meta = json.load(f)
        meta["version"] = "6.0.0"
        with open(META_PATH, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)
        print(f"[step5] meta.json version → 6.0.0")


def migrate(db_path: str = None):
    path = db_path or str(DB_PATH)

    if not Path(path).exists():
        print(f"[error] 数据库不存在: {path}")
        sys.exit(1)

    print(f"=== Mnemosyne v5.0 → v6.0 迁移 ===")
    print(f"数据库: {path}")

    backup_path = step1_backup(path)
    step2_alter(path)
    step3_backfill(path)
    ok = step4_verify(path)
    step5_update_meta(path)

    if ok:
        print(f"\n[OK] 迁移完成")
    else:
        print(f"\n[WARN] 迁移完成但有警告，请检查")
        print(f"备份文件: {backup_path}")


if __name__ == "__main__":
    migrate()

#!/usr/bin/env python3
"""Mnemosyne v4.1 — 写入节点+向量+实时边

通过 core 模块操作：
- SQLiteStore.add_node → 写节点 + Harrier 向量 + is_a 自动建边
- SQLiteStore.add_edge → 写 contradicts 等手动边
"""

import argparse
import json
import sys

from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

from core.utils import fix_windows_encoding, ensure_hf_offline

fix_windows_encoding()
ensure_hf_offline()

from core import SQLiteStore, HarrierEmbedder

_store = None


def _get_store() -> SQLiteStore:
    global _store
    if _store is None:
        _store = SQLiteStore(embedder=HarrierEmbedder())
    return _store


def write_node(content: str, node_type: str = "experience",
               task_type: str = None, project: str = None,
               tags: list = None, principle: str = None,
               db_path: str = None) -> str:
    store = _get_store()
    return store.add_node(
        content=content, node_type=node_type,
        task_type=task_type, project=project,
        tags=tags, principle=principle,
    )


def write_edge(from_id: str, to_id: str, relation_type: str,
               weight: float = 0.5, source: str = "auto",
               db_path: str = None) -> str:
    store = _get_store()
    return store.add_edge(
        from_id=from_id, to_id=to_id,
        relation_type=relation_type, weight=weight, source=source,
    )


def touch_node(node_id: str, db_path: str = None):
    store = _get_store()
    conn = store._connect()
    try:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "UPDATE nodes SET access_count = access_count + 1, "
            "last_access = ?, updated_at = ? WHERE id = ?",
            (now, now, node_id),
        )
        conn.commit()
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="写入经验节点")
    parser.add_argument("--content", required=True, help="经验文本")
    parser.add_argument("--type", default="experience", help="节点类型")
    parser.add_argument("--task-type", default=None, help="任务类型")
    parser.add_argument("--project", default=None, help="项目名")
    parser.add_argument("--tags", default=None, help="JSON array of tags")
    parser.add_argument("--principle", default=None, help="抽象原理")
    parser.add_argument("--contradicts", default=None, help="被纠正的节点ID")
    args = parser.parse_args()

    tags = json.loads(args.tags) if args.tags else []
    node_id = write_node(args.content, args.type, args.task_type,
                         args.project, tags, args.principle)

    print(f"[graph_write] 节点已写入: {node_id}")

    if args.principle:
        print(f"[graph_write] principle 已记录: {args.principle}")

    if args.contradicts:
        edge_id = write_edge(node_id, args.contradicts, "contradicts",
                             weight=0.8, source="auto")
        if edge_id:
            print(f"[graph_write] contradicts 边已建: {node_id[:8]} → {args.contradicts[:8]}")
        else:
            print(f"[graph_write] contradicts 边已存在，跳过")


if __name__ == "__main__":
    main()

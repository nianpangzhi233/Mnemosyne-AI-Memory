#!/usr/bin/env python3
"""Mnemosyne v4.1 — 图谱清洗与健康报告

人脑的遗忘和整理机制：
- 清洗：删除垃圾数据（孤立节点、模板骨架、完全重复）
- 合并：近重复节点合并强化
- 报告：健康度一目了然

用法：
    python scripts/graph_audit.py                # 健康报告
    python scripts/graph_audit.py --clean         # 清洗（预览不执行）
    python scripts/graph_audit.py --clean --force # 清洗并执行
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from core.utils import fix_windows_encoding, ensure_hf_offline

fix_windows_encoding()
ensure_hf_offline()

import sqlite3
import numpy as np

DB_PATH = Path(__file__).resolve().parent.parent / "graph.db"

TEMPLATE_PREFIXES = ["因果前件:", "因果后件:", "因果策略:", "概念迁移:"]


def get_conn():
    return sqlite3.connect(str(DB_PATH))


def report():
    conn = get_conn()
    c = conn.cursor()

    c.execute("SELECT type, COUNT(*) FROM nodes GROUP BY type")
    type_dist = dict(c.fetchall())
    total_nodes = sum(type_dist.values())

    c.execute("SELECT relation_type, source, COUNT(*) FROM edges WHERE status='active' GROUP BY relation_type, source ORDER BY COUNT(*) DESC")
    edge_dist = c.fetchall()
    total_edges = sum(r[2] for r in edge_dist)

    c.execute("SELECT COUNT(*) FROM edges WHERE status='vetoed'")
    vetoed = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM nodes n WHERE NOT EXISTS (SELECT 1 FROM edges e WHERE (e.from_id=n.id OR e.to_id=n.id) AND e.status='active')")
    orphans = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM nodes WHERE vector IS NULL")
    no_vector = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM nodes WHERE content LIKE '因果前件:%' OR content LIKE '因果后件:%' OR content LIKE '概念迁移:%' OR content LIKE '因果策略:%'")
    templates = c.fetchone()[0]

    c.execute("SELECT value FROM meta WHERE key='embedding_model'")
    model = c.fetchone()
    model_name = model[0] if model else "unknown"

    c.execute("SELECT value FROM meta WHERE key='last_dream'")
    last_dream = c.fetchone()
    last_dream_str = last_dream[0] if last_dream and last_dream[0] else "never"

    conn.close()

    density = total_edges / max(1, total_nodes)
    health = "OK"
    issues = []
    if orphans > total_nodes * 0.3:
        health = "WARN"
        issues.append(f"孤立节点过多 ({orphans}/{total_nodes})")
    if templates > total_nodes * 0.3:
        health = "WARN"
        issues.append(f"模板化节点过多 ({templates})")
    if density > 100:
        health = "WARN"
        issues.append(f"边密度过高 ({density:.1f} edges/node)")
    if no_vector > 0:
        issues.append(f"{no_vector} 节点无向量")

    print(f"\n{'='*50}")
    print(f"  Mnemosyne 健康报告")
    print(f"{'='*50}")
    print(f"  状态: {health}")
    print(f"  模型: {model_name}")
    print(f"  上次做梦: {last_dream_str}")
    print(f"")
    print(f"  节点: {total_nodes} (有向量: {total_nodes - no_vector}, 无向量: {no_vector})")
    for t, cnt in sorted(type_dist.items(), key=lambda x: -x[1]):
        print(f"    {t}: {cnt}")
    print(f"")
    print(f"  边: {total_edges} (vetoed: {vetoed})")
    for rel, src, cnt in edge_dist:
        print(f"    {rel} ({src}): {cnt}")
    print(f"  密度: {density:.1f} edges/node")
    print(f"")
    print(f"  孤立节点: {orphans}")
    print(f"  模板化节点: {templates}")
    if issues:
        print(f"")
        for issue in issues:
            print(f"  ⚠️  {issue}")
    print(f"{'='*50}\n")

    return {"health": health, "orphans": orphans, "templates": templates}


def clean(force=False):
    print(f"\n{'='*50}")
    print(f"  图谱清洗 {'（执行模式）' if force else '（预览模式）'}")
    print(f"{'='*50}\n")

    conn = get_conn()
    c = conn.cursor()

    # 1. 清理模板化骨架节点
    like_clauses = " OR ".join([f"content LIKE '{p}%'" for p in TEMPLATE_PREFIXES])
    c.execute(f"SELECT id FROM nodes WHERE {like_clauses}")
    template_ids = [r[0] for r in c.fetchall()]
    if template_ids:
        print(f"  [1] 模板化节点: {len(template_ids)} 条")
        if force:
            placeholders = ",".join(["?"] * len(template_ids))
            c.execute(f"DELETE FROM edges WHERE from_id IN ({placeholders}) OR to_id IN ({placeholders})",
                      template_ids + template_ids)
            c.execute(f"DELETE FROM nodes WHERE id IN ({placeholders})", template_ids)
            conn.commit()
            print(f"      已删除")
        else:
            print(f"      预览：--force 执行删除")
    else:
        print(f"  [1] 模板化节点: 无")

    # 2. 清理孤立节点
    c.execute("""
        SELECT n.id FROM nodes n
        WHERE NOT EXISTS (
            SELECT 1 FROM edges e
            WHERE (e.from_id=n.id OR e.to_id=n.id) AND e.status='active'
        ) AND n.type != 'experience'
    """)
    orphan_ids = [r[0] for r in c.fetchall()]
    if orphan_ids:
        print(f"  [2] 孤立非经验节点: {len(orphan_ids)} 条")
        if force:
            placeholders = ",".join(["?"] * len(orphan_ids))
            c.execute(f"DELETE FROM edges WHERE from_id IN ({placeholders}) OR to_id IN ({placeholders})",
                      orphan_ids + orphan_ids)
            c.execute(f"DELETE FROM nodes WHERE id IN ({placeholders})", orphan_ids)
            conn.commit()
            print(f"      已删除")
        else:
            print(f"      预览：--force 执行删除")
    else:
        print(f"  [2] 孤立节点: 无")

    # 3. 合并完全重复（向量相似 > 0.98）
    c.execute("SELECT id, content, vector, base_score FROM nodes WHERE vector IS NOT NULL AND type='experience'")
    rows = c.fetchall()
    merge_count = 0
    seen = set()
    for i in range(len(rows)):
        if rows[i][0] in seen:
            continue
        va = np.frombuffer(rows[i][2], dtype=np.float32)
        for j in range(i + 1, len(rows)):
            if rows[j][0] in seen:
                continue
            vb = np.frombuffer(rows[j][2], dtype=np.float32)
            sim = float(np.dot(va, vb))
            if sim > 0.98:
                merge_count += 1
                seen.add(rows[j][0])
                if force:
                    stronger = rows[i][0] if rows[i][3] >= rows[j][3] else rows[j][0]
                    weaker = rows[j][0] if stronger == rows[i][0] else rows[i][0]
                    new_base = min(1.5, rows[i][3] + 0.1)
                    c.execute("UPDATE nodes SET base_score=? WHERE id=?", (new_base, stronger))
                    c.execute("UPDATE edges SET from_id=? WHERE from_id=?", (stronger, weaker))
                    c.execute("UPDATE edges SET to_id=? WHERE to_id=?", (stronger, weaker))
                    c.execute("DELETE FROM nodes WHERE id=?", (weaker,))
    if merge_count > 0:
        print(f"  [3] 完全重复: {merge_count} 对")
        if force:
            conn.commit()
            print(f"      已合并")
        else:
            print(f"      预览：--force 执行合并")
    else:
        print(f"  [3] 完全重复: 无")

    conn.close()
    print(f"\n{'='*50}\n")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="图谱清洗与健康报告")
    parser.add_argument("--clean", action="store_true", help="执行清洗")
    parser.add_argument("--force", action="store_true", help="真正执行（否则只预览）")
    args = parser.parse_args()

    if args.clean:
        clean(force=args.force)
    report()


if __name__ == "__main__":
    main()

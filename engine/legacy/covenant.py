#!/usr/bin/env python3
"""Memory Evolution v4.0 — 安全审核脚本

功能：
- 审核图谱中自动建立的边（source=dream 或 source=auto）
- 四条安全规则：
  1. 拒绝自环边（from=to）
  2. 拒绝低置信度边（weight < 0.3）
  3. 拒绝涉及用户隐私的边（含敏感关键词）
  4. 拒绝与失败模式冲突的策略（继承自 v3 covenant）

可独立运行，也可被 graph_dream.py Phase 6 调用。
"""

import argparse
import json
from pathlib import Path

import sqlite3

DB_PATH = Path(__file__).resolve().parent.parent / "graph.db"
COVENANT_PATH = Path(__file__).resolve().parent.parent / "engine" / "covenant.json"

# 隐私关键词（中英混合）
PRIVACY_KEYWORDS = [
    "密码", "密钥", "token", "secret", "password",
    "api_key", "私钥", "身份证", "手机号", "银行卡",
    "credential", "private_key",
]

# 失败模式关键词（从 v3 covenant 继承）
FAILURE_PATTERN_KEYWORDS = [
    "失败模式", "已否决", "冲突",
]


def check_self_loop(from_id: str, to_id: str) -> list:
    """规则1: 自环检测"""
    if from_id == to_id:
        return ["self_loop"]
    return []


def check_low_confidence(weight: float) -> list:
    """规则2: 低置信度检测"""
    if weight < 0.3:
        return [f"low_confidence({weight:.2f})"]
    return []


def check_privacy(from_content: str, to_content: str) -> list:
    """规则3: 隐私检测"""
    reasons = []
    for kw in PRIVACY_KEYWORDS:
        from_match = from_content and kw in from_content.lower()
        to_match = to_content and kw in to_content.lower()
        if from_match or to_match:
            reasons.append(f"privacy({kw})")
            break  # 只报告第一个匹配
    return reasons


def check_failure_pattern(from_content: str, to_content: str,
                          covenant_data: dict = None) -> list:
    """规则4: 失败模式冲突检测

    从 covenant.json 的 veto_queue 中提取失败模式关键词，
    检查边的节点内容是否与已知失败模式冲突。
    """
    if not covenant_data:
        return []

    reasons = []
    veto_queue = covenant_data.get("data", {}).get("veto_queue", {})
    for vid, veto in veto_queue.items():
        if veto.get("status") != "vetoed":
            continue
        action = veto.get("action", "")
        reason = veto.get("reason", "")
        # 如果节点内容包含被否决策略的关键部分
        if action and any(kw in action for kw in ["概念迁移"]):
            # 检查节点是否涉及被否决的概念迁移
            for content in [from_content, to_content]:
                if content and action.split(":")[-1].strip()[:20] in content:
                    reasons.append(f"conflicts_vetoed({vid[:8]})")
                    break

    return reasons


def audit_edges(source_filter: str = None, dry_run: bool = False):
    """审核所有自动建的边

    Args:
        source_filter: 只审核特定来源的边（dream/auto/migrate），None 表示全部
        dry_run: 只检测不执行 veto

    Returns:
        (vetoed_count, total_checked, veto_details)
    """
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    # 构建查询
    query = """
        SELECT e.id, e.from_id, e.to_id, e.weight, e.relation_type, e.source,
               nf.content AS from_content, nt.content AS to_content
        FROM edges e
        LEFT JOIN nodes nf ON e.from_id = nf.id
        LEFT JOIN nodes nt ON e.to_id = nt.id
        WHERE e.status = 'active'
    """
    params = []
    if source_filter:
        query += " AND e.source = ?"
        params.append(source_filter)

    cur.execute(query, params)
    edges = cur.fetchall()

    # 加载 covenant 数据
    covenant_data = None
    if COVENANT_PATH.exists():
        with open(COVENANT_PATH, "r", encoding="utf-8") as f:
            covenant_data = json.load(f)

    vetoed = 0
    veto_details = []

    for edge_id, from_id, to_id, weight, rel_type, source, from_content, to_content in edges:
        reasons = []

        # 规则1: 自环
        reasons.extend(check_self_loop(from_id, to_id))

        # 规则2: 低置信度
        reasons.extend(check_low_confidence(weight or 0.5))

        # 规则3: 隐私
        reasons.extend(check_privacy(from_content or "", to_content or ""))

        # 规则4: 失败模式冲突
        reasons.extend(check_failure_pattern(
            from_content or "", to_content or "", covenant_data))

        if reasons:
            if not dry_run:
                cur.execute("UPDATE edges SET status='vetoed' WHERE id=?", (edge_id,))
            vetoed += 1
            veto_details.append({
                "edge_id": edge_id,
                "relation": rel_type,
                "source": source,
                "reasons": reasons,
            })

    if not dry_run:
        conn.commit()
    conn.close()

    return vetoed, len(edges), veto_details


def show_audit_report(veto_details: list):
    """显示审核报告"""
    if not veto_details:
        print("  所有边通过审核")
        return

    print(f"  发现 {len(veto_details)} 条违规边:")
    for d in veto_details:
        reasons = ", ".join(d["reasons"])
        print(f"    {d['edge_id'][:8]}.. {d['relation']} ({d['source']}): {reasons}")


def main():
    parser = argparse.ArgumentParser(description="安全审核")
    parser.add_argument("--source", default=None,
                        help="只审核特定来源 (dream/auto/migrate)")
    parser.add_argument("--dry-run", action="store_true",
                        help="只检测不执行 veto")
    parser.add_argument("--full", action="store_true",
                        help="审核所有 active 边")
    args = parser.parse_args()

    source = args.source
    if args.full:
        source = None  # 审核全部

    print(f"[covenant] 审核模式: {'dry-run' if args.dry_run else 'live'}")
    print(f"[covenant] 审核范围: {source or '所有来源'}")

    vetoed, total, details = audit_edges(source_filter=source, dry_run=args.dry_run)
    print(f"[covenant] 检查 {total} 条边，否决 {vetoed} 条")
    show_audit_report(details)


if __name__ == "__main__":
    main()

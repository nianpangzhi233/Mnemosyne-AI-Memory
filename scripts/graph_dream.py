#!/usr/bin/env python3
"""Mnemosyne v7.0 — 做梦全流程（Fast/Slow 双流 + Skill Memory）

通过 core 模块操作：
- DreamPipeline + Fast/Slow 双流 Phase
- v6.1: ContradictsPhase 增量检测（diff + keyword + LLM）
- v6.1: SimilarToPhase 增量检测
- v6.1: VectorIndex 快速路由 + Creative is_a 零跳
- v7.0: SkillEmbryo/Development/MirrorEvolution phases
- SQLiteStore + HarrierEmbedder 注入
"""

import sys

from pathlib import Path

import sqlite3

SCRIPTS_DIR = Path(__file__).resolve().parent
DB_PATH = SCRIPTS_DIR.parent / "graph.db"

sys.path.insert(0, str(SCRIPTS_DIR))

from core.utils import fix_windows_encoding, ensure_hf_offline

fix_windows_encoding()
ensure_hf_offline()

from core import (
    SQLiteStore, HarrierEmbedder,
    run_dream, DreamPipeline,
    SimilarToPhase, CausalPhase, ContradictsPhase, TransfersPhase,
    SkillEmbryoPhase, SkillDevelopmentPhase, SkillMirrorEvolutionPhase,
    StrategyPhase, CovenantPhase, DecayPhase, SyncPhase,
)


def show_stats():
    store = SQLiteStore(embedder=HarrierEmbedder())
    conn = store._connect()
    try:
        cur = conn.cursor()
        stats = {}
        for query, key in [
            ("SELECT COUNT(*) FROM nodes", "总节点"),
            ("SELECT COUNT(*) FROM edges", "总边"),
            ("SELECT COUNT(*) FROM edges WHERE source='dream'", "做梦边"),
            ("SELECT COUNT(*) FROM nodes WHERE tier='hot'", "hot节点"),
            ("SELECT COUNT(*) FROM nodes WHERE tier='warm'", "warm节点"),
            ("SELECT COUNT(*) FROM nodes WHERE tier='cold'", "cold节点"),
            ("SELECT COUNT(*) FROM edges WHERE status='vetoed'", "已否决边"),
        ]:
            cur.execute(query)
            stats[key] = cur.fetchone()[0]

        cur.execute(
            "SELECT relation_type, COUNT(*) FROM edges "
            "WHERE status='active' GROUP BY relation_type"
        )
        rel_stats = {r[0]: r[1] for r in cur.fetchall()}
    finally:
        conn.close()

    print("=" * 40)
    print("图谱统计")
    print("=" * 40)
    for k, v in stats.items():
        print(f"  {k}: {v}")
    if rel_stats:
        print("  活跃边分布:")
        for rt, cnt in sorted(rel_stats.items(), key=lambda x: -x[1]):
            print(f"    {rt}: {cnt}")
    print("=" * 40)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="做梦全流程")
    parser.add_argument("--full", action="store_true", help="完整做梦（全部Phase）")
    parser.add_argument("--phase", type=int, help="只跑某个Phase")
    parser.add_argument("--stats", action="store_true", help="查看统计")
    parser.add_argument("--no-slow", action="store_true", help="Skip slow path (LLM phases)")
    args = parser.parse_args()

    if args.stats:
        show_stats()
        return

    store = SQLiteStore(embedder=HarrierEmbedder())
    embedder = store._embedder  # v6.1: reuse same embedder instance

    if args.phase:
        results = run_dream(store, embedder, phases=[args.phase])
        for r in results:
            print(f"  结果: {r['result']}")
        return

    if args.full:
        from datetime import datetime, timezone

        results = run_dream(store, embedder, slow=not args.no_slow)
        dream_finished_at = datetime.now(timezone.utc).isoformat()

        conn = sqlite3.connect(str(DB_PATH))
        conn.execute(
            "UPDATE meta SET value=? WHERE key='last_dream'",
            (dream_finished_at,),
        )
        conn.commit()
        conn.close()

        print("\n[Dream] 完成!")
        show_stats()
        return

    print("请指定 --full, --phase N, 或 --stats")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Mnemosyne v4.1 — 向量+FTS5+图谱遍历联合查询

通过 core 模块操作：
- SQLiteStore.search_by_vector → 向量相似度搜索
- SQLiteStore.search_by_keyword → FTS5 关键词搜索
- SQLiteStore.search_hybrid → 混合检索
- SQLiteStore.traverse → 图谱 BFS 遍历
"""

import argparse
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


def vector_search(query: str, top: int = 5, layer: str = "L2"):
    return _get_store().search_by_vector(query, top=top, layer=layer)


def keyword_search(query: str, top: int = 5, layer: str = "L2"):
    return _get_store().search_by_keyword(query, top=top, layer=layer)


def hybrid_search(query: str, top: int = 5, layer: str = "L2"):
    return _get_store().search_hybrid(query, top=top, layer=layer)


def traverse(node_id: str, depth: int = 2, max_results: int = 10,
             touch: bool = True):
    return _get_store().traverse(node_id, depth=depth, max_results=max_results)


def inject(context: str, max_chars: int = 500):
    store = _get_store()

    top_results = store.search_hybrid(context, top=5, layer="L2")
    spread_results = store.search_spreading(context, mode="creative", top=5, layer="L1")
    if not top_results:
        top_results = spread_results
    else:
        seen = {r["id"] for r in top_results}
        for item in spread_results:
            if item["id"] not in seen:
                top_results.append(item)
                seen.add(item["id"])

    if not top_results:
        return ""

    assoc_results = []
    for r in top_results[:3]:
        traversal = store.traverse(r["id"], depth=1, max_results=3)
        assoc_results.extend(traversal)

    lines = []
    total = 0
    for r in top_results:
        text = r.get("content") or r.get("overview") or r.get("abstract", "")
        line = f"- [{r['tier']}] {text}"
        if r.get("principle"):
            line += f" (原理: {r['principle']})"
        if total + len(line) > max_chars:
            break
        lines.append(line)
        total += len(line)

    if assoc_results and total < max_chars * 0.8:
        lines.append("")
        lines.append("联想:")
        for r in assoc_results[:5]:
            line = f"  {r['relation']} -> {r['content'][:60]}"
            if total + len(line) > max_chars:
                break
            lines.append(line)
            total += len(line)

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="联合查询")
    parser.add_argument("--vector-search", dest="vector_search", help="向量搜索")
    parser.add_argument("--keyword-search", dest="keyword_search", help="关键词搜索")
    parser.add_argument("--hybrid-search", dest="hybrid_search", help="混合搜索")
    parser.add_argument("--traverse", help="遍历节点ID")
    parser.add_argument("--inject", action="store_true", help="注入模式")
    parser.add_argument("--context", help="注入上下文")
    parser.add_argument("--top", type=int, default=5)
    parser.add_argument("--depth", type=int, default=2)
    parser.add_argument("--max-results", dest="max_results", type=int, default=10)
    parser.add_argument("--max-chars", dest="max_chars", type=int, default=500)
    parser.add_argument("--layer", choices=["L0", "L1", "L2"], default="L2",
                        help="Return granularity: L0=abstract, L1=overview, L2=full")
    parser.add_argument("--detail", help="Comma-separated node IDs to fetch full details")
    args = parser.parse_args()

    if args.detail:
        ids = [x.strip() for x in args.detail.split(",") if x.strip()]
        store = _get_store()
        for nid in ids:
            node = store.get_node(nid)
            if node:
                print(f"  [{node.get('tier')}] {node.get('content', '')[:80]}")
                if node.get("principle"):
                    print(f"    principle: {node['principle']}")
                print(f"    decay: {node.get('decay_score', 0):.3f} | project: {node.get('project')}")
            else:
                print(f"  {nid}: not found")
    elif args.vector_search:
        results = vector_search(args.vector_search, args.top, args.layer)
        if not results:
            print("  无匹配结果")
        for r in results:
            if args.layer == "L0":
                print(f"  [{r['similarity']:.3f}] [{r['tier']}] {r.get('abstract', '')[:80]}")
            elif args.layer == "L1":
                print(f"  [{r['similarity']:.3f}] [{r['tier']}] {r.get('abstract', '')[:80]}")
                if r.get("principle"):
                    print(f"    principle: {r['principle']}")
            else:
                print(f"  [{r['similarity']:.3f}/{r['score']:.3f}] [{r['tier']}] {r['content'][:60]}")

    elif args.keyword_search:
        results = keyword_search(args.keyword_search, args.top, args.layer)
        if not results:
            print("  无匹配结果")
        for r in results:
            if args.layer == "L0":
                print(f"  [{r['tier']}] {r.get('abstract', '')[:80]}")
            elif args.layer == "L1":
                print(f"  [{r['tier']}] {r.get('abstract', '')[:80]}")
                if r.get("principle"):
                    print(f"    principle: {r['principle']}")
            else:
                print(f"  [{r['tier']}] {r['content'][:60]}")

    elif args.hybrid_search:
        results = hybrid_search(args.hybrid_search, args.top, args.layer)
        if not results:
            print("  无匹配结果")
        for r in results:
            if args.layer == "L0":
                print(f"  [{r.get('score',0):.3f}] [{r['tier']}] {r.get('abstract', '')[:80]}")
            elif args.layer == "L1":
                print(f"  [{r.get('score',0):.3f}] [{r['tier']}] {r.get('abstract', '')[:80]}")
                if r.get("principle"):
                    print(f"    principle: {r['principle']}")
            else:
                print(f"  [{r.get('score',0):.3f}] [{r['tier']}] {r['content'][:60]}")

    elif args.traverse:
        results = traverse(args.traverse, args.depth, args.max_results)
        if not results:
            print("  无关联节点")
        for r in results:
            direction = "→" if r["direction"] == "outgoing" else "←"
            print(f"  {r['from'][:8]}.. {direction} {r['relation']} {direction} {r['content'][:40]}")

    elif args.inject and args.context:
        output = inject(args.context, args.max_chars)
        print(output if output else "无匹配经验")


if __name__ == "__main__":
    main()

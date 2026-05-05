#!/usr/bin/env python3
"""Dream Pipeline — 做梦流程插件化框架

v4.1 将 graph_dream.py 的 8 个 Phase 重构为独立插件类：
  每个 Phase 继承 DreamPhase，只通过 AbstractGraphStore 接口操作数据，
  不直接访问 SQL / _connect()。

原 graph_dream.py 保持不动（向后兼容），新代码全部在此模块。
"""

import json
import math
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from .graph_store import AbstractGraphStore
from .embedder import AbstractEmbedder

TYPE_WEIGHTS = {
    "experience": 1.0, "principle": 1.3, "strategy": 1.0,
    "correction": 1.2,
}

_PROPOSALS_PATH = Path(__file__).resolve().parent.parent.parent / "proposals" / "pending.md"
_HOT_MEMORY_PATH = Path(__file__).resolve().parent.parent.parent / "hot" / "memory.md"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _days_since(iso_str: str) -> float:
    if not iso_str:
        return 0
    dt = datetime.fromisoformat(iso_str)
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return max(0, (now - dt).total_seconds() / 86400)


class DreamPhase(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def run(self, store: AbstractGraphStore, embedder: AbstractEmbedder) -> dict: ...


class DreamPipeline:
    def __init__(self):
        self._phases: List[DreamPhase] = []

    def register(self, phase: DreamPhase) -> "DreamPipeline":
        self._phases.append(phase)
        return self

    def execute(self, store: AbstractGraphStore, embedder: AbstractEmbedder) -> List[Dict[str, Any]]:
        results = []
        for i, phase in enumerate(self._phases, 1):
            print(f"[Phase {i}] {phase.name}")
            result = phase.run(store, embedder)
            print(f"  结果: {result}")
            results.append({"phase": i, "name": phase.name, "result": result})
        return results


class SimilarToPhase(DreamPhase):
    @property
    def name(self) -> str:
        return "向量扫描 similar_to"

    def run(self, store: AbstractGraphStore, embedder: AbstractEmbedder) -> dict:
        nodes = store.bulk_get_vectors()
        nodes = [n for n in nodes if n.get("task_type") is not None]
        if len(nodes) < 2:
            return {"added": 0}

        existing = store.bulk_get_edge_pairs("similar_to")

        edges_to_add = []
        for i in range(len(nodes)):
            va = np.frombuffer(nodes[i]["vector"], dtype=np.float32)
            for j in range(i + 1, len(nodes)):
                vb = np.frombuffer(nodes[j]["vector"], dtype=np.float32)
                sim = float(np.dot(va, vb))
                if sim > 0.85 and (nodes[i]["id"], nodes[j]["id"]) not in existing:
                    edges_to_add.append({
                        "from_id": nodes[i]["id"],
                        "to_id": nodes[j]["id"],
                        "relation_type": "similar_to",
                        "weight": round(sim, 3),
                        "source": "dream",
                    })

        added = store.bulk_add_edges(edges_to_add)
        return {"added": added}


class CausalPhase(DreamPhase):
    @property
    def name(self) -> str:
        return "因果检测 caused/solves"

    def run(self, store: AbstractGraphStore, embedder: AbstractEmbedder) -> dict:
        by_task = store.bulk_get_nodes_by_task()

        edges_to_add = []
        for items in by_task.values():
            for i in range(len(items) - 1):
                curr, nxt = items[i], items[i + 1]
                if curr.get("result") == "failure" and nxt.get("result") == "success":
                    edges_to_add.append({
                        "from_id": curr["id"], "to_id": nxt["id"],
                        "relation_type": "caused", "weight": 0.6, "source": "dream",
                    })
                    edges_to_add.append({
                        "from_id": nxt["id"], "to_id": curr["id"],
                        "relation_type": "solves", "weight": 0.6, "source": "dream",
                    })

        added = store.bulk_add_edges(edges_to_add)
        return {"added": added}


class ContradictsPhase(DreamPhase):
    OPPOSITE_PAIRS = [
        ("失败", "成功"), ("错误", "正确"), ("问题", "解决"),
        ("慢", "快"), ("崩溃", "稳定"), ("不能用", "能用"),
        ("不支持", "支持"), ("不要", "要"), ("不能", "能"),
    ]

    @property
    def name(self) -> str:
        return "冲突检测 contradicts"

    def run(self, store: AbstractGraphStore, embedder: AbstractEmbedder) -> dict:
        nodes = store.bulk_get_vectors()
        existing = store.bulk_get_edge_pairs("contradicts")

        by_task: Dict[str, list] = {}
        for n in nodes:
            by_task.setdefault(n.get("task_type") or "general", []).append(n)

        edges_to_add = []
        for items in by_task.values():
            for i in range(len(items)):
                for j in range(i + 1, len(items)):
                    a, b = items[i], items[j]
                    if (a["id"], b["id"]) in existing:
                        continue
                    va = np.frombuffer(a["vector"], dtype=np.float32)
                    vb = np.frombuffer(b["vector"], dtype=np.float32)
                    sim = float(np.dot(va, vb))
                    if sim > 0.6 and self._is_contradict(a["content"], b["content"]):
                        edges_to_add.append({
                            "from_id": a["id"], "to_id": b["id"],
                            "relation_type": "contradicts", "weight": 0.7, "source": "dream",
                        })

        added = store.bulk_add_edges(edges_to_add)
        return {"added": added}

    @staticmethod
    def _is_contradict(text_a: str, text_b: str) -> bool:
        for w1, w2 in ContradictsPhase.OPPOSITE_PAIRS:
            if (w1 in text_a and w2 in text_b) or (w2 in text_a and w1 in text_b):
                return True
        return False


class TransfersPhase(DreamPhase):
    @property
    def name(self) -> str:
        return "跨域迁移 transfers_to"

    def run(self, store: AbstractGraphStore, embedder: AbstractEmbedder) -> dict:
        existing = store.bulk_get_edge_pairs("transfers_to")

        is_a_edges = store.query_edges("relation_type='is_a' AND status='active'")
        principle_groups: Dict[str, list] = {}
        for e in is_a_edges:
            principle_groups.setdefault(e["to_id"], []).append(e["from_id"])

        edges_to_add = []
        for principle_id, node_ids in principle_groups.items():
            nodes = []
            for nid in node_ids:
                n = store.get_node(nid)
                if n:
                    nodes.append(n)
            for i in range(len(nodes)):
                for j in range(i + 1, len(nodes)):
                    if nodes[i].get("task_type") != nodes[j].get("task_type"):
                        pair = (nodes[i]["id"], nodes[j]["id"])
                        if pair not in existing:
                            edges_to_add.append({
                                "from_id": nodes[i]["id"], "to_id": nodes[j]["id"],
                                "relation_type": "transfers_to", "weight": 0.5, "source": "dream",
                            })

        added = store.bulk_add_edges(edges_to_add)
        return {"added": added}


class StrategyPhase(DreamPhase):
    @property
    def name(self) -> str:
        return "策略生成"

    def run(self, store: AbstractGraphStore, embedder: AbstractEmbedder) -> dict:
        similar_edges = store.query_edges(
            "relation_type='similar_to' AND source='dream' AND status='active'"
        )

        strategy_nodes = store.query_nodes("type='strategy'")
        strategy_ids = {n["id"] for n in strategy_nodes}

        hub_count: Dict[str, int] = {}
        for e in similar_edges:
            if e["from_id"] in strategy_ids or e["to_id"] in strategy_ids:
                continue
            hub_count[e["from_id"]] = hub_count.get(e["from_id"], 0) + 1
            hub_count[e["to_id"]] = hub_count.get(e["to_id"], 0) + 1

        hubs = {nid for nid, cnt in hub_count.items() if cnt >= 2}

        strategies = []
        edges_to_add = []
        for hub_id in hubs:
            hub = store.get_node(hub_id)
            if not hub:
                continue
            if not hub.get("principle"):
                continue

            strategy_content = hub["principle"]
            existing = [s for s in strategy_nodes if s["content"] == strategy_content]
            if existing:
                continue

            vec = embedder.encode(strategy_content)
            vec_blob = vec.astype(np.float32).tobytes()

            strategy_id = store.add_raw_node(
                type="strategy",
                content=strategy_content,
                vector=vec_blob,
                task_type=hub.get("task_type"),
                tags="[]",
            )

            edges_to_add.append({
                "from_id": strategy_id, "to_id": hub_id,
                "relation_type": "evolved_from", "weight": 0.8, "source": "dream",
            })
            strategies.append({"id": strategy_id, "content": strategy_content, "from": hub_id})

        store.bulk_add_edges(edges_to_add)

        if strategies:
            _PROPOSALS_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(_PROPOSALS_PATH, "w", encoding="utf-8") as f:
                f.write("# 待审核策略\n\n> 由做梦 Phase 5 自动生成，需人工审核\n\n")
                for s in strategies:
                    f.write(f"- **{s['content'][:60]}**\n")
                    f.write(f"  - ID: `{s['id']}`\n")
                    f.write(f"  - 来源节点: `{s['from']}`\n\n")

        return {"added": len(strategies)}


class CovenantPhase(DreamPhase):
    PRIVACY_KEYWORDS = [
        "密码", "密钥", "token", "secret", "password", "api_key", "私钥",
        "身份证", "手机号", "银行卡", "credential", "private_key",
    ]

    @property
    def name(self) -> str:
        return "covenant 审核"

    def run(self, store: AbstractGraphStore, embedder: AbstractEmbedder) -> dict:
        dream_edges = store.query_edges("source='dream' AND status='active'")

        veto_ids = []
        for e in dream_edges:
            if e["from_id"] == e["to_id"]:
                veto_ids.append(e["id"])
                continue
            if e["weight"] < 0.3:
                veto_ids.append(e["id"])
                continue
            from_node = store.get_node(e["from_id"])
            to_node = store.get_node(e["to_id"])
            from_c = (from_node or {}).get("content", "") or ""
            to_c = (to_node or {}).get("content", "") or ""
            for kw in self.PRIVACY_KEYWORDS:
                if kw in from_c.lower() or kw in to_c.lower():
                    veto_ids.append(e["id"])
                    break

        vetoed = store.veto_edges(veto_ids)
        return {"checked": len(dream_edges), "vetoed": vetoed}


class DecayPhase(DreamPhase):
    @property
    def name(self) -> str:
        return "衰减重算"

    def run(self, store: AbstractGraphStore, embedder: AbstractEmbedder) -> dict:
        all_nodes = store.query_nodes()
        updates = []
        for n in all_nodes:
            days = _days_since(n.get("last_access") or "")
            tw = TYPE_WEIGHTS.get(n.get("type", "experience"), 1.0)
            access = n.get("access_count", 0)
            base = n.get("base_score", 0.8)
            new_decay = base * math.exp(-0.03 * days) * math.log2(access + 2) * tw
            new_decay = min(2.0, max(0.0, new_decay))
            if new_decay < 0.05:
                new_tier = "cold"
            elif new_decay < 0.2:
                new_tier = "warm"
            else:
                new_tier = "hot"
            if new_tier != n.get("tier") or abs(new_decay - (n.get("decay_score") or 0)) > 0.001:
                updates.append({"id": n["id"], "decay_score": round(new_decay, 4), "tier": new_tier})

        updated = store.bulk_update_decay(updates)
        return {"updated": updated}


class SyncPhase(DreamPhase):
    @property
    def name(self) -> str:
        return "memory.md 同步"

    def run(self, store: AbstractGraphStore, embedder: AbstractEmbedder) -> dict:
        rows = store.get_top_hot_nodes(limit=50)

        lines = ["# 活跃记忆", "", f"> 自动生成于 {_now_iso()}，共 {len(rows)} 条", ""]

        by_task: Dict[str, list] = {}
        for r in rows:
            key = r.get("task_type") or "general"
            by_task.setdefault(key, []).append(r)

        for task, items in by_task.items():
            lines.append(f"## {task}")
            for r in items:
                prefix = f"[{r['decay_score']:.2f}]"
                if r.get("principle"):
                    lines.append(f"- {prefix} {r['content'][:80]} (原理: {r['principle']})")
                else:
                    lines.append(f"- {prefix} {r['content'][:80]}")
            lines.append("")

        if len(lines) > 150:
            lines = lines[:149] + ["... (截断)"]

        _HOT_MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_HOT_MEMORY_PATH, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        return {"synced": len(rows)}


class LLMReviewPhase(DreamPhase):
    @property
    def name(self) -> str:
        return "LLM 深度审查（REM）"

    def run(self, store: AbstractGraphStore, embedder: AbstractEmbedder) -> dict:
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from llm_judge import run_llm_review
        return run_llm_review(store, embedder, {})


class SnapshotPhase(DreamPhase):
    @property
    def name(self) -> str:
        return "预检快照"

    def run(self, store: AbstractGraphStore, embedder: AbstractEmbedder) -> dict:
        nodes = store.count_nodes()
        edges = store.count_edges()
        return {"nodes_before": nodes, "edges_before": edges,
                "node_cap": max(200, int(nodes * 1.5)),
                "edge_cap": max(500, int(edges * 2))}


class AuditPhase(DreamPhase):
    def __init__(self):
        self._snapshot = {}

    def set_snapshot(self, snapshot: dict):
        self._snapshot = snapshot

    @property
    def name(self) -> str:
        return "后审计"

    def run(self, store: AbstractGraphStore, embedder: AbstractEmbedder) -> dict:
        nodes = store.count_nodes()
        edges = store.count_edges()
        snap = self._snapshot

        alerts = []
        node_cap = snap.get("node_cap", 9999)
        edge_cap = snap.get("edge_cap", 9999)
        if nodes > node_cap:
            alerts.append(f"节点膨胀超限: {nodes} > {node_cap}")
        if edges > edge_cap:
            alerts.append(f"边膨胀超限: {edges} > {edge_cap}")

        strategy_count = store.count_nodes_where("type='strategy'")
        if strategy_count > nodes * 0.5:
            alerts.append(f"策略节点占比过高: {strategy_count}/{nodes}")

        return {"nodes_after": nodes, "edges_after": edges,
                "alerts": alerts, "status": "PASS" if not alerts else "WARN"}


_ALL_PHASES = [
    SnapshotPhase, SimilarToPhase, CausalPhase, ContradictsPhase, TransfersPhase,
    StrategyPhase, CovenantPhase, DecayPhase, LLMReviewPhase, SyncPhase, AuditPhase,
]


def run_dream(store: AbstractGraphStore, embedder: AbstractEmbedder,
              phases: Optional[List[int]] = None) -> List[Dict[str, Any]]:
    pipeline = DreamPipeline()
    audit_phase = AuditPhase()
    phase_list = []

    for i, cls in enumerate(_ALL_PHASES, 1):
        if phases is None or i in phases:
            if cls == AuditPhase:
                phase_list.append(audit_phase)
            else:
                phase_list.append(cls())

    for p in phase_list:
        pipeline.register(p)

    results = pipeline.execute(store, embedder)

    snapshot = {}
    if results:
        snapshot = results[0].get("result", {})
    audit_phase.set_snapshot(snapshot)

    return results

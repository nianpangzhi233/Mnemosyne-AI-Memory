#!/usr/bin/env python3
"""Dream Pipeline — 做梦流程插件化框架

v6.0 Fast/Slow 双流架构：
  Fast Path（不调 LLM，每次必跑）：
    SnapshotPhase → SimilarToPhase → DecayPhase → CovenantPhase → SyncPhase
  Slow Path（调 LLM，可选/异步）：
    LogScanPhase → DistillPhase → CausalPhase → TransfersPhase →
    ContradictsPhase → StrategyPhase → LLMReviewPhase
  AuditPhase 始终在最后执行。

每个 Phase 继承 DreamPhase，只通过 AbstractGraphStore 接口操作数据，
不直接访问 SQL / _connect()。
"""

import json
import math
import re
import sqlite3
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

    @staticmethod
    def _get_last_dream_time(store) -> str:
        try:
            conn = store._connect()
            try:
                cur = conn.cursor()
                cur.execute("SELECT value FROM meta WHERE key='last_dream'")
                row = cur.fetchone()
                return row[0] if row and row[0] else ""
            finally:
                conn.close()
        except Exception:
            return ""


_DREAM_LOG_DB = Path(__file__).resolve().parent.parent.parent / "dream_log.db"


def _init_dream_log():
    conn = sqlite3.connect(str(_DREAM_LOG_DB))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS dreams (
            id TEXT PRIMARY KEY,
            started_at TEXT,
            finished_at TEXT,
            status TEXT,
            nodes_before INTEGER,
            edges_before INTEGER,
            nodes_after INTEGER,
            edges_after INTEGER,
            phases TEXT
        )
    """)
    conn.commit()
    conn.close()


class DreamPipeline:
    def __init__(self):
        self._phases: List[DreamPhase] = []

    def register(self, phase: DreamPhase) -> "DreamPipeline":
        self._phases.append(phase)
        return self

    def execute(self, store: AbstractGraphStore, embedder: AbstractEmbedder) -> List[Dict[str, Any]]:
        import sqlite3 as _sq
        _init_dream_log()
        started = _now_iso()
        nodes_before = store.count_nodes()
        edges_before = store.count_edges()

        results = []
        for i, phase in enumerate(self._phases, 1):
            print(f"[Phase {i}] {phase.name}")
            try:
                result = phase.run(store, embedder)
                print(f"  结果: {result}")
                results.append({"phase": i, "name": phase.name, "result": result})
            except Exception as e:
                print(f"  错误: {e}")
                results.append({"phase": i, "name": phase.name, "result": {"status": "ERROR", "error": str(e)}})

        nodes_after = store.count_nodes()
        edges_after = store.count_edges()
        final_status = "PASS"
        for r in results:
            res = r.get("result", {})
            if isinstance(res, dict) and res.get("status") == "WARN":
                final_status = "WARN"
                break

        log_conn = _sq.connect(str(_DREAM_LOG_DB))
        try:
            log_conn.execute(
                "INSERT INTO dreams(id, started_at, finished_at, status, nodes_before, edges_before, nodes_after, edges_after, phases) VALUES (?,?,?,?,?,?,?,?,?)",
                (str(uuid.uuid4()), started, _now_iso(), final_status,
                 nodes_before, edges_before, nodes_after, edges_after,
                 json.dumps(results, ensure_ascii=False, default=str))
            )
            log_conn.commit()
        finally:
            log_conn.close()

        return results


class SimilarToPhase(DreamPhase):
    @property
    def name(self) -> str:
        return "向量扫描 similar_to (VectorIndexPhase)"

    def run(self, store: AbstractGraphStore, embedder: AbstractEmbedder) -> dict:
        # v6.1: Incremental — only check new nodes vs all
        last_dream = self._get_last_dream_time(store)
        if last_dream:
            new_nodes = store.query_nodes(
                "created_at > ? AND task_type IS NOT NULL AND type='experience'",
                (last_dream,)
            )
        else:
            new_nodes = store.query_nodes("task_type IS NOT NULL AND type='experience'")

        if not new_nodes:
            return {"added": 0, "new_nodes": 0}

        all_nodes = store.bulk_get_vectors()
        all_nodes = [n for n in all_nodes if n.get("task_type") is not None]
        existing = store.bulk_get_edge_pairs("similar_to")

        edges_to_add = []
        for new_n in new_nodes:
            new_vec_raw = new_n.get("vector")
            if not new_vec_raw:
                continue
            va = np.frombuffer(new_vec_raw, dtype=np.float32)
            for old_n in all_nodes:
                if old_n["id"] == new_n["id"]:
                    continue
                if (new_n["id"], old_n["id"]) in existing:
                    continue
                vb = np.frombuffer(old_n["vector"], dtype=np.float32)
                sim = float(np.dot(va, vb))
                if sim > 0.85:
                    edge = {
                        "from_id": new_n["id"],
                        "to_id": old_n["id"],
                        "relation_type": "similar_to",
                        "weight": round(sim, 3),
                        "source": "dream",
                    }
                    edge["graph_dim"] = "semantic"
                    edge["strength"] = "strong" if edge.get("weight", 0.5) >= 0.6 else "weak"
                    edges_to_add.append(edge)

        added = store.bulk_add_edges(edges_to_add)
        return {"added": added, "new_nodes": len(new_nodes)}


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
        ("不行", "行"), ("不可", "可"), ("不适用", "适用"),
    ]

    @property
    def name(self) -> str:
        return "语义矛盾检测 + A-MEM 进化"

    def run(self, store: AbstractGraphStore, embedder: AbstractEmbedder) -> dict:
        # Step 1: Get nodes created since last dream (diff-based)
        last_dream = self._get_last_dream_time(store)
        if last_dream:
            new_nodes = store.query_nodes(
                "created_at > ? AND type = 'experience'",
                (last_dream,)
            )
        else:
            new_nodes = store.query_nodes("type = 'experience'")

        if not new_nodes:
            return {"added": 0, "evolved": 0, "scanned": 0, "new_nodes": 0}

        existing = store.bulk_get_edge_pairs("contradicts")
        store._ensure_vector_index()

        edges_to_add = []
        evolution_updates = []
        scanned = 0

        for new_n in new_nodes:
            new_vec_raw = new_n.get("vector")
            if not new_vec_raw:
                continue
            new_vec = np.frombuffer(new_vec_raw, dtype=np.float32)
            candidates = store._vector_index.search(new_vec, top=10)

            for cand_id, sim in candidates:
                if new_n["id"] == cand_id:
                    continue
                if (new_n["id"], cand_id) in existing or (cand_id, new_n["id"]) in existing:
                    continue
                scanned += 1
                cand = store.get_node(cand_id)
                if not cand:
                    continue

                # Step 2: Keyword fast-check (zero-cost string match)
                if not self._has_opposition_keywords(new_n["content"], cand["content"]):
                    continue

                # Step 3: LLM deep-check (if enabled, semantic understanding)
                contradicts = True  # keyword match alone is sufficient signal
                if self._llm_enabled():
                    result = self._llm_judge_contradiction(new_n, cand)
                    if result is not None:
                        contradicts = result.get("contradicts", True)

                if contradicts:
                    edges_to_add.append({
                        "from_id": new_n["id"], "to_id": cand_id,
                        "relation_type": "contradicts", "weight": 0.7, "source": "dream",
                        "graph_dim": "causal", "strength": "strong",
                    })
                    evolution_updates.append({
                        "id": cand_id,
                        "field": "confidence",
                        "delta": -0.2,
                    })

        added = store.bulk_add_edges(edges_to_add)

        for upd in evolution_updates:
            node = store.get_node(upd["id"])
            if node:
                new_conf = max(0.0, node.get("confidence", 1.0) + upd["delta"])
                store.update_node(upd["id"], confidence=new_conf)

        return {"added": added, "evolved": len(evolution_updates),
                "scanned": scanned, "new_nodes": len(new_nodes)}

    @classmethod
    def _has_opposition_keywords(cls, text_a: str, text_b: str) -> bool:
        for w1, w2 in cls.OPPOSITE_PAIRS:
            if (w1 in text_a and w2 in text_b) or (w2 in text_a and w1 in text_b):
                return True
        return False

    @staticmethod
    def _llm_enabled() -> bool:
        try:
            import sys
            from pathlib import Path
            scripts_dir = Path(__file__).resolve().parent.parent
            if str(scripts_dir) not in sys.path:
                sys.path.insert(0, str(scripts_dir))
            from llm_judge import load_config
            return load_config().get("enabled", False)
        except Exception:
            return False

    @staticmethod
    def _llm_judge_contradiction(new_node: dict, old_node: dict) -> dict:
        try:
            import sys
            from pathlib import Path
            scripts_dir = Path(__file__).resolve().parent.parent
            if str(scripts_dir) not in sys.path:
                sys.path.insert(0, str(scripts_dir))
            from llm_judge import load_config, _call_llm, _extract_json

            config = load_config()
            if not config.get("enabled"):
                return None

            system = (
                "You are a contradiction detection engine for a memory system.\n"
                "Two memories are about the same topic area. Determine if they contradict.\n\n"
                "Contradiction: one says X works/is good, the other says X fails/is bad.\n"
                "Not contradiction: different contexts (Windows vs Linux).\n\n"
                "Return EXACTLY this JSON, nothing else:\n"
                '{"contradicts": true/false, "scope": "condition if partial", "confidence": 0.0-1.0}'
            )
            user = (
                f"Memory A: {new_node.get('content', '')[:300]}\n"
                f"Memory B: {old_node.get('content', '')[:300]}\n\n"
                f"Principle A: {new_node.get('principle', '') or 'none'}\n"
                f"Principle B: {old_node.get('principle', '') or 'none'}"
            )
            result = _call_llm(config["endpoint"], config["model"], system, user,
                              timeout=config.get("timeout", 120))
            if result:
                return _extract_json(result)
        except Exception:
            pass
        return None


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
            half_life = n.get("half_life_days") or 30.0
            verified_count = n.get("verified_count") or 0
            confidence = n.get("confidence") or 1.0
            adjusted_half_life = half_life * (1 + math.log(verified_count + 1))
            new_decay = base * math.exp(-math.log(2) * days / max(1, adjusted_half_life)) * math.log2(access + 2) * tw * confidence
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


class LogScanPhase(DreamPhase):
    @property
    def name(self) -> str:
        return "对话日志扫描"

    def run(self, store: AbstractGraphStore, embedder: AbstractEmbedder) -> dict:
        import sys
        from pathlib import Path
        scripts_dir = Path(__file__).resolve().parent.parent
        if str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))
        from log_scanner.scanner import scan

        fragments = scan()
        written = 0
        for frag in fragments:
            content = frag["content"]
            project = frag.get("session_title", "")[:30] or None
            try:
                store.add_node(content=content, node_type="raw",
                               project=project, principle=None)
                written += 1
            except Exception:
                pass

        return {"scanned_sessions": len(fragments), "written": written}


class DistillPhase(DreamPhase):
    @property
    def name(self) -> str:
        return "L2 蒸馏（raw → experience）"

    def run(self, store: AbstractGraphStore, embedder: AbstractEmbedder) -> dict:
        import sys
        import time
        from pathlib import Path
        scripts_dir = Path(__file__).resolve().parent.parent
        if str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))
        from llm_judge import load_config, _call_llm, _extract_json

        config = load_config()
        if not config.get("enabled"):
            return {"distilled": 0, "discarded": 0, "skipped": "LLM disabled"}

        endpoint = config["endpoint"]
        model = config["model"]
        timeout = config.get("timeout", 120)

        raw_nodes = store.query_nodes("type='raw'")
        if not raw_nodes:
            return {"distilled": 0, "discarded": 0, "skipped": "no raw nodes"}

        distilled = 0
        discarded = 0
        errors = 0

        system_prompt = (
            "You are a memory distillation engine for an AI agent called Mnemosyne.\n"
            "Your job: decide if a raw conversation fragment contains experience worth remembering long-term.\n\n"
            "## What to KEEP\n"
            "- Task completed with clear outcome (success or failure)\n"
            "- Bug fixed with root cause and solution\n"
            "- Decision made with reasoning (chose X over Y because...)\n"
            "- User preference or style learned ('I prefer...')\n"
            "- Pattern or principle discovered that generalizes\n"
            "- Error that reveals a non-obvious trap\n\n"
            "## What to DISCARD\n"
            "- Pure chitchat, greetings, acknowledgments\n"
            "- Incomplete task with no conclusion\n"
            "- Tool invocation logs with no insight\n"
            "- Configuration changes with no lesson learned\n"
            "- Duplicate of existing knowledge\n\n"
            "## Output Format\n"
            "Respond with EXACTLY this JSON structure, nothing else:\n\n"
            "If worth keeping:\n"
            '{"keep": true, "principle": "concise one-line principle that generalizes the lesson", "summary": "1-2 sentence factual summary of what happened and what was learned"}\n\n'
            "If not worth keeping:\n"
            '{"keep": false}\n\n'
            "## Examples\n\n"
            "Fragment: [User] gzip请求体解析失败 [AI] 加了gunzip解压 [Tool:bash] tests passed\n"
            '{"keep": true, "principle": "Check Content-Encoding before parsing request body", "summary": "Fixed gzip-compressed request body parsing by adding decompression step before JSON.parse"}\n\n'
            "Fragment: [User] 你好 [AI] 你好！有什么可以帮你的？ [User] 谢谢\n"
            '{"keep": false}\n\n'
            "Fragment: [User] 我喜欢函数式风格不要class [AI] 收到 [Tool:edit] refactored\n"
            '{"keep": true, "principle": "User prefers functional style over classes", "summary": "User stated preference for functional programming style, avoid class-based patterns"}\n\n'
            "Now judge the following fragment:"
        )

        for node in raw_nodes:
            content = node.get("content", "")
            content = re.sub(r"<[^>]+>", "", content)
            content = content.strip()
            if not content or len(content) < 50:
                conn = store._connect()
                try:
                    conn.execute("UPDATE nodes SET tier='cold' WHERE id=?", (node["id"],))
                    conn.commit()
                finally:
                    conn.close()
                discarded += 1
                continue

            user_prompt = f"Fragment:\n{content[:800]}"
            result = _call_llm(endpoint, model, system_prompt, user_prompt, timeout)

            if not result:
                errors += 1
                time.sleep(2)
                continue

            parsed = _extract_json(result)
            if not parsed:
                errors += 1
                continue

            if parsed.get("keep"):
                principle = parsed.get("principle", "")
                summary = parsed.get("summary", "")

                abstract = (principle or content[:150])[:150]
                overview = (summary or content[:600])[:600]

                conn = store._connect()
                try:
                    conn.execute(
                        "UPDATE nodes SET type='experience', principle=?, abstract=?, overview=? WHERE id=?",
                        (principle, abstract, overview, node["id"]),
                    )
                    conn.commit()
                finally:
                    conn.close()

                distilled += 1
            else:
                conn = store._connect()
                try:
                    conn.execute("UPDATE nodes SET tier='cold' WHERE id=?", (node["id"],))
                    conn.commit()
                finally:
                    conn.close()
                discarded += 1

            time.sleep(3)

        return {"distilled": distilled, "discarded": discarded, "errors": errors, "total_raw": len(raw_nodes)}


_FAST_PHASES = [SnapshotPhase, SimilarToPhase, DecayPhase, CovenantPhase, SyncPhase]
_SLOW_PHASES = [LogScanPhase, DistillPhase, CausalPhase, TransfersPhase, ContradictsPhase, StrategyPhase, LLMReviewPhase]

# Keep old name for backward compatibility
_ALL_PHASES = [SnapshotPhase, LogScanPhase, SimilarToPhase, CausalPhase, ContradictsPhase, TransfersPhase,
               StrategyPhase, CovenantPhase, DecayPhase, LLMReviewPhase, DistillPhase, SyncPhase, AuditPhase]


def run_dream(store: AbstractGraphStore, embedder: AbstractEmbedder,
              phases: Optional[List[int]] = None,
              slow: bool = True) -> List[Dict[str, Any]]:
    pipeline = DreamPipeline()
    audit_phase = AuditPhase()

    if phases is not None:
        # Legacy mode: run specific phases by index from _ALL_PHASES
        phase_list = []
        for i, cls in enumerate(_ALL_PHASES, 1):
            if i in phases:
                if cls == AuditPhase:
                    phase_list.append(audit_phase)
                else:
                    phase_list.append(cls())
    else:
        # Fast/Slow dual-stream mode
        phase_list = []
        for cls in _FAST_PHASES:
            phase_list.append(cls())
        if slow:
            for cls in _SLOW_PHASES:
                phase_list.append(cls())
        phase_list.append(audit_phase)

    for p in phase_list:
        pipeline.register(p)

    results = pipeline.execute(store, embedder)

    snapshot = {}
    if results:
        snapshot = results[0].get("result", {})
    audit_phase.set_snapshot(snapshot)

    return results

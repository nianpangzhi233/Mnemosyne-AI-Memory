#!/usr/bin/env python3
"""llm_judge.py — LLM 智能审查层（仿 REM 睡眠）

自适应三轮审查：
  第一轮（快判）：最少上下文，快速分类 high/medium/low
  第二轮（深判）：中/低置信度条目补充 1 跳上下文
  第三轮（终判）：仍为 low 的写 proposals

配置：~/memory-evolution/llm_config.json（不存在则纯规则模式）
"""

import json
import sys
import sqlite3
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from core.utils import fix_windows_encoding

fix_windows_encoding()

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "llm_config.json"
DB_PATH = BASE_DIR / "graph.db"


def load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"enabled": False}


def _call_llm(endpoint: str, model: str, system: str, user: str,
              timeout: int = 30, api_key: str = None) -> Optional[str]:
    payload_dict = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.1,
        "max_tokens": 2048,
        "thinking": {"type": "disabled"},
    }

    if api_key is None:
        api_key = load_config().get("api_key")

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = json.dumps(payload_dict).encode("utf-8")

    req = urllib.request.Request(
        endpoint, data=payload, headers=headers,
    )

    max_retries = 3
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                msg = body["choices"][0]["message"]
                content = msg.get("content") or msg.get("reasoning") or ""
                return content.strip() if content else None
        except urllib.error.HTTPError as e:
            if e.code in (400, 429, 503) and attempt < max_retries - 1:
                wait = 1
                print(f"  [llm_judge] {e.code}, retry {attempt+1}/{max_retries}...", file=sys.stderr)
                import time
                time.sleep(wait)
                continue
            print(f"  [llm_judge] LLM 调用失败: {e}", file=sys.stderr)
            return None
        except Exception as e:
            print(f"  [llm_judge] LLM 调用失败: {e}", file=sys.stderr)
            return None


def _extract_json(text: str):
    text = text.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0]
    elif "```" in text:
        text = text.split("```")[1].split("```")[0]
    start = text.find("{")
    if start == -1:
        start = text.find("[")
    if start >= 0:
        text = text[start:]
    return json.loads(text.strip())


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Undo Log ──────────────────────────────────────────────

def undo_log_init():
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
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
    conn.commit()
    conn.close()


def undo_log_write(operation: str, target_type: str, target_id: str,
                   before_data: dict, after_data: dict = None):
    import uuid
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        "INSERT INTO undo_log(id, operation, target_type, target_id, before_data, after_data, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), operation, target_type, target_id,
         json.dumps(before_data, ensure_ascii=False),
         json.dumps(after_data, ensure_ascii=False) if after_data else None,
         _now_iso()),
    )
    conn.commit()
    conn.close()


def undo_log_purge(days: int = 7):
    conn = sqlite3.connect(str(DB_PATH))
    cutoff = datetime.now(timezone.utc).timestamp() - days * 86400
    conn.execute(
        "DELETE FROM undo_log WHERE julianday('now') - julianday(created_at) > ?",
        (days,),
    )
    conn.commit()
    conn.close()


# ── 第一轮：快判 ─────────────────────────────────────────

def quick_review_edges(edges: list, store, config: dict) -> list:
    if not edges:
        return []

    summaries = []
    for e in edges:
        from_node = store.get_node(e["from_id"])
        to_node = store.get_node(e["to_id"])
        from_c = (from_node or {}).get("content", "")[:60] if from_node else "?"
        to_c = (to_node or {}).get("content", "")[:60] if to_node else "?"
        from_p = (from_node or {}).get("principle", "") or ""
        to_p = (to_node or {}).get("principle", "") or ""
        summaries.append({
            "idx": len(summaries),
            "relation": e["relation_type"],
            "weight": e["weight"],
            "from": from_c, "from_principle": from_p[:40],
            "to": to_c, "to_principle": to_p[:40],
        })

    prompt = f"""对以下{len(summaries)}条边快速判断。每条只需返回 confidence(high/medium/low) 和 action(keep/veto)。

判断标准：
- high: 明确有意义（同一教训的不同阶段、真正的因果关系、同类经验聚合）
- medium: 可能有关但不确定（表面相关但领域不同、语义重叠但角度不同）
- low: 明显无意义或误判（矛盾判断有误、跨域牵强关联）
- veto: 删除这条边

边列表:
{json.dumps(summaries, ensure_ascii=False, indent=2)}

只返回 JSON 数组: [{{"idx":0, "confidence":"high", "action":"keep", "reason":"一句话"}}]"""

    system = (
        "你是 Mnemosyne 记忆图谱审核员，模拟大脑 REM 睡眠的审查功能。\n"
        "你的任务：快速评估自动生成的知识图谱边是否有意义。\n\n"
        "边代表经验之间的关系（因果、相似、矛盾、迁移等）。\n"
        "有意义的边帮助 AI 在未来检索时发现深层关联。\n"
        "无意义的边是噪声，浪费 token。\n\n"
        "只返回 JSON 数组，不要其他文字。"
    )

    result = _call_llm(config["endpoint"], config["model"], system, prompt,
                       timeout=config.get("timeout", 120))
    if result:
        try:
            return _extract_json(result)
        except Exception:
            pass
    return [{"idx": i, "confidence": "high", "action": "keep",
             "reason": "LLM unavailable, auto-keep"} for i in range(len(edges))]


# ── 第二轮：深判 ─────────────────────────────────────────

def deep_review_items(items: list, store, config: dict) -> list:
    if not items:
        return []

    enriched = []
    for item in items:
        node = store.get_node(item.get("target_id", ""))
        if not node:
            enriched.append(item)
            continue

        neighbors = store.query_edges(
            f"(from_id='{item['target_id']}' OR to_id='{item['target_id']}') AND status='active'"
        )
        neighbor_summary = []
        for n in neighbors[:5]:
            other_id = n["to_id"] if n["from_id"] == item["target_id"] else n["from_id"]
            other = store.get_node(other_id)
            other_c = (other or {}).get("content", "")[:40] if other else "?"
            neighbor_summary.append(f"  {n['relation_type']} → {other_c}")

        item["content_full"] = node.get("content", "")[:100]
        item["principle"] = node.get("principle", "")
        item["task_type"] = node.get("task_type", "")
        item["access_count"] = node.get("access_count", 0)
        item["neighbors"] = neighbor_summary
        enriched.append(item)

    prompt = f"""对以下{len(enriched)}条拿不准的项做深度判断。

每项有完整内容和图谱上下文。判断:
- action: keep(保留) / merge(合并到target_id) / delete(删除垃圾) / veto_edge(删除边)
- confidence: high / medium / low

项目:
{json.dumps(enriched, ensure_ascii=False, indent=2, default=str)}

只返回 JSON 数组: [{{"target_id":"xxx", "action":"keep", "confidence":"high", "reason":"...", "merge_target":"yyy"}}]"""

    system = (
        "你是 Mnemosyne 记忆图谱深度审核员。\n"
        "你的任务：对第一轮快判中置信度不高的条目做细致分析。\n\n"
        "每项都包含完整内容和图谱邻居信息，你需要理解语义本质后再判断。\n"
        "关键：区分「真正无关」和「看似无关实则深层关联」。\n\n"
        "只返回 JSON 数组，不要其他文字。"
    )

    result = _call_llm(config["endpoint"], config["model"], system, prompt,
                       timeout=config.get("timeout", 120))
    if result:
        try:
            return _extract_json(result)
        except Exception:
            pass
    return [{"target_id": item.get("target_id", ""), "action": "keep",
             "confidence": "medium", "reason": "LLM deep review failed"}
            for item in items]


# ── 执行审查结果 ─────────────────────────────────────────

def execute_review(results: list, store) -> dict:
    executed = 0
    tentative = 0
    proposed = 0

    for r in results:
        action = r.get("action", "keep")
        confidence = r.get("confidence", "high")

        if action == "keep" or confidence == "high" and action not in ("veto", "delete", "merge"):
            continue

        if confidence == "high":
            if action in ("veto", "veto_edge"):
                target_id = r.get("target_id", r.get("edge_id", ""))
                if target_id:
                    edge = store.get_edge(target_id)
                    if edge:
                        undo_log_write("veto_edge", "edge", target_id, edge)
                        store.veto_edges([target_id])
                        executed += 1

            elif action == "delete":
                target_id = r.get("target_id", "")
                node = store.get_node(target_id)
                if node:
                    undo_log_write("delete_node", "node", target_id, node)
                    conn = store._connect()
                    conn.execute("DELETE FROM edges WHERE from_id=? OR to_id=?",
                                 (target_id, target_id))
                    conn.execute("DELETE FROM nodes WHERE id=?", (target_id,))
                    conn.commit()
                    conn.close()
                    executed += 1

            elif action == "merge":
                target_id = r.get("target_id", "")
                merge_to = r.get("merge_target", "")
                if target_id and merge_to:
                    node = store.get_node(target_id)
                    if node:
                        undo_log_write("merge_node", "node", target_id, node)
                        conn = store._connect()
                        conn.execute("UPDATE edges SET from_id=? WHERE from_id=?",
                                     (merge_to, target_id))
                        conn.execute("UPDATE edges SET to_id=? WHERE to_id=?",
                                     (merge_to, target_id))
                        conn.execute("DELETE FROM nodes WHERE id=?", (target_id,))
                        conn.commit()
                        conn.close()
                        executed += 1

        elif confidence == "medium":
            target_id = r.get("target_id", "")
            if target_id and action == "veto_edge":
                conn = store._connect()
                conn.execute(
                    "UPDATE edges SET status='tentative' WHERE id=?", (target_id,))
                conn.commit()
                conn.close()
                tentative += 1

        else:
            proposed += 1

    return {"executed": executed, "tentative": tentative, "proposed": proposed}


# ── 主入口：完整审查流程 ─────────────────────────────────

def run_llm_review(store, embedder, snapshot: dict) -> dict:
    config = load_config()
    if not config.get("enabled", False):
        return {"status": "disabled", "reason": "LLM not enabled in config"}

    undo_log_init()
    undo_log_purge(days=config.get("undo_log_days", 7))

    # 构建审查池：增量 + 被激活的 + 随机抽样
    recent_edges = store.query_edges("source='dream' AND status='active'")

    touched_nodes = store.query_nodes(
        "updated_at > datetime('now', '-1 day')"
    )

    sample_ratio = config.get("sample_ratio", 0.1)
    import random
    all_nodes = store.query_nodes("")
    sample_size = max(1, int(len(all_nodes) * sample_ratio))
    random_nodes = random.sample(all_nodes, min(sample_size, len(all_nodes))) if all_nodes else []

    review_items = []
    for n in random_nodes:
        if n["id"] not in {t["id"] for t in touched_nodes}:
            review_items.append({"target_id": n["id"], "source": "random_sample"})

    print(f"  [LLM] 审查池: {len(recent_edges)} 新边 + {len(touched_nodes)} 已激活 + {len(random_nodes)} 随机抽样")

    # 第一轮：快判边
    print(f"  [LLM] 第一轮快判 {len(recent_edges)} 条边...")
    quick_results = quick_review_edges(recent_edges, store, config)

    medium_low_edges = [r for r in quick_results
                        if r.get("confidence") in ("medium", "low")
                        and r.get("action") != "keep"]

    # 第二轮：深判中低置信度
    if medium_low_edges:
        print(f"  [LLM] 第二轮深判 {len(medium_low_edges)} 条...")
        for qr in quick_results:
            if qr.get("confidence") in ("medium", "low") and qr.get("action") != "keep":
                target_id = ""
                for e in recent_edges:
                    if recent_edges.index(e) == qr.get("idx", -1):
                        target_id = e["id"]
                        break
                qr["target_id"] = target_id

        deep_results = deep_review_items(medium_low_edges, store, config)

        for dr in deep_results:
            if dr.get("confidence") == "low":
                tid = dr.get("target_id", "")[:8]
                reason = dr.get("reason", "")
                proposals_path = BASE_DIR / "proposals" / "pending.md"
                proposals_path.parent.mkdir(parents=True, exist_ok=True)
                with open(proposals_path, "a", encoding="utf-8") as f:
                    f.write(f"- **{tid}**: {reason}\n")
    else:
        deep_results = []

    # 执行高置信度 + 中置信度标记
    all_results = quick_results + deep_results
    exec_result = execute_review(all_results, store)

    print(f"  [LLM] 执行: {exec_result['executed']} | 待复审: {exec_result['tentative']} | 提案: {exec_result['proposed']}")

    return {
        "status": "done",
        "edges_reviewed": len(recent_edges),
        "nodes_sampled": len(random_nodes),
        "quick_judged": len(quick_results),
        "deep_judged": len(medium_low_edges),
        **exec_result,
    }

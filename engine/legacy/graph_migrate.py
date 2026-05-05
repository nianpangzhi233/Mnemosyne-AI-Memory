#!/usr/bin/env python3
"""Memory Evolution v4.0 — v3→v4 数据迁移

迁移步骤：
1. 读 hot/memory.md → 每条经验生成向量 → 写入 nodes（type=experience）
2. 读 engine/sensor.json records → 去重合并 → 写入 nodes
3. 读 engine/causal.json observations → 写入 edges（type=caused）
4. 读 engine/evo_devo.json strategies → 写入 nodes（type=strategy）+ evolved_from 边
5. 旧 JSON 文件移到 engine/legacy/（备份，不删除）
6. 跑一次完整做梦（Phase 1-8）

约束：
- 不删除原始数据
- 旧 JSON 归档到 legacy/
- 重复运行安全（节点内容去重）
"""

import os
os.environ.setdefault('HF_HUB_OFFLINE', '1')

import json
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import sqlite3

# 路径常量
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "graph.db"
HOT_MEMORY_PATH = BASE_DIR / "hot" / "memory.md"
SENSOR_PATH = BASE_DIR / "engine" / "sensor.json"
CAUSAL_PATH = BASE_DIR / "engine" / "causal.json"
EVO_DEVO_PATH = BASE_DIR / "engine" / "evo_devo.json"
COVENANT_PATH = BASE_DIR / "engine" / "covenant.json"
LEGACY_DIR = BASE_DIR / "engine" / "legacy"

MODEL_NAME = "BAAI/bge-m3"
_model = None


def get_model():
    """懒加载 BGE-M3 模型"""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        print("[migrate] 加载 BGE-M3 模型（首次约10秒）...")
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def content_fingerprint(content: str) -> str:
    """内容指纹：截取前100字符去空格，用于去重"""
    return re.sub(r'\s+', '', content[:100]).lower()


def node_exists_by_content(cur, content: str) -> str:
    """按内容去重：如果已有相同内容的节点，返回其 ID"""
    fp = content_fingerprint(content)
    cur.execute("SELECT id, content FROM nodes")
    for nid, existing_content in cur.fetchall():
        if content_fingerprint(existing_content) == fp:
            return nid
    return ""


def write_node_with_vector(cur, content: str, node_type: str,
                           task_type: str = None, project: str = None,
                           principle: str = None, metadata: dict = None):
    """写入节点（含向量生成），返回 node_id。已存在则跳过返回空串"""
    # 去重检查
    existing = node_exists_by_content(cur, content)
    if existing:
        return ""

    model = get_model()
    vector = model.encode(content, normalize_embeddings=True)
    vector_blob = vector.astype(np.float32).tobytes()

    node_id = str(uuid.uuid4())
    created = now_iso()
    tags_json = "[]"
    metadata_json = json.dumps(metadata or {}, ensure_ascii=False)

    cur.execute("""
        INSERT INTO nodes(id, type, content, principle, vector, tier,
                          decay_score, base_score, access_count, last_access,
                          created_at, updated_at, task_type, project, tags, metadata)
        VALUES (?, ?, ?, ?, ?, 'hot', 0.8, 0.8, 1, ?, ?, ?, ?, ?, ?, ?)
    """, (node_id, node_type, content, principle, vector_blob,
          created, created, created, task_type, project, tags_json, metadata_json))

    return node_id


def step1_migrate_memory_md():
    """Step 1: 从 hot/memory.md 迁移经验

    只提取 '- **标题**' 开头的主条目，合并其子行（原因/教训/项目）
    为一条完整经验。Preferences 和 Rules 段落跳过。
    """
    if not HOT_MEMORY_PATH.exists():
        print("[Step 1] hot/memory.md 不存在，跳过")
        return 0

    print("[Step 1] 迁移 hot/memory.md ...")
    content = HOT_MEMORY_PATH.read_text(encoding="utf-8")

    lines = content.split("\n")
    entries = []
    current_entry = None
    in_patterns = False

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("## Patterns"):
            in_patterns = True
            continue
        if stripped.startswith("## ") and in_patterns:
            in_patterns = False

        if not in_patterns:
            continue

        if stripped.startswith("- **"):
            if current_entry:
                entries.append(current_entry)
            title = re.sub(r'^-\s*\*\*(.+?)\*\*\s*', '', stripped)
            current_entry = {"title": title, "details": [], "line": stripped}
        elif current_entry and stripped.startswith("- "):
            detail = stripped[2:]
            for prefix in ["原因：", "教训：", "影响：", "修复：", "方案：",
                           "延伸：", "案例：", "项目："]:
                if detail.startswith(prefix):
                    detail = detail[len(prefix):]
                    break
            current_entry["details"].append(detail)

    if current_entry:
        entries.append(current_entry)

    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    count = 0
    for entry in entries:
        full_text = entry["title"]
        if entry["details"]:
            full_text += "。" + "；".join(entry["details"])
        principle = ""
        for d in entry["details"]:
            if any(k in d for k in ["先", "别", "要", "必须", "不能",
                                     "确保", "避免", "优先"]):
                principle = d
                break

        node_id = write_node_with_vector(
            cur, full_text, "experience", principle=principle)
        if node_id:
            count += 1
    conn.commit()
    conn.close()
    print(f"  迁移 {count} 条经验（去重后）")
    return count


def step2_migrate_sensor():
    """Step 2: 从 engine/sensor.json 迁移记录"""
    if not SENSOR_PATH.exists():
        print("[Step 2] engine/sensor.json 不存在，跳过")
        return 0

    print("[Step 2] 迁移 engine/sensor.json ...")
    with open(SENSOR_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    records = data.get("data", {}).get("records", [])
    if not records:
        print("  无记录")
        return 0

    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    count = 0
    for rec in records:
        ctx = rec.get("context", {})
        result = rec.get("result", "")
        task_type = rec.get("task_type", "")
        created_at = rec.get("created_at", "")

        # 组合经验文本
        lesson = ctx.get("lesson", "")
        if not lesson:
            issue = ctx.get("issue", "")
            solution = ctx.get("solution", "")
            lesson = solution or issue or ""
        if not lesson:
            continue

        # 添加 result 前缀让内容更丰富
        content = f"[{result}] {lesson}" if result else lesson

        node_id = write_node_with_vector(
            cur, content, "experience", task_type=task_type,
            metadata={"result": result, "source": "sensor",
                      "original_created_at": created_at}
        )
        if node_id:
            count += 1

    conn.commit()
    conn.close()
    print(f"  迁移 {count} 条记录（去重后）")
    return count


def step3_migrate_causal():
    """Step 3: 从 engine/causal.json 迁移因果关系"""
    if not CAUSAL_PATH.exists():
        print("[Step 3] engine/causal.json 不存在，跳过")
        return 0

    print("[Step 3] 迁移 engine/causal.json ...")
    with open(CAUSAL_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    observations = data.get("data", {}).get("observations", {})
    if not observations:
        print("  无观察数据")
        return 0

    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    count = 0

    for obs_key, obs_data in observations.items():
        # obs_key 格式: "node_a->node_b"
        parts = obs_key.split("->")
        if len(parts) != 2:
            continue

        # v3 的 causal 节点在 v4 中不一定有对应节点
        # 我们直接记录因果关系为边
        # 但需要先确保 from/to 节点存在
        # 由于 v3 causal 节点是抽象变量组合，v4 中不一定有
        # 这里我们创建抽象节点来承接这些边
        graph = data.get("data", {}).get("graph", {})
        from_key, to_key = parts[0].strip(), parts[1].strip()

        from_node_info = graph.get(from_key, {})
        to_node_info = graph.get(to_key, {})

        # 创建抽象因果节点（如果内容可提取）
        from_vars = from_node_info.get("variables", {})
        to_vars = to_node_info.get("variables", {})

        from_content = json.dumps(from_vars, ensure_ascii=False)
        to_content = json.dumps(to_vars, ensure_ascii=False)

        avg_strength = obs_data.get("avg_strength", 0.5)

        # 只有正向强度才建边
        if avg_strength <= 0:
            continue

        from_id = write_node_with_vector(
            cur, f"因果前件: {from_content}", "experience",
            task_type=from_vars.get("task_type"),
            metadata={"source": "causal_v3", "v3_key": from_key}
        )
        to_id = write_node_with_vector(
            cur, f"因果后件: {to_content}", "experience",
            task_type=to_vars.get("task_type"),
            metadata={"source": "causal_v3", "v3_key": to_key}
        )

        # 如果节点已存在，需要查找
        if not from_id:
            existing = node_exists_by_content(cur, f"因果前件: {from_content}")
            from_id = existing
        if not to_id:
            existing = node_exists_by_content(cur, f"因果后件: {to_content}")
            to_id = existing

        if from_id and to_id:
            edge_id = str(uuid.uuid4())
            cur.execute("""
                INSERT OR IGNORE INTO edges(id, from_id, to_id, relation_type, weight, source, status, created_at)
                VALUES (?, ?, ?, 'caused', ?, 'migrate', 'active', ?)
            """, (edge_id, from_id, to_id, round(abs(avg_strength), 3), now_iso()))
            count += 1

    conn.commit()
    conn.close()
    print(f"  迁移 {count} 条因果边")
    return count


def step4_migrate_strategies():
    """Step 4: 从 engine/evo_devo.json 迁移策略"""
    if not EVO_DEVO_PATH.exists():
        print("[Step 4] engine/evo_devo.json 不存在，跳过")
        return 0

    print("[Step 4] 迁移 engine/evo_devo.json ...")
    with open(EVO_DEVO_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    strategies = data.get("data", {}).get("strategies", {})
    if not strategies:
        print("  无策略")
        return 0

    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    count = 0
    for sid, strat in strategies.items():
        content = strat.get("content", "")
        task_type = strat.get("task_type", "")
        weight = strat.get("weight", 0.5)
        origin = strat.get("origin", "")

        if not content:
            continue

        node_id = write_node_with_vector(
            cur, content, "strategy", task_type=task_type,
            metadata={"source": "evo_devo_v3", "origin": origin,
                      "v3_id": sid, "v3_weight": weight}
        )
        if node_id:
            count += 1

    conn.commit()
    conn.close()
    print(f"  迁移 {count} 条策略（去重后）")
    return count


def step5_archive_legacy():
    """Step 5: 归档旧 JSON 到 engine/legacy/"""
    print("[Step 5] 归档旧 JSON ...")

    LEGACY_DIR.mkdir(parents=True, exist_ok=True)

    json_files = [SENSOR_PATH, CAUSAL_PATH, EVO_DEVO_PATH]
    # 添加其他 v3 JSON
    for name in ["concept.json", "decay-scores.json", "metacognitive.json",
                  "symbolic.json", "world_model.json"]:
        p = BASE_DIR / "engine" / name
        if p.exists():
            json_files.append(p)

    archived = 0
    for src in json_files:
        if not src.exists():
            continue
        dst = LEGACY_DIR / src.name
        if dst.exists():
            # 已归档过，跳过
            continue
        shutil.copy2(str(src), str(dst))
        archived += 1
        print(f"  归档: {src.name}")

    print(f"  共归档 {archived} 个文件（原文件保留）")
    return archived


def step6_run_dream():
    """Step 6: 跑一次完整做梦"""
    print("[Step 6] 运行完整做梦 ...")

    # 导入 graph_dream 模块
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from graph_dream import phase1_similar_to, phase2_causal, phase3_contradicts
    from graph_dream import phase4_transfers, phase5_strategy, phase6_covenant
    from graph_dream import phase7_decay, phase8_sync, show_stats

    phases = [
        ("Phase 1: similar_to", phase1_similar_to),
        ("Phase 2: caused/solves", phase2_causal),
        ("Phase 3: contradicts", phase3_contradicts),
        ("Phase 4: transfers_to", phase4_transfers),
        ("Phase 5: 策略生成", phase5_strategy),
        ("Phase 6: covenant 审核", phase6_covenant),
        ("Phase 7: 衰减重算", phase7_decay),
        ("Phase 8: memory.md 同步", phase8_sync),
    ]

    for name, func in phases:
        print(f"  {name}")
        result = func()
        print(f"    结果: {result}")

    show_stats()


def migrate():
    """执行完整迁移流程"""
    print("=" * 50)
    print("Memory Evolution v3 → v4 迁移")
    print("=" * 50)

    # 检查 graph.db 是否存在
    if not DB_PATH.exists():
        print("[migrate] graph.db 不存在，先建库...")
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from graph_init import init_db
        init_db()

    # 加载模型（所有步骤共享）
    print("[migrate] 初始化嵌入模型...")
    get_model()

    step1_migrate_memory_md()
    step2_migrate_sensor()
    step3_migrate_causal()
    step4_migrate_strategies()
    step5_archive_legacy()
    step6_run_dream()

    print("\n" + "=" * 50)
    print("迁移完成!")
    print("=" * 50)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="v3→v4 数据迁移")
    parser.add_argument("--step", type=int, help="只跑某个步骤 (1-6)")
    parser.add_argument("--dry-run", action="store_true", help="只检测不写入")
    args = parser.parse_args()

    if args.step:
        steps = {
            1: step1_migrate_memory_md,
            2: step2_migrate_sensor,
            3: step3_migrate_causal,
            4: step4_migrate_strategies,
            5: step5_archive_legacy,
            6: step6_run_dream,
        }
        if args.step in steps:
            steps[args.step]()
        else:
            print(f"无效步骤: {args.step}，可选 1-6")
    else:
        migrate()

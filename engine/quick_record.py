#!/usr/bin/env python3
"""Quick record tool for Memory Evolution.

Usage:
  python quick_record.py reflection "任务类型" "发现了什么" "下次怎么做"
  python quick_record.py correction "主题" "做错了什么" "应该怎么做"
  python quick_record.py sensor "任务类型" "success/failure" "上下文描述"
  python quick_record.py stats
"""
import json
import sys
import os
from datetime import datetime
from pathlib import Path

BASE = Path.home() / "memory-evolution"


def record_reflection(context: str, reflection: str, lesson: str):
    """Append a reflection to reflections/log.md"""
    path = BASE / "reflections" / "log.md"
    header = path.read_text(encoding="utf-8") if path.exists() else "# Reflection Log\n\n> Summaries of reflections, newest first.\n\n"

    # Check for duplicate lesson
    if lesson in header:
        print(f"SKIP: Lesson already recorded: {lesson[:50]}...")
        return

    entry = f"\n## {datetime.now().strftime('%Y-%m-%d %H:%M')} — {context}\n\n"
    entry += f"**CONTEXT**: {context}\n\n**REFLECTION**: {reflection}\n\n**LESSON**: {lesson}\n"

    # Insert after header (before first reflection)
    marker = "\n## "
    if marker in header:
        idx = header.index(marker)
        header = header[:idx] + entry + header[idx:]
    else:
        header += entry

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(header, encoding="utf-8")
    print(f"OK: Reflection recorded → {context}")


def record_correction(topic: str, wrong: str, correct: str):
    """Append a correction to hot/corrections.md"""
    path = BASE / "hot" / "corrections.md"
    content = path.read_text(encoding="utf-8") if path.exists() else "# Corrections Log\n\n| Date | What I Got Wrong | Correct Answer | Status |\n|------|-----------------|----------------|--------|\n"

    today = datetime.now().strftime("%Y-%m-%d")
    line = f"| {today} | {wrong} | {correct} | Active |\n"

    content += line
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"OK: Correction recorded → {topic}")


def record_sensor(task_type: str, result: str, context_desc: str):
    """Append a sensor record to engine/sensor.json"""
    path = BASE / "engine" / "sensor.json"
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
    else:
        data = {"records": []}

    # Keep module structure if it exists
    if "data" in data:
        records = data["data"].get("records", [])
    else:
        records = data.get("records", [])

    record = {
        "timestamp": datetime.now().isoformat(),
        "task_type": task_type,
        "result": result,
        "context": {"lesson": context_desc},
    }

    records.append(record)

    # Write back maintaining structure
    if "data" in data:
        data["data"]["records"] = records
        if "data" in data["data"]:
            data["data"]["data"]["record_index"] = len(records)
    else:
        data["records"] = records

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"OK: Sensor recorded → {task_type} {result}")


def show_stats():
    """Show current memory evolution stats"""
    print("=== Memory Evolution Stats ===\n")

    # HOT memory
    hot_mem = BASE / "hot" / "memory.md"
    if hot_mem.exists():
        lines = hot_mem.read_text(encoding="utf-8").strip().split("\n")
        print(f"hot/memory.md:      {len(lines)} lines")
    else:
        print("hot/memory.md:      (missing)")

    # Corrections
    corrections = BASE / "hot" / "corrections.md"
    if corrections.exists():
        lines = corrections.read_text(encoding="utf-8").strip().split("\n")
        print(f"hot/corrections.md: {len(lines)} lines")
    else:
        print("hot/corrections.md: (missing)")

    # Reflections
    reflections = BASE / "reflections" / "log.md"
    if reflections.exists():
        content = reflections.read_text(encoding="utf-8")
        count = content.count("## ")
        print(f"reflections/log.md: {count} reflections")
    else:
        print("reflections/log.md: (missing)")

    # Sensor
    sensor = BASE / "engine" / "sensor.json"
    if sensor.exists():
        data = json.loads(sensor.read_text(encoding="utf-8"))
        if "data" in data:
            records = data["data"].get("records", [])
        else:
            records = data.get("records", [])
        success = sum(1 for r in records if r.get("result") == "success")
        failure = sum(1 for r in records if r.get("result") == "failure")
        print(f"engine/sensor.json: {len(records)} records ({success}✓ / {failure}✗)")
    else:
        print("engine/sensor.json: (missing)")

    # Proposals
    proposals = BASE / "proposals" / "pending.md"
    if proposals.exists():
        content = proposals.read_text(encoding="utf-8")
        count = content.count("## ")
        print(f"proposals/pending:  {count} proposals")
    else:
        print("proposals/pending:  (missing)")

    # Warm/Cold
    warm_files = list((BASE / "warm").rglob("*")) if (BASE / "warm").exists() else []
    cold_files = list((BASE / "cold").rglob("*")) if (BASE / "cold").exists() else []
    print(f"warm/:              {len([f for f in warm_files if f.is_file()])} files")
    print(f"cold/:              {len([f for f in cold_files if f.is_file()])} files")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "reflection" and len(sys.argv) >= 5:
        record_reflection(sys.argv[2], sys.argv[3], sys.argv[4])
    elif cmd == "correction" and len(sys.argv) >= 5:
        record_correction(sys.argv[2], sys.argv[3], sys.argv[4])
    elif cmd == "sensor" and len(sys.argv) >= 5:
        record_sensor(sys.argv[2], sys.argv[3], sys.argv[4])
    elif cmd == "stats":
        show_stats()
    else:
        print(f"Unknown command or missing args: {cmd}")
        print(__doc__)
        sys.exit(1)

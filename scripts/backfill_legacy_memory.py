#!/usr/bin/env python3
"""Backfill legacy Mnemosyne memories with task_type and structured metadata.

Default mode is dry-run. Use --apply to write changes after reviewing output.
"""

import argparse
import json
import shutil
import sqlite3
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
ROOT = SCRIPTS_DIR.parent
DB_PATH = ROOT / "graph.db"

sys.path.insert(0, str(SCRIPTS_DIR))
from core.utils import fix_windows_encoding, ensure_hf_offline  # noqa: E402

fix_windows_encoding()
ensure_hf_offline()

from llm_judge import load_config, _call_llm, _extract_json  # noqa: E402


SYSTEM_PROMPT = (
    "You are a legacy memory backfill engine for Mnemosyne.\n"
    "Classify and structure one existing memory node.\n"
    "Use concise factual fields; do not invent details not supported by the content.\n\n"
    "Prefer the most specific domain category over generic debugging. For example, API gateway gzip parsing belongs to api_proxy, not debugging; ASR provider work belongs to asr_integration; visual/frontend work belongs to visual_design. Use debugging only when no clearer domain exists.\n\n"
    "Return EXACTLY this JSON object:\n"
    "{\n"
    '  "task_type": "best existing type or new snake_case type",\n'
    '  "outcome": "success|failure|partial|decision|preference|observation",\n'
    '  "problem": "specific problem if any, else empty string",\n'
    '  "solution": "specific solution if any, else empty string",\n'
    '  "root_cause": "root cause if known, else empty string",\n'
    '  "entities": ["important tools/libs/files/concepts"],\n'
    '  "evidence": "short quote or fact from the memory supporting this classification",\n'
    '  "confidence": 0.0\n'
    "}\n"
)

VALID_OUTCOMES = {"success", "failure", "partial", "decision", "preference", "observation"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_registered_types(conn: sqlite3.Connection) -> list[str]:
    row = conn.execute("SELECT value FROM meta WHERE key='registered_task_types'").fetchone()
    if not row:
        return []
    try:
        data = json.loads(row[0])
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _merge_metadata(old_raw: str, parsed: dict) -> str:
    old = {}
    if old_raw and old_raw != "{}":
        try:
            old = json.loads(old_raw)
            if not isinstance(old, dict):
                old = {}
        except (json.JSONDecodeError, TypeError):
            old = {}
    for key in ("outcome", "problem", "solution", "root_cause", "entities", "evidence"):
        if key not in old or old.get(key) in (None, "", []):
            old[key] = parsed.get(key, [] if key == "entities" else "")
    old["backfilled_by"] = "backfill_legacy_memory.py"
    old["backfilled_at"] = _now_iso()
    old["backfill_confidence"] = parsed.get("confidence", 0.0)
    return json.dumps(old, ensure_ascii=False)


def _candidate_query(include_metadata: bool) -> str:
    where = ["type='experience'"]
    if include_metadata:
        where.append("(task_type IS NULL OR metadata IS NULL OR metadata='{}' OR metadata NOT LIKE '%outcome%')")
    else:
        where.append("task_type IS NULL")
    return "SELECT id, content, principle, task_type, metadata FROM nodes WHERE " + " AND ".join(where) + " ORDER BY created_at ASC"


def _classify(node: dict, registered_types: list[str], config: dict) -> dict:
    content = node.get("content") or ""
    principle = node.get("principle") or ""
    types_str = ", ".join(registered_types) if registered_types else "none"
    user = (
        f"Registered task types: [{types_str}]\n\n"
        f"Current task_type: {node.get('task_type') or 'null'}\n"
        f"Principle: {principle[:400]}\n"
        f"Content: {content[:1200]}"
    )
    result = _call_llm(
        config["endpoint"], config["model"], SYSTEM_PROMPT, user,
        timeout=config.get("timeout", 30), api_key=config.get("api_key"),
    )
    if not result:
        return {"id": node["id"], "error": "empty LLM result"}
    try:
        parsed = _extract_json(result)
    except Exception as exc:
        return {"id": node["id"], "error": f"invalid JSON: {exc}"}
    if not isinstance(parsed, dict):
        return {"id": node["id"], "error": "JSON is not object"}
    task_type = str(parsed.get("task_type") or "").strip()
    if not task_type:
        return {"id": node["id"], "error": "missing task_type"}
    if not isinstance(parsed.get("entities"), list):
        parsed["entities"] = []
    outcome = str(parsed.get("outcome") or "observation").strip().lower()
    if outcome not in VALID_OUTCOMES:
        outcome = "observation"
    parsed["outcome"] = outcome
    return {"id": node["id"], "parsed": parsed}


def _backup_db() -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = ROOT / f"graph.backup-before-backfill-{stamp}.db"
    shutil.copy2(DB_PATH, backup)
    return backup


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill legacy memory task_type and structured metadata")
    parser.add_argument("--apply", action="store_true", help="Write changes to graph.db")
    parser.add_argument("--limit", type=int, default=30, help="Max nodes to inspect/process")
    parser.add_argument("--workers", type=int, default=6, help="Concurrent LLM calls")
    parser.add_argument("--metadata", action="store_true", help="Also fill structured metadata, not just task_type")
    parser.add_argument("--no-backup", action="store_true", help="Skip DB backup when applying")
    args = parser.parse_args()

    config = load_config()
    if not config.get("enabled"):
        print("LLM disabled; cannot backfill")
        return 1

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        registered = _load_registered_types(conn)
        rows = conn.execute(_candidate_query(args.metadata)).fetchmany(args.limit)
        nodes = [dict(r) for r in rows]
    finally:
        conn.close()

    print(f"mode: {'APPLY' if args.apply else 'DRY-RUN'}")
    print(f"candidates: {len(nodes)}")
    print(f"registered_types: {', '.join(registered) if registered else 'none'}")
    if not nodes:
        return 0

    results = []
    with ThreadPoolExecutor(max_workers=max(1, min(args.workers, len(nodes)))) as pool:
        futures = {pool.submit(_classify, n, registered, config): n for n in nodes}
        for future in as_completed(futures):
            results.append((futures[future], future.result()))

    ok = [r for _, r in results if r.get("parsed")]
    errors = [r for _, r in results if r.get("error")]
    print(f"classified: {len(ok)}, errors: {len(errors)}")

    for node, result in results[: min(20, len(results))]:
        print("-" * 70)
        print(f"id: {node['id'][:8]}")
        print(f"old_task_type: {node.get('task_type')}")
        print(f"content: {(node.get('content') or '')[:120]}")
        if result.get("error"):
            print(f"ERROR: {result['error']}")
            continue
        parsed = result["parsed"]
        print(f"new_task_type: {parsed.get('task_type')}")
        print(f"outcome: {parsed.get('outcome')} confidence={parsed.get('confidence')}")
        print(f"problem: {parsed.get('problem')}")
        print(f"solution: {parsed.get('solution')}")
        print(f"entities: {parsed.get('entities')}")
        print(f"evidence: {parsed.get('evidence')}")

    if not args.apply:
        print("dry-run only; rerun with --apply to write changes")
        return 0

    backup = None if args.no_backup else _backup_db()
    if backup:
        print(f"backup: {backup}")

    conn = sqlite3.connect(str(DB_PATH))
    try:
        changed = 0
        for node, result in results:
            parsed = result.get("parsed")
            if not parsed:
                continue
            new_task_type = parsed.get("task_type") or node.get("task_type")
            new_metadata = _merge_metadata(node.get("metadata") or "{}", parsed)
            conn.execute(
                "UPDATE nodes SET task_type=COALESCE(task_type, ?), metadata=?, updated_at=? WHERE id=?",
                (new_task_type, new_metadata, _now_iso(), node["id"]),
            )
            changed += 1
        conn.commit()
    finally:
        conn.close()
    print(f"updated: {changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

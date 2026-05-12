#!/usr/bin/env python3
"""Backfill legacy skill evolution evidence after functional scoring repair.

Default mode is dry-run. Use --apply to write graph.db.
"""

import argparse
import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from core import HarrierEmbedder, SQLiteStore  # noqa: E402


def _json_loads(value, default):
    if value in (None, ""):
        return default
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default


def _connect(db_path: Path):
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _latest_eval_summary(conn, skill_id: str):
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM skill_eval_runs WHERE skill_id=? AND eval_mode!='dry_run' ORDER BY datetime(created_at)",
        (skill_id,),
    ).fetchall()]
    if not rows:
        return None
    latest = rows[-1]
    grouped = defaultdict(list)
    for row in rows:
        key = row.get("round") or 0
        grouped[key].append(row)
    best = None
    for round_no, group in grouped.items():
        deltas = [float(r.get("live_test_delta") or 0) for r in group]
        regressions = sum(1 for r in group if r.get("regression"))
        avg_delta = sum(deltas) / len(deltas) if deltas else 0.0
        avg_baseline = sum(float(r.get("baseline_score") or 0) for r in group) / len(group)
        avg_with = sum(float(r.get("with_skill_score") or 0) for r in group) / len(group)
        avg_darwin = sum(float(r.get("darwin_score") or 0) for r in group) / len(group)
        passed = avg_delta > 0 and regressions == 0 and avg_darwin >= 80
        candidate = {
            "round": round_no,
            "eval_mode": group[-1].get("eval_mode"),
            "prompt_count": len(group),
            "darwin_score": round(avg_darwin, 1),
            "baseline_score": round(avg_baseline, 1),
            "with_skill_score": round(avg_with, 1),
            "live_test_delta": round(avg_delta, 1),
            "regression_count": regressions,
            "passed": passed,
            "prompt_results": [
                {
                    "run_id": r.get("id"),
                    "prompt_id": r.get("prompt_id"),
                    "baseline_score": r.get("baseline_score"),
                    "with_skill_score": r.get("with_skill_score"),
                    "delta": r.get("live_test_delta"),
                    "regression": bool(r.get("regression")),
                }
                for r in group
            ],
        }
        if best is None or (candidate["passed"], candidate["live_test_delta"], candidate["darwin_score"]) > (best["passed"], best["live_test_delta"], best["darwin_score"]):
            best = candidate
    best["latest_decision"] = latest.get("decision")
    best["latest_decision_reason"] = latest.get("decision_reason")
    prompt_ids = [str(item.get("prompt_id") or "") for item in best.get("prompt_results") or []]
    best["auto_smoke_only"] = bool(prompt_ids) and all(pid == "auto-smoke" for pid in prompt_ids)
    best["real_prompt_count"] = sum(1 for pid in prompt_ids if pid and pid != "auto-smoke")
    return best


def _source_key(artifact):
    return tuple(sorted(artifact.get("source_node_ids") or []))


def _name_key(name: str):
    return " ".join((name or "").lower().replace("skill embryo:", "").split())


def analyze(db_path: Path):
    store = SQLiteStore(db_path=str(db_path), embedder=HarrierEmbedder())
    conn = _connect(db_path)
    try:
        artifacts = store.list_skill_artifacts()
        summaries = {artifact["node_id"]: _latest_eval_summary(conn, artifact["node_id"]) for artifact in artifacts}
        actions = []
        duplicate_groups = defaultdict(list)
        for artifact in artifacts:
            duplicate_groups[(_source_key(artifact), _name_key(artifact.get("name")))].append(artifact)

        for artifact in artifacts:
            skill_id = artifact["node_id"]
            summary = summaries.get(skill_id)
            if artifact.get("status") == "needs_revision" and not artifact.get("needs_revision"):
                actions.append({"type": "sync_needs_revision_flag", "skill_id": skill_id, "name": artifact.get("name")})
            if artifact.get("status") == "approved":
                metadata = artifact.get("metadata") or {}
                usage_loop = metadata.get("usage_loop") if isinstance(metadata, dict) else {}
                risky = artifact.get("needs_revision") or (usage_loop or {}).get("audit_failures") or (usage_loop or {}).get("trigger_mismatch_count")
                already_paused = not artifact.get("inject_enabled") and artifact.get("review_status") == "audit_hold"
                if risky and not already_paused:
                    actions.append({"type": "pause_risky_approved_injection", "skill_id": skill_id, "name": artifact.get("name")})
            if summary and summary["passed"]:
                if summary.get("auto_smoke_only"):
                    metadata = artifact.get("metadata") or {}
                    if not metadata.get("needs_real_darwin_test"):
                        actions.append({"type": "mark_auto_smoke_retest_needed", "skill_id": skill_id, "name": artifact.get("name"), "darwin": summary})
                    continue
                has_verified = store._has_active_edge(skill_id, "verified_by")
                if not has_verified:
                    actions.append({"type": "backfill_verified_evidence", "skill_id": skill_id, "name": artifact.get("name"), "darwin": summary})
                if artifact.get("latest_decision") != "evolved" or artifact.get("latest_live_test_delta") != summary["live_test_delta"]:
                    actions.append({"type": "sync_latest_darwin_fields", "skill_id": skill_id, "name": artifact.get("name"), "darwin": summary})

        for (_, _), group in duplicate_groups.items():
            if len(group) < 2:
                continue
            def duplicate_rank(artifact):
                summary = summaries.get(artifact["node_id"]) or {}
                return (
                    1 if summary else 0,
                    0 if summary.get("auto_smoke_only") else 1,
                    {"approved": 5, "evolved": 4, "tested": 3, "needs_revision": 2, "draft": 1, "embryo": 0, "deprecated": -1}.get(artifact.get("status"), 0),
                    summary.get("live_test_delta") or artifact.get("latest_live_test_delta") or -999,
                    artifact.get("updated_at") or "",
                )
            group = sorted(group, key=lambda a: (
                duplicate_rank(a)
            ), reverse=True)
            keeper = group[0]
            for duplicate in group[1:]:
                if duplicate.get("status") != "deprecated":
                    actions.append({
                        "type": "mark_duplicate_skill",
                        "skill_id": duplicate["node_id"],
                        "name": duplicate.get("name"),
                        "duplicate_of": keeper["node_id"],
                    })
        return store, actions
    finally:
        conn.close()


def apply_actions(store: SQLiteStore, actions):
    applied = []
    for action in actions:
        skill_id = action["skill_id"]
        kind = action["type"]
        if kind == "sync_needs_revision_flag":
            store.update_skill_artifact(skill_id, needs_revision=1, review_status="needs_revision")
        elif kind == "pause_risky_approved_injection":
            store.update_skill_artifact(skill_id, inject_enabled=0, requires_feedback=1, review_status="audit_hold")
        elif kind == "backfill_verified_evidence":
            store.record_skill_verification_evidence(skill_id, action["darwin"], prompt_results=action["darwin"].get("prompt_results"))
        elif kind == "sync_latest_darwin_fields":
            summary = action["darwin"]
            mnemosyne = store.score_skill_mnemosyne(skill_id)
            decision = store.decide_skill_evolution(skill_id, darwin_result=summary, mnemosyne_result=mnemosyne)
            action["decision"] = decision
        elif kind == "mark_auto_smoke_retest_needed":
            artifact = store.get_skill_artifact(skill_id)
            metadata = artifact.get("metadata") or {}
            metadata["needs_real_darwin_test"] = True
            metadata["auto_smoke_backfill_note"] = "Legacy auto-smoke eval is not enough for verified evidence; rerun with real baseline-vs-skill prompts."
            store.update_skill_artifact(
                skill_id,
                needs_revision=1,
                review_status="needs_real_test",
                trial_enabled=1,
                requires_feedback=1,
                metadata=metadata,
            )
        elif kind == "mark_duplicate_skill":
            artifact = store.get_skill_artifact(skill_id)
            metadata = artifact.get("metadata") or {}
            metadata["duplicate_of"] = action["duplicate_of"]
            store.update_skill_artifact(
                skill_id,
                status="deprecated",
                review_status="duplicate",
                inject_enabled=0,
                trial_enabled=0,
                requires_feedback=0,
                metadata=metadata,
            )
        applied.append(action)
    return applied


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill legacy skill evolution evidence")
    parser.add_argument("--db", default=str(ROOT / "graph.db"))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    db_path = Path(args.db)
    store, actions = analyze(db_path)
    result = {"mode": "apply" if args.apply else "dry_run", "action_count": len(actions), "actions": actions}
    if args.apply:
        result["applied"] = apply_actions(store, actions)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

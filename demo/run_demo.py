#!/usr/bin/env python3
"""Run a safe cold-start Mnemosyne demo on temporary SQLite files.

The demo does not touch the real graph.db or dream_log.db. It imports safe
seed conversations, runs deterministic dream phases, writes a reviewable
EvolutionReport, creates a governed skill candidate, and records telemetry.
"""

import argparse
import json
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from core.dream_pipeline import AuditPhase, CausalPhase, ConceptPhase, DreamPipeline, SnapshotPhase, TransfersPhase
from core.sqlite_store import SQLiteStore
from core.telemetry import finish_run, list_runs, start_run
from graph_init import init_db


SEED_DIR = Path(__file__).resolve().parent / "seed_conversations"


class DemoEmbedder:
    def get_dimension(self):
        return 3

    def encode(self, text):
        lower = text.lower()
        if "gzip" in lower or "parse" in lower:
            return _unit([1, 0, 0])
        if "contract" in lower or "field" in lower:
            return _unit([0, 1, 0])
        if "windows" in lower or "utf" in lower or "sqlite" in lower:
            return _unit([0, 0, 1])
        return _unit([1, 1, 0])


def _unit(values):
    vec = np.array(values, dtype=np.float32)
    return vec / np.linalg.norm(vec)


def _load_seed_records(seed_dir: Path):
    records = []
    for path in sorted(seed_dir.glob("day*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                item = json.loads(line)
                item["source_file"] = path.name
                records.append(item)
    return records


def _add_demo_node(store: SQLiteStore, record: dict):
    vec = store._embedder.encode(record["content"]).astype(np.float32).tobytes()
    metadata = dict(record.get("metadata") or {})
    metadata["day"] = record.get("day")
    metadata["source_file"] = record.get("source_file")
    return store.add_raw_node(
        id=record["id"],
        type="experience",
        content=record["content"],
        principle=record.get("principle"),
        vector=vec,
        task_type=record.get("task_type"),
        project="demo",
        tags=json.dumps(["demo", "seed"], ensure_ascii=False),
        metadata=json.dumps(metadata, ensure_ascii=False),
    )


def _read_latest_report(dream_log_db: Path) -> dict:
    conn = sqlite3.connect(str(dream_log_db))
    try:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM evolution_reports ORDER BY created_at DESC LIMIT 1").fetchone()
        if not row:
            return {}
        return json.loads(row["report"] or "{}")
    finally:
        conn.close()


def _create_demo_skill(store: SQLiteStore) -> str:
    return store.create_skill_artifact(
        name="Check compressed JSON request bodies",
        source_node_ids=["problem-gzip", "solution-gzip"],
        status="evolved",
        trigger_patterns=["API gateway fails to parse JSON request bodies", "gzip or Content-Encoding parse issue"],
        preconditions=["HTTP request body parsing fails or returns mojibake"],
        procedure=[
            "Inspect Content-Encoding before parsing.",
            "If gzip is present, decompress the body before JSON.parse.",
            "Add a contract test with a gzipped request body.",
        ],
        verification="A gzipped JSON request parses successfully and the plain JSON path still works.",
        failure_modes=["Assuming all request bodies are plain JSON", "Trusting console mojibake instead of stored bytes"],
        risk_level="low",
        metadata={"demo": True, "story_step": "skill_candidate"},
    )


def _run_demo(tmp_path: Path) -> dict:
    db_path = tmp_path / "demo_graph.db"
    dream_log_db = tmp_path / "demo_dream_log.db"
    init_db(str(db_path))
    store = SQLiteStore(db_path=str(db_path), embedder=DemoEmbedder())
    embedder = store._embedder

    records = _load_seed_records(SEED_DIR)
    for record in records:
        _add_demo_node(store, record)

    run_id = start_run("demo_cold_start", db_path=dream_log_db, summary={"seed_records": len(records)})
    pipeline = DreamPipeline(dream_log_db=dream_log_db)
    audit = AuditPhase()
    for phase in (SnapshotPhase(), CausalPhase(), ConceptPhase(), TransfersPhase(), audit):
        pipeline.register(phase)
    results = pipeline.execute(store, embedder)

    skill_id = _create_demo_skill(store)
    store.update_skill_artifact(
        skill_id,
        trial_enabled=1,
        requires_feedback=1,
        latest_decision="evolved",
        latest_decision_reason="demo low-risk skill candidate with source evidence; trial only, not default injection",
        latest_darwin_score=82.0,
        latest_mnemosyne_score=81.0,
        latest_live_test_delta=2.0,
        latest_eval_mode="demo_story",
    )
    store.sync_skill_node_content(
        skill_id,
        "Check compressed JSON request bodies",
        trigger_patterns=["API gateway fails to parse JSON request bodies", "gzip or Content-Encoding parse issue"],
        procedure=[
            "Inspect Content-Encoding before parsing.",
            "If gzip is present, decompress the body before JSON.parse.",
            "Add a contract test with a gzipped request body.",
        ],
        verification="A gzipped JSON request parses successfully and the plain JSON path still works.",
    )
    injection = store.inject_skills(
        "API gateway fails to parse gzipped JSON request bodies",
        mode="trial",
        min_similarity=0.0,
        top=3,
    )
    report = _read_latest_report(dream_log_db)

    solves_edges = store.query_edges("relation_type='solves' AND status='active'")
    transfer_edges = store.query_edges("relation_type='transfers_to' AND status='active'")
    concepts = store.query_nodes("type='concept'")
    checks = {
        "seed_memories_imported": len(records) >= 6,
        "solves_edge_created": len(solves_edges) > 0,
        "concept_created": len(concepts) > 0,
        "transfers_created": len(transfer_edges) > 0,
        "report_created": bool(report.get("dream_id")),
        "report_has_evidence": bool((report.get("sections") or {}).get("new_concepts") or (report.get("sections") or {}).get("recommended_actions")),
        "skill_candidate_created": bool(skill_id),
        "injection_demo": bool(injection and "Check compressed JSON request bodies" in injection),
    }
    finish_run(run_id, "PASS" if all(checks.values()) else "WARN", db_path=dream_log_db, summary={"checks": checks, "skill_id": skill_id})
    runs = list_runs(limit=5, db_path=dream_log_db)
    checks["telemetry_run_created"] = any(run.get("run_type") == "demo_cold_start" for run in runs)

    status = "PASS" if all(checks.values()) else "WARN"
    return {
        "status": status,
        "demo_dir": str(tmp_path),
        "demo_db": str(db_path),
        "dream_log_db": str(dream_log_db),
        "seed_records": len(records),
        "nodes": store.count_nodes(),
        "edges": store.count_edges(),
        "skill_id": skill_id,
        "injection_output": injection,
        "checks": checks,
        "report_summary": report.get("summary"),
        "reviewable_counts": report.get("reviewable_counts"),
        "telemetry_runs": [{"run_type": run.get("run_type"), "status": run.get("status")} for run in runs],
        "phases": results,
        "next_step": "Run with --keep to inspect the demo SQLite files after the command exits.",
    }


def main():
    parser = argparse.ArgumentParser(description="Run a safe Mnemosyne cold-start demo")
    parser.add_argument("--keep", action="store_true", help="Keep the demo directory instead of deleting it")
    parser.add_argument("--out", help="Directory to use when --keep is enabled")
    args = parser.parse_args()

    if args.keep:
        demo_dir = Path(args.out) if args.out else Path(tempfile.mkdtemp(prefix="mnemosyne-demo-"))
        demo_dir.mkdir(parents=True, exist_ok=True)
        result = _run_demo(demo_dir)
        result["kept"] = True
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return 0 if result["status"] == "PASS" else 1

    tmp = Path(tempfile.mkdtemp(prefix="mnemosyne-demo-"))
    try:
        result = _run_demo(tmp)
        result["kept"] = False
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return 0 if result["status"] == "PASS" else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())

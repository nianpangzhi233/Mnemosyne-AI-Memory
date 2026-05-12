#!/usr/bin/env python3
"""Run a safe local Mnemosyne demo on temporary SQLite files.

The demo does not touch graph.db or dream_log.db. It creates a small graph,
runs deterministic dream phases, and writes a demo EvolutionReport.
"""

import json
import sqlite3
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from core.dream_pipeline import CausalPhase, ConceptPhase, DreamPipeline, SnapshotPhase, TransfersPhase, AuditPhase
from core.sqlite_store import SQLiteStore


class DemoEmbedder:
    def encode(self, text):
        lower = text.lower()
        if "gzip" in lower or "parse" in lower:
            return _unit([1, 0, 0])
        if "contract" in lower or "field" in lower:
            return _unit([0, 1, 0])
        return _unit([1, 1, 0])


def _unit(values):
    vec = np.array(values, dtype=np.float32)
    return vec / np.linalg.norm(vec)


def _init_demo_db(path: Path):
    conn = sqlite3.connect(str(path))
    try:
        conn.executescript(
            """
            CREATE TABLE nodes (
                id TEXT PRIMARY KEY,
                type TEXT,
                content TEXT,
                principle TEXT,
                abstract TEXT,
                overview TEXT,
                vector BLOB,
                task_type TEXT,
                project TEXT,
                tags TEXT DEFAULT '[]',
                context_tags TEXT DEFAULT '[]',
                metadata TEXT DEFAULT '{}',
                confidence REAL DEFAULT 1.0,
                verified_at TEXT,
                created_at TEXT DEFAULT '2026-05-12T00:00:00+00:00',
                updated_at TEXT DEFAULT '2026-05-12T00:00:00+00:00',
                last_access TEXT DEFAULT '2026-05-12T00:00:00+00:00',
                access_count INTEGER DEFAULT 0,
                verified_count INTEGER DEFAULT 0,
                base_score REAL DEFAULT 0.8,
                decay_score REAL DEFAULT 1.0,
                half_life_days REAL DEFAULT 30,
                tier TEXT DEFAULT 'hot',
                precondition TEXT,
                predicted_outcome TEXT,
                precondition_vec BLOB
            );
            CREATE TABLE edges (
                id TEXT PRIMARY KEY,
                from_id TEXT,
                to_id TEXT,
                relation_type TEXT,
                weight REAL,
                source TEXT,
                graph_dim TEXT DEFAULT 'semantic',
                strength TEXT DEFAULT 'strong',
                status TEXT DEFAULT 'active',
                created_at TEXT DEFAULT '2026-05-12T00:00:00+00:00',
                metadata TEXT DEFAULT '{}'
            );
            CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
            CREATE VIRTUAL TABLE nodes_fts USING fts5(id, content, principle, abstract, overview);
            """
        )
        conn.commit()
    finally:
        conn.close()


def _add_demo_node(store: SQLiteStore, node_id: str, content: str, principle: str, task_type: str, metadata: dict):
    vec = store._embedder.encode(content).astype(np.float32).tobytes()
    return store.add_raw_node(
        id=node_id,
        type="experience",
        content=content,
        principle=principle,
        vector=vec,
        task_type=task_type,
        project="demo",
        tags=json.dumps(["demo"], ensure_ascii=False),
        metadata=json.dumps(metadata, ensure_ascii=False),
    )


def main():
    with tempfile.TemporaryDirectory(prefix="mnemosyne-demo-") as tmp:
        db_path = Path(tmp) / "demo_graph.db"
        dream_log_db = Path(tmp) / "demo_dream_log.db"
        _init_demo_db(db_path)
        store = SQLiteStore(db_path=str(db_path), embedder=DemoEmbedder())
        embedder = store._embedder

        _add_demo_node(
            store,
            "problem-gzip",
            "API gateway failed to parse gzipped JSON request bodies.",
            "Check content encoding before parsing request bodies.",
            "api_proxy",
            {"outcome": "failure", "problem": "gzipped JSON parse failed", "entities": ["gzip", "json"]},
        )
        _add_demo_node(
            store,
            "solution-gzip",
            "Gunzip request bodies before JSON.parse in the API gateway.",
            "Check content encoding before parsing request bodies.",
            "api_proxy",
            {"outcome": "success", "solution": "gunzip before parse", "entities": ["gzip", "json"]},
        )
        for node_id, task in (("contract-a", "memory_system"), ("contract-b", "testing"), ("contract-c", "documentation")):
            _add_demo_node(
                store,
                node_id,
                f"{task} work benefited from explicit field contracts.",
                "Use explicit contracts before adding new memory fields.",
                task,
                {"outcome": "success", "solution": "contract first", "entities": ["contract", "field"]},
            )

        pipeline = DreamPipeline(dream_log_db=dream_log_db)
        audit = AuditPhase()
        for phase in (SnapshotPhase(), CausalPhase(), ConceptPhase(), TransfersPhase(), audit):
            pipeline.register(phase)
        results = pipeline.execute(store, embedder)
        status = "PASS"
        for item in results:
            result = item.get("result", {})
            if isinstance(result, dict) and result.get("status") in {"ERROR", "FAIL"}:
                status = "FAIL"
                break
            if isinstance(result, dict) and result.get("status") == "WARN":
                status = "WARN"

        print(json.dumps({
            "status": status,
            "demo_db": str(db_path),
            "dream_log_db": str(dream_log_db),
            "nodes": store.count_nodes(),
            "edges": store.count_edges(),
            "phases": results,
        }, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()

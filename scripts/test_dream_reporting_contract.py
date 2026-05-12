#!/usr/bin/env python3
"""Contract test for dream EvolutionReport and telemetry persistence."""

import json
import sqlite3
import sys
import tempfile
import uuid
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
ROOT = SCRIPTS_DIR.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from core.dream_pipeline import _build_evolution_report, _init_dream_log
from api import start_api


class ReportStore:
    def __init__(self):
        self.nodes = {
            "mem-1": {
                "id": "mem-1",
                "type": "experience",
                "content": "Repeated gzip parsing failures were fixed by checking Content-Encoding.",
                "principle": "Check content encoding before parsing request bodies.",
                "task_type": "api_proxy",
                "project": "demo",
                "created_at": "2026-05-12T00:00:00+00:00",
            },
            "concept-1": {
                "id": "concept-1",
                "type": "concept",
                "content": "Explicit contracts prevent silent field drift.",
                "principle": "Use explicit contracts before adding new memory fields.",
                "task_type": "memory_system",
                "project": "demo",
                "created_at": "2026-05-12T00:00:00+00:00",
            },
        }
        self.edges = [
            {
                "id": "edge-contradiction-1",
                "from_id": "mem-1",
                "to_id": "old-prediction",
                "relation_type": "contradicts",
                "status": "active",
                "weight": 0.8,
                "created_at": "2026-05-12T00:00:00+00:00",
            }
        ]
        self.skills = [
            {
                "node_id": "skill-1",
                "name": "Check compressed request bodies",
                "slug": "check-compressed-request-bodies",
                "status": "embryo",
                "review_status": "draft",
                "source_node_ids": ["mem-1"],
                "evidence_node_ids": [],
                "latest_decision": None,
                "latest_decision_reason": None,
            }
        ]

    def query_nodes(self, where_clause="", params=()):
        return list(self.nodes.values())

    def get_node(self, node_id):
        return self.nodes.get(node_id)

    def query_edges(self, where_clause="", params=()):
        return list(self.edges)

    def list_skill_artifacts(self, statuses=None):
        if not statuses:
            return self.skills
        return [skill for skill in self.skills if skill.get("status") in statuses]


def main():
    with tempfile.TemporaryDirectory(prefix="mnemosyne-report-contract-") as tmp:
        dream_log_db = Path(tmp) / "dream_log.db"
        old_api_db = start_api.DREAM_LOG_DB
        start_api.DREAM_LOG_DB = dream_log_db
        try:
            _init_dream_log(dream_log_db)
            dream_id = f"report-contract-{uuid.uuid4().hex}"
            results = [
                {"phase": 1, "name": "预检快照", "result": {"nodes_before": 10, "edges_before": 20}, "duration_ms": 1.2},
                {"phase": 2, "name": "因果检测 caused/solves", "result": {"added": 2}, "duration_ms": 3.4},
                {"phase": 3, "name": "技能胚胎涌现 SkillEmbryoPhase", "result": {"created": 1, "created_skill_ids": ["skill-1"]}, "duration_ms": 1.4},
                {"phase": 3, "name": "后审计", "result": {"status": "PASS", "alerts": []}, "duration_ms": 2.0},
            ]
            report = _build_evolution_report(dream_id, results, "PASS", 10, 20, 11, 22, 9.5, store=ReportStore())
            assert report["node_delta"] == 1
            assert report["edge_delta"] == 2
            assert report["highlights"], "report should include highlights for changed phases"
            assert report["sections"]["new_memories"], "report should expose new memories for review"
            assert report["sections"]["new_concepts"], "report should expose new concepts for review"
            assert report["sections"]["new_skills"], "report should expose skill candidates for review"
            assert report["sections"]["contradictions"], "report should expose contradiction evidence"
            assert report["sections"]["recommended_actions"], "report should suggest actionable reviews"
            assert report["sections"]["new_skills"][0]["evidence_ids"] == ["mem-1"]

            conn = sqlite3.connect(str(dream_log_db))
            try:
                conn.execute(
                    "INSERT INTO dreams(id, started_at, finished_at, status, nodes_before, edges_before, nodes_after, edges_after, phases) VALUES (?,?,?,?,?,?,?,?,?)",
                    (dream_id, "2026-05-12T00:00:00+00:00", "2026-05-12T00:00:01+00:00", "PASS", 10, 20, 11, 22, json.dumps(results)),
                )
                conn.execute(
                    "INSERT INTO evolution_reports(id, dream_id, created_at, status, summary, report) VALUES (?,?,?,?,?,?)",
                    (str(uuid.uuid4()), dream_id, "2026-05-12T00:00:01+00:00", "PASS", report["summary"], json.dumps(report)),
                )
                conn.execute(
                    "INSERT INTO telemetry_events(id, dream_id, created_at, event_type, phase, duration_ms, status, payload) VALUES (?,?,?,?,?,?,?,?)",
                    (str(uuid.uuid4()), dream_id, "2026-05-12T00:00:01+00:00", "dream", None, 9.5, "PASS", json.dumps({"phase_count": 3})),
                )
                conn.commit()
            finally:
                conn.close()

            latest_report = start_api.latest_evolution_report()["report"]
            assert latest_report["dream_id"] == dream_id
            telemetry = start_api.latest_telemetry(limit=5)["events"]
            assert any(event["dream_id"] == dream_id and event["event_type"] == "dream" for event in telemetry)
            summary = start_api.telemetry_summary()
            assert "by_status" in summary
            print(json.dumps({"status": "PASS", "dream_id": dream_id, "dream_log_db": str(dream_log_db)}, ensure_ascii=False, indent=2))
        finally:
            start_api.DREAM_LOG_DB = old_api_db


if __name__ == "__main__":
    main()

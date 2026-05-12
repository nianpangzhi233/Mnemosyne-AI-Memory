#!/usr/bin/env python3
"""Functional acceptance test for the Skill Evolution loop.

The goal is not to prove code paths are smooth. It proves a full-test Darwin win
is converted into graph evidence and can pass Mnemosyne governance.
"""

import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from core import HarrierEmbedder, ReplayAgentRunner, ReplayJudgeRunner, SQLiteStore  # noqa: E402
from graph_init import init_db  # noqa: E402


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="mnemosyne-skill-loop-"))
    try:
        db = tmp / "graph.db"
        init_db(str(db))
        store = SQLiteStore(db_path=str(db), embedder=HarrierEmbedder())
        store.sync_skill_file = lambda node_id: {
            "node_id": node_id,
            "file_path": "skills/functional-analogical-thinking/SKILL.md",
            "absolute_path": str(tmp / "SKILL.md"),
            "file_hash": "functional-test-no-file-write",
            "file_synced_at": "test",
        }
        source_ids = [
            store.add_node(
                content=f"Analogical thinking source evidence {idx}",
                node_type="experience",
                task_type="skill_memory",
                principle="Use cross-domain analogies to generate functional solutions",
            )
            for idx in range(3)
        ]
        skill_id = store.create_skill_artifact(
            name="Functional Analogical Thinking",
            source_node_ids=source_ids,
            status="draft",
            trigger_patterns=["complex problem", "need creative solution", "analogy"],
            preconditions=["The user needs more than a generic checklist"],
            procedure=[
                "Define the target problem and core tension.",
                "Find same-domain, cross-domain, biomimetic, and theory analogies.",
                "Extract transferable principles from each analogy.",
                "Generate concrete options and rank next actions.",
            ],
            verification="Compare baseline vs with-skill answers on realistic prompts; require positive delta and no regression.",
            failure_modes=["Surface-level analogies", "Too much structure without actionable options"],
            risk_level="low",
        )
        store.add_skill_test_prompt(
            skill_id,
            "classroom-feedback",
            "Design a psychologically safe classroom feedback mechanism with ritual.",
            expected="The answer should use analogies to produce actionable mechanisms, not only a checklist.",
            tags=["functional", "analogical"],
        )
        runner = ReplayAgentRunner(
            baseline_output="A reasonable checklist with rewards, private corrections, and class goals.",
            with_skill_output="A structured analogy-driven design using growth portfolios, game achievements, forest niches, and self-determination theory to produce ranked mechanisms.",
        )
        judge = ReplayJudgeRunner({
            "winner": "with_skill",
            "baseline_score": 7,
            "with_skill_score": 8.5,
            "delta": 1.5,
            "regression": False,
            "reason": "with_skill produces more transferable principles and clearer next actions.",
        })
        result = store.run_skill_darwin_evaluation(skill_id, runner, judge, round_no=1, eval_mode="full_test")
        artifact = store.get_skill_artifact(skill_id)
        edges = store.query_edges("from_id=? AND relation_type='verified_by' AND status='active'", (skill_id,))
        ok = (
            result["decision"]["decision"] == "evolved"
            and artifact["status"] == "evolved"
            and artifact["latest_live_test_delta"] > 0
            and artifact["latest_darwin_score"] >= 80
            and artifact["latest_mnemosyne_score"] >= 80
            and len(edges) >= 1
        )
        print(json.dumps({
            "status": "PASS" if ok else "FAIL",
            "skill_id": skill_id,
            "decision": result["decision"],
            "darwin": result["darwin"],
            "mnemosyne": result["mnemosyne"],
            "verified_by_edges": len(edges),
        }, ensure_ascii=False, indent=2))
        return 0 if ok else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())

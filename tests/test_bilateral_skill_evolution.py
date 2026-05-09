import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from graph_init import init_db
import core.sqlite_store as sqlite_store_module
from core.sqlite_store import SQLiteStore
from core.dream_pipeline import SkillMirrorEvolutionPhase
from core.skill_evolution import SkillEvolutionRunner
from core.runners import ReplayAgentRunner, ReplayJudgeRunner


class DummyEmbedder:
    def get_dimension(self):
        return 1024

    def encode(self, text):
        seed = abs(hash(text)) % 1024
        vec = np.zeros(1024, dtype=np.float32)
        vec[seed] = 1.0
        return vec


class DummyRunner:
    def run(self, prompt, skill_content=None):
        if skill_content:
            return {"output": "Check Content-Encoding first. If it is gzip, gunzip before JSON.parse."}
        return {"output": "The JSON schema may be malformed; inspect body parser settings."}


class DummyJudge:
    def judge(self, prompt, expected, baseline, with_skill):
        return {
            "winner": "with_skill",
            "baseline_score": 5,
            "with_skill_score": 9,
            "delta": 4,
            "regression": False,
            "reason": "with_skill checks Content-Encoding and gzip before JSON.parse.",
        }


class RegressionJudge:
    def judge(self, prompt, expected, baseline, with_skill):
        return {
            "winner": "baseline",
            "baseline_score": 8,
            "with_skill_score": 6,
            "delta": -2,
            "regression": True,
            "reason": "with_skill over-applied the skill.",
        }


class BilateralSkillEvolutionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="mnemosyne-v71-test-"))
        self.db_path = self.tmp / "graph.db"
        init_db(str(self.db_path))
        self.old_skills_dir = sqlite_store_module._SKILLS_DIR
        sqlite_store_module._SKILLS_DIR = self.tmp / "skills"
        self.store = SQLiteStore(str(self.db_path), embedder=DummyEmbedder())

    def tearDown(self):
        sqlite_store_module._SKILLS_DIR = self.old_skills_dir
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _source_nodes(self, count=3):
        ids = []
        for idx in range(count):
            ids.append(self.store.add_node(
                content=f"gzip JSON source memory {idx}: check Content-Encoding before JSON.parse",
                node_type="experience",
                task_type="api_proxy",
                project="Mnemosyne",
                tags=["gzip", "json"],
                principle=f"Check Content-Encoding before parsing JSON {idx}",
            ))
        return ids

    def _draft_skill(self, status="draft", source_count=3):
        sources = self._source_nodes(source_count)
        skill_id = self.store.create_skill_artifact(
            name="Test isolated gzip body before JSON parse",
            source_node_ids=sources,
            status=status,
            trigger_patterns=["gzip JSON body", "garbled request bytes"],
            preconditions=["HTTP request body parsing fails"],
            procedure=[
                "Inspect request headers before parsing.",
                "If Content-Encoding is gzip, gunzip the body.",
                "Only then call JSON.parse.",
            ],
            verification="Request body parses after gzip decompression.",
            failure_modes=["Do not assume the body is plain JSON."],
            risk_level="low",
        )
        self.store.update_skill_artifact(skill_id, evidence_node_ids=sources)
        return skill_id, sources

    def _add_verification_edges(self, skill_id, count=2):
        for idx in range(count):
            verify_id = self.store.add_node(
                content=f"verification {idx}: gzip skill found Content-Encoding before JSON.parse",
                node_type="skill_feedback",
                task_type="skill_feedback",
                tags=["skill_feedback", "helpful"],
                principle=f"Skill feedback: helpful {idx}",
            )
            self.store.add_edge(skill_id, verify_id, "verified_by", weight=0.9, source="test")

    def test_dry_run_mirror_does_not_promote_draft_to_evolved(self):
        skill_id, _ = self._draft_skill(status="draft")

        try:
            result = SkillMirrorEvolutionPhase().run(self.store, DummyEmbedder())

            artifact = self.store.get_skill_artifact(skill_id)
            self.assertEqual(artifact["status"], "draft")
            self.assertEqual(result["evolved"], 0)
            self.assertIn(skill_id, result["blocked_dry_run_promotions"])
        finally:
            artifact = self.store.get_skill_artifact(skill_id)
            file_path = artifact.get("file_path") if artifact else None
            if file_path:
                mirror = self.tmp / file_path
                if mirror.exists():
                    mirror.unlink()
                parent = mirror.parent
                if parent.exists() and not any(parent.iterdir()):
                    parent.rmdir()

    def test_bilateral_decision_rejects_dry_run_even_with_high_scores(self):
        skill_id, _ = self._draft_skill(status="tested")
        self._add_verification_edges(skill_id, count=3)
        mnemosyne = self.store.score_skill_mnemosyne(skill_id)
        self.assertTrue(mnemosyne["passed"])

        decision = self.store.decide_skill_evolution(
            skill_id,
            darwin_result={
                "passed": True,
                "darwin_score": 95,
                "live_test_delta": 3,
                "regression_count": 0,
                "eval_mode": "dry_run",
            },
            mnemosyne_result=mnemosyne,
        )

        self.assertEqual(decision["decision"], "needs_revision")
        self.assertFalse(decision["darwin_passed"])
        self.assertIn("dry_run_cannot_evolve", decision["decision_reason"])

    def test_bilateral_decision_requires_mnemosyne_pass(self):
        skill_id, _ = self._draft_skill(status="tested", source_count=1)

        decision = self.store.decide_skill_evolution(
            skill_id,
            darwin_result={
                "passed": True,
                "darwin_score": 90,
                "live_test_delta": 2,
                "regression_count": 0,
                "eval_mode": "full_test",
            },
        )

        self.assertEqual(decision["decision"], "needs_revision")
        self.assertTrue(decision["darwin_passed"])
        self.assertFalse(decision["mnemosyne_passed"])

    def test_bilateral_decision_promotes_only_when_both_sides_pass(self):
        skill_id, _ = self._draft_skill(status="tested")
        self._add_verification_edges(skill_id, count=3)
        mnemosyne = self.store.score_skill_mnemosyne(skill_id)

        decision = self.store.decide_skill_evolution(
            skill_id,
            darwin_result={
                "passed": True,
                "darwin_score": 90,
                "live_test_delta": 2,
                "regression_count": 0,
                "eval_mode": "full_test",
            },
            mnemosyne_result=mnemosyne,
        )

        self.assertEqual(decision["decision"], "evolved")
        self.assertTrue(decision["darwin_passed"])
        self.assertTrue(decision["mnemosyne_passed"])
        self.assertEqual(self.store.get_skill_artifact(skill_id)["status"], "evolved")

    def test_failed_bilateral_decision_downgrades_existing_evolved_skill(self):
        skill_id, _ = self._draft_skill(status="evolved")
        self._add_verification_edges(skill_id, count=3)

        decision = self.store.decide_skill_evolution(
            skill_id,
            darwin_result={
                "passed": False,
                "darwin_score": 90,
                "live_test_delta": -1,
                "regression_count": 1,
                "eval_mode": "full_test",
            },
        )

        self.assertEqual(decision["decision"], "needs_revision")
        self.assertEqual(self.store.get_skill_artifact(skill_id)["status"], "needs_revision")

    def test_approval_requires_evolved_status(self):
        skill_id, _ = self._draft_skill(status="draft")
        self._add_verification_edges(skill_id, count=2)

        with self.assertRaisesRegex(ValueError, "must be evolved"):
            self.store.approve_skill(skill_id)

    def test_darwin_evaluation_records_baseline_with_skill_and_judge(self):
        skill_id, _ = self._draft_skill(status="tested")
        self._add_verification_edges(skill_id, count=3)
        self.store.add_skill_test_prompt(
            skill_id,
            "gzip-json-1",
            "A Node.js proxy receives garbled bytes before JSON.parse. What should it check?",
            "Check Content-Encoding and gunzip before parsing JSON.",
            tags=["happy_path"],
        )

        result = self.store.run_skill_darwin_evaluation(skill_id, DummyRunner(), DummyJudge())
        runs = self.store.list_skill_eval_runs(skill_id)

        self.assertEqual(result["decision"]["decision"], "evolved")
        self.assertEqual(len(runs), 1)
        self.assertIn("schema", runs[0]["baseline_output"])
        self.assertIn("Content-Encoding", runs[0]["with_skill_output"])
        self.assertEqual(runs[0]["judge_output"]["winner"], "with_skill")
        self.assertGreater(runs[0]["live_test_delta"], 0)
        self.assertEqual(runs[0]["decision"], "evolved")
        self.assertEqual(runs[0]["kept"], 1)
        self.assertEqual(self.store.get_skill_artifact(skill_id)["status"], "evolved")

    def test_skill_evolution_runner_uses_injected_runners(self):
        skill_id, _ = self._draft_skill(status="tested")
        self._add_verification_edges(skill_id, count=3)
        self.store.add_skill_test_prompt(
            skill_id,
            "gzip-json-1",
            "A Node.js proxy receives garbled bytes before JSON.parse. What should it check?",
            "Check Content-Encoding and gunzip before parsing JSON.",
        )
        runner = ReplayAgentRunner(
            baseline_output="Guess body parser settings first.",
            with_skill_output="Check Content-Encoding and gunzip before JSON.parse.",
        )
        judge = ReplayJudgeRunner({
            "winner": "with_skill",
            "baseline_score": 4,
            "with_skill_score": 9,
            "delta": 5,
            "regression": False,
            "reason": "Injected runner improved the answer.",
        })

        result = SkillEvolutionRunner(self.store, runner, judge).run(skill_id)

        self.assertEqual(result["decision"]["decision"], "evolved")
        self.assertEqual(self.store.list_skill_eval_runs(skill_id)[0]["judge_output"]["winner"], "with_skill")

    def test_darwin_evaluation_regression_does_not_evolve(self):
        skill_id, _ = self._draft_skill(status="tested")
        self._add_verification_edges(skill_id, count=3)
        self.store.add_skill_test_prompt(
            skill_id,
            "gzip-json-1",
            "A Node.js proxy receives garbled bytes before JSON.parse. What should it check?",
            "Check Content-Encoding and gunzip before parsing JSON.",
        )

        result = self.store.run_skill_darwin_evaluation(skill_id, DummyRunner(), RegressionJudge())

        self.assertEqual(result["decision"]["decision"], "needs_revision")
        self.assertFalse(result["darwin"]["passed"])
        self.assertEqual(result["darwin"]["regression_count"], 1)
        self.assertEqual(self.store.list_skill_eval_runs(skill_id)[0]["decision"], "needs_revision")
        self.assertEqual(self.store.list_skill_eval_runs(skill_id)[0]["reverted"], 1)

    def test_sync_skill_test_prompts_file(self):
        skill_id, _ = self._draft_skill(status="draft")
        self.store.add_skill_test_prompt(
            skill_id,
            "gzip-json-1",
            "What should be checked before JSON.parse sees garbled bytes?",
            "Content-Encoding: gzip",
            tags=["smoke"],
        )

        info = None
        try:
            info = self.store.sync_skill_test_prompts_file(skill_id)
            path = Path(info["absolute_path"])
            self.assertTrue(path.exists())
            text = path.read_text(encoding="utf-8")
            self.assertIn("gzip-json-1", text)
            self.assertIn("Content-Encoding", text)
            self.assertEqual(info["count"], 1)
        finally:
            if info:
                path = Path(info["absolute_path"])
                if path.exists():
                    path.unlink()
                parent = path.parent
                if parent.exists() and not any(parent.iterdir()):
                    parent.rmdir()


if __name__ == "__main__":
    unittest.main()

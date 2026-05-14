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
from core.dream_pipeline import SkillLiveEvolutionPhase, SkillMirrorEvolutionPhase, SkillTestPromptGenerationPhase
from core.skill_evolution import SkillEvolutionRunner
from core.runners import ReplayAgentRunner, ReplayJudgeRunner
import skill_daemon


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
        self.store.update_skill_artifact(
            skill_id,
            latest_darwin_score=91,
            latest_mnemosyne_score=88,
            latest_live_test_delta=22,
            latest_eval_mode="full_test",
        )

        try:
            result = SkillMirrorEvolutionPhase().run(self.store, DummyEmbedder())

            artifact = self.store.get_skill_artifact(skill_id)
            self.assertEqual(artifact["status"], "draft")
            self.assertEqual(result["evolved"], 0)
            self.assertEqual(artifact.get("latest_eval_mode"), "full_test")
            self.assertEqual(artifact.get("latest_darwin_score"), 91)
            self.assertIn("latest_format_check", artifact.get("metadata") or {})
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
        self.store.add_skill_test_prompt(
            skill_id,
            "gzip-json-1",
            "A Node.js proxy receives garbled bytes before JSON.parse. What should it check?",
            "Check Content-Encoding and gunzip before parsing JSON.",
        )

        decision = self.store.decide_skill_evolution(
            skill_id,
            darwin_result={
                "passed": True,
                "darwin_score": 90,
                "live_test_delta": 2,
                "regression_count": 0,
                "eval_mode": "full_test",
                "prompt_results": [{"prompt_id": "gzip-json-1"}],
            },
        )

        self.assertEqual(decision["decision"], "needs_revision")
        self.assertTrue(decision["darwin_passed"])
        self.assertFalse(decision["mnemosyne_passed"])

    def test_bilateral_decision_promotes_only_when_both_sides_pass(self):
        skill_id, _ = self._draft_skill(status="tested")
        self._add_verification_edges(skill_id, count=3)
        self.store.add_skill_test_prompt(
            skill_id,
            "gzip-json-1",
            "A Node.js proxy receives garbled bytes before JSON.parse. What should it check?",
            "Check Content-Encoding and gunzip before parsing JSON.",
        )
        mnemosyne = self.store.score_skill_mnemosyne(skill_id)

        decision = self.store.decide_skill_evolution(
            skill_id,
            darwin_result={
                "passed": True,
                "darwin_score": 90,
                "live_test_delta": 2,
                "regression_count": 0,
                "eval_mode": "full_test",
                "prompt_results": [{"prompt_id": "gzip-json-1"}],
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
        self.store.add_skill_test_prompt(
            skill_id,
            "gzip-json-1",
            "A Node.js proxy receives garbled bytes before JSON.parse. What should it check?",
            "Check Content-Encoding and gunzip before parsing JSON.",
        )

        decision = self.store.decide_skill_evolution(
            skill_id,
            darwin_result={
                "passed": False,
                "darwin_score": 90,
                "live_test_delta": -1,
                "regression_count": 1,
                "eval_mode": "full_test",
                "prompt_results": [{"prompt_id": "gzip-json-1"}],
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

    def test_full_test_rejects_auto_smoke_only_prompt(self):
        skill_id, _ = self._draft_skill(status="tested")
        self._add_verification_edges(skill_id, count=3)
        self.store.add_skill_test_prompt(
            skill_id,
            "auto-smoke",
            "Use the skill Test isolated gzip body before JSON parse on a matching task.",
            "Request body parses after gzip decompression.",
            tags=["auto", "smoke"],
        )

        with self.assertRaisesRegex(ValueError, "real active test prompt"):
            self.store.run_skill_darwin_evaluation(skill_id, DummyRunner(), DummyJudge(), eval_mode="full_test")

    def test_replay_smoke_cannot_update_real_governance_scores(self):
        skill_id, _ = self._draft_skill(status="tested")
        self._add_verification_edges(skill_id, count=3)
        self.store.add_skill_test_prompt(
            skill_id,
            "auto-smoke",
            "Use the skill Test isolated gzip body before JSON parse on a matching task.",
            "Request body parses after gzip decompression.",
            tags=["auto", "smoke"],
        )

        result = self.store.run_skill_darwin_evaluation(
            skill_id,
            DummyRunner(),
            DummyJudge(),
            eval_mode="replay_smoke",
        )
        artifact = self.store.get_skill_artifact(skill_id)

        self.assertEqual(result["decision"]["decision"], "needs_revision")
        self.assertFalse(result["darwin"]["passed"])
        self.assertIn("replay_smoke_cannot_evolve", result["decision"]["decision_reason"])
        self.assertEqual(artifact.get("status"), "tested")
        self.assertEqual(artifact.get("review_status"), "tested")
        self.assertIsNone(artifact.get("latest_darwin_score"))
        self.assertIsNone(artifact.get("latest_live_test_delta"))
        self.assertEqual(artifact.get("metadata", {}).get("latest_non_governing_eval", {}).get("eval_mode"), "replay_smoke")

    def test_grounded_llm_prompt_is_real_evidence_after_hard_validation(self):
        skill_id, _ = self._draft_skill(status="tested")
        self.store.add_skill_test_prompt(
            skill_id,
            "llm-candidate-1",
            "A proxy receives gzip bytes but JSON.parse sees mojibake. Diagnose the fix.",
            "Answer checks Content-Encoding and gunzips before JSON.parse.",
            tags=["llm_generated", "grounded", "auto_full_test"],
            status="active",
            metadata={"grounding_node_ids": ["source-1"]},
        )

        prompts = self.store.list_real_skill_test_prompts(skill_id)
        self.assertEqual(prompts[0]["prompt_id"], "llm-candidate-1")
        self.assertEqual(prompts[0]["metadata"]["grounding_node_ids"], ["source-1"])

    def test_llm_generated_prompt_without_grounding_is_not_real_evidence(self):
        skill_id, _ = self._draft_skill(status="tested")
        self.store.add_skill_test_prompt(
            skill_id,
            "llm-candidate-1",
            "A proxy receives gzip bytes but JSON.parse sees mojibake. Diagnose the fix.",
            "Answer checks Content-Encoding and gunzips before JSON.parse.",
            tags=["llm_generated", "grounded", "auto_full_test"],
            status="active",
        )

        self.assertEqual(self.store.list_real_skill_test_prompts(skill_id), [])

    def test_prompt_metadata_is_synced_to_test_prompts_file(self):
        skill_id, _ = self._draft_skill(status="draft")
        self.store.add_skill_test_prompt(
            skill_id,
            "llm-candidate-1",
            "A proxy receives gzip bytes but JSON.parse sees mojibake. Diagnose the fix.",
            "Answer checks Content-Encoding and gunzips before JSON.parse.",
            tags=["llm_generated", "grounded", "auto_full_test"],
            metadata={"grounding_node_ids": ["source-1"]},
        )

        info = self.store.sync_skill_test_prompts_file(skill_id)
        path = Path(info["absolute_path"])
        try:
            text = path.read_text(encoding="utf-8")
            self.assertIn("grounding_node_ids", text)
            self.assertIn("source-1", text)
        finally:
            if path.exists():
                path.unlink()
            if path.parent.exists() and not any(path.parent.iterdir()):
                path.parent.rmdir()

    def test_verification_evidence_keeps_prompt_grounding_metadata(self):
        skill_id, _ = self._draft_skill(status="tested")
        self._add_verification_edges(skill_id, count=3)
        self.store.add_skill_test_prompt(
            skill_id,
            "llm-candidate-1",
            "A proxy receives gzip bytes but JSON.parse sees mojibake. Diagnose the fix.",
            "Answer checks Content-Encoding and gunzips before JSON.parse.",
            tags=["llm_generated", "grounded", "auto_full_test"],
            metadata={"grounding_node_ids": ["source-1"]},
        )

        result = self.store.run_skill_darwin_evaluation(skill_id, DummyRunner(), DummyJudge())
        evidence_id = result["darwin"].get("verification_evidence_id")
        evidence = self.store.get_node(evidence_id)

        prompt_results = evidence["metadata"]["prompt_results"]
        self.assertEqual(prompt_results[0]["prompt_metadata"]["grounding_node_ids"], ["source-1"])

    def test_score_skill_mnemosyne_is_pure_by_default(self):
        skill_id, _ = self._draft_skill(status="tested")

        result = self.store.score_skill_mnemosyne(skill_id)
        artifact = self.store.get_skill_artifact(skill_id)

        self.assertIn("mnemosyne_score", result)
        self.assertIsNone(artifact.get("mnemosyne_score"))

    def test_score_skill_mnemosyne_can_persist_when_explicit(self):
        skill_id, _ = self._draft_skill(status="tested")

        result = self.store.score_skill_mnemosyne(skill_id, persist=True)
        artifact = self.store.get_skill_artifact(skill_id)

        self.assertEqual(artifact.get("mnemosyne_score"), result["mnemosyne_score"])

    def test_needs_revision_requeues_when_real_prompt_is_newer_than_eval(self):
        skill_id, _ = self._draft_skill(status="needs_revision")
        self.store.add_skill_test_prompt(
            skill_id,
            "gzip-json-1",
            "A Node.js proxy receives garbled bytes before JSON.parse. What should it check?",
            "Check Content-Encoding and gunzip before parsing JSON.",
        )
        self.store.record_skill_eval_run(skill_id, prompt_id="gzip-json-1", eval_mode="full_test")
        self.store.update_skill_artifact(skill_id, latest_eval_mode="full_test")
        self.store.add_skill_test_prompt(
            skill_id,
            "gzip-json-2",
            "A proxy body is gzip-compressed but parsing assumes plain JSON. What should be done?",
            "Gunzip according to Content-Encoding before JSON.parse.",
        )

        artifact = self.store.get_skill_artifact(skill_id)
        self.assertTrue(skill_daemon._should_requeue_needs_revision(self.store, artifact))

    def test_live_evolution_phase_consumes_grounded_prompts_immediately(self):
        skill_id, _ = self._draft_skill(status="tested")
        self._add_verification_edges(skill_id, count=3)
        self.store.add_skill_test_prompt(
            skill_id,
            "llm-candidate-1",
            "A proxy receives gzip bytes but JSON.parse sees mojibake. Diagnose the fix.",
            "Answer checks Content-Encoding and gunzips before JSON.parse.",
            tags=["llm_generated", "grounded", "auto_full_test"],
            metadata={"grounding_node_ids": ["source-1"]},
        )
        self.store.update_skill_artifact(skill_id, metadata={"needs_real_darwin_test": True})

        result = SkillLiveEvolutionPhase().run(self.store, DummyEmbedder())
        artifact = self.store.get_skill_artifact(skill_id)

        self.assertEqual(result["evaluated"], 1)
        self.assertIn(result["evolved"], (0, 1))
        self.assertIn(result["needs_revision"], (0, 1))
        self.assertEqual(artifact["latest_eval_mode"], "full_test")
        self.assertIn(artifact["metadata"].get("last_full_test_decision"), {"evolved", "needs_revision"})

    def test_llm_prompt_validation_requires_baseline_and_improvement(self):
        valid, error = SkillTestPromptGenerationPhase._validate_prompts({
            "prompts": [
                {
                    "prompt": "A Node.js proxy receives garbled gzip bytes before JSON.parse. What should be checked?",
                    "expected": "It checks Content-Encoding and gunzips before parsing.",
                    "baseline_expected_failure": "A generic answer inspects only schema or parser options.",
                    "with_skill_expected_improvement": "The skill forces Content-Encoding inspection before parsing.",
                    "grounding_node_ids": ["source-1"],
                    "risk_tags": ["gzip"],
                },
                {
                    "prompt": "Use the skill on a matching task.",
                    "expected": "too generic",
                    "baseline_expected_failure": "none",
                    "with_skill_expected_improvement": "none",
                },
            ]
        })

        self.assertIsNone(error)
        self.assertEqual(len(valid), 1)
        self.assertEqual(valid[0]["risk_tags"], ["gzip"])

    def test_llm_prompt_validation_can_require_source_grounding(self):
        valid, error = SkillTestPromptGenerationPhase._validate_prompts({
            "prompts": [
                {
                    "prompt": "A Node.js proxy receives garbled gzip bytes before JSON.parse. What should be checked?",
                    "expected": "It checks Content-Encoding and gunzips before parsing.",
                    "baseline_expected_failure": "A generic answer inspects only schema or parser options.",
                    "with_skill_expected_improvement": "The skill forces Content-Encoding inspection before parsing.",
                    "grounding_node_ids": ["source-1"],
                },
                {
                    "prompt": "An unrelated task with no source grounding.",
                    "expected": "Something unrelated.",
                    "baseline_expected_failure": "Unknown.",
                    "with_skill_expected_improvement": "Unknown.",
                    "grounding_node_ids": ["other"],
                },
            ]
        }, source_node_ids=["source-1"])

        self.assertIsNone(error)
        self.assertEqual(len(valid), 1)
        self.assertEqual(valid[0]["grounding_node_ids"], ["source-1"])

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

import json
import shutil
import sqlite3
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
import mcp_server


class DummyEmbedder:
    def get_dimension(self):
        return 1024

    def encode(self, text):
        seed = abs(hash(text)) % 1024
        vec = np.zeros(1024, dtype=np.float32)
        vec[seed] = 1.0
        return vec


class SkillEvidenceFlowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="mnemosyne-v72-test-"))
        self.db_path = self.tmp / "graph.db"
        init_db(str(self.db_path))
        self.old_skills_dir = sqlite_store_module._SKILLS_DIR
        sqlite_store_module._SKILLS_DIR = self.tmp / "skills"
        self.store = SQLiteStore(str(self.db_path), embedder=DummyEmbedder())

    def tearDown(self):
        sqlite_store_module._SKILLS_DIR = self.old_skills_dir
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _source_nodes(self):
        return [
            self.store.add_node(
                content=f"skill evidence source {idx}",
                node_type="experience",
                task_type="skill_memory",
                tags=["skill"],
                principle=f"skill evidence principle {idx}",
            )
            for idx in range(2)
        ]

    def _skill(self, status="evolved", trial_enabled=1):
        skill_id = self.store.create_skill_artifact(
            name="Evidence Flow Skill",
            source_node_ids=self._source_nodes(),
            status=status,
            trigger_patterns=["evidence feedback"],
            procedure=["Use evidence", "Record result"],
            verification="Evidence is written back.",
            risk_level="low",
        )
        self.store.update_skill_artifact(skill_id, trial_enabled=trial_enabled, requires_feedback=1)
        return skill_id

    def _usage_rows(self, skill_id):
        conn = sqlite3.connect(str(self.db_path))
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM skill_usage_feedback WHERE skill_id=?", (skill_id,))
            keys = [d[0] for d in cur.description]
            return [dict(zip(keys, row)) for row in cur.fetchall()]
        finally:
            conn.close()

    def _edges(self, skill_id, relation):
        conn = sqlite3.connect(str(self.db_path))
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT relation_type, weight FROM edges WHERE from_id=? AND relation_type=?",
                (skill_id, relation),
            )
            return cur.fetchall()
        finally:
            conn.close()

    def test_success_creates_structured_row_and_verified_by(self):
        skill_id = self._skill()

        result = self.store.skill_feedback(skill_id, outcome="success", task_context="task", used_as="trial")

        rows = self._usage_rows(skill_id)
        self.assertEqual(rows[0]["outcome"], "success")
        self.assertEqual(rows[0]["feedback_node_id"], result["feedback_id"])
        self.assertEqual(self._edges(skill_id, "verified_by")[0][1], 0.7)
        artifact = self.store.get_skill_artifact(skill_id)
        self.assertEqual(artifact["trial_count"], 1)
        self.assertEqual(artifact["trial_success_count"], 1)

    def test_legacy_helpful_maps_to_success(self):
        skill_id = self._skill()

        result = self.store.skill_feedback(skill_id, rating="helpful", task_context="task", used_as="trial")

        self.assertEqual(result["outcome"], "success")
        self.assertEqual(self._usage_rows(skill_id)[0]["outcome"], "success")
        self.assertEqual(self._usage_rows(skill_id)[0]["rating"], "helpful")

    def test_partial_needs_revision_without_failure_counter(self):
        skill_id = self._skill()

        self.store.skill_feedback(skill_id, outcome="partial", task_context="task", used_as="trial")

        self.assertEqual(self._edges(skill_id, "needs_revision")[0][1], 0.7)
        artifact = self.store.get_skill_artifact(skill_id)
        self.assertEqual(artifact["trial_count"], 1)
        self.assertEqual(artifact["trial_failure_count"], 0)
        self.assertEqual(artifact["needs_revision"], 1)

    def test_miss_creates_fails_on_and_test_prompt(self):
        skill_id = self._skill()

        result = self.store.skill_feedback(
            skill_id,
            outcome="miss",
            task_context="A task the skill missed.",
            verification_result="Expected repaired behavior.",
            used_as="trial",
            create_test_prompt=True,
        )

        self.assertEqual(self._edges(skill_id, "fails_on")[0][1], 0.7)
        artifact = self.store.get_skill_artifact(skill_id)
        self.assertEqual(artifact["trial_failure_count"], 1)
        self.assertTrue(result["created_prompt_id"])
        prompts = self.store.list_skill_test_prompts(skill_id)
        self.assertEqual(prompts[0]["prompt"], "A task the skill missed.")
        self.assertIn("regression", prompts[0]["tags"])
        self.assertEqual(self.store.list_real_skill_test_prompts(skill_id)[0]["prompt"], "A task the skill missed.")
        path = sqlite_store_module._SKILLS_DIR / artifact["slug"] / "test-prompts.json"
        self.assertTrue(path.exists())

    def test_misleading_high_weight_fails_on_and_disables_trial(self):
        skill_id = self._skill(trial_enabled=1)

        self.store.skill_feedback(skill_id, outcome="misleading", task_context="bad advice", used_as="trial")

        self.assertEqual(self._edges(skill_id, "fails_on")[0][1], 0.9)
        artifact = self.store.get_skill_artifact(skill_id)
        self.assertEqual(artifact["trial_failure_count"], 1)
        self.assertEqual(artifact["trial_enabled"], 0)

    def test_trigger_mismatch_metadata_and_needs_revision(self):
        skill_id = self._skill()

        self.store.skill_feedback(skill_id, outcome="trigger_mismatch", task_context="wrong trigger", used_as="trial")

        self.assertEqual(self._edges(skill_id, "needs_revision")[0][1], 0.8)
        artifact = self.store.get_skill_artifact(skill_id)
        self.assertEqual(artifact["trial_failure_count"], 1)
        self.assertEqual(artifact["needs_revision"], 1)
        self.assertEqual(artifact["metadata"]["usage_loop"]["trigger_mismatch_count"], 1)

    def test_approved_usage_does_not_increment_trial_counters(self):
        skill_id = self._skill(status="approved", trial_enabled=0)
        self.store.update_skill_artifact(skill_id, inject_enabled=1, requires_feedback=0)

        self.store.skill_feedback(skill_id, outcome="success", task_context="approved use", used_as="approved")

        artifact = self.store.get_skill_artifact(skill_id)
        self.assertEqual(artifact["trial_count"], 0)
        self.assertEqual(artifact["trial_success_count"], 0)
        self.assertEqual(self._usage_rows(skill_id)[0]["used_as"], "approved")

    def test_empty_task_context_does_not_create_prompt(self):
        skill_id = self._skill()

        result = self.store.skill_feedback(skill_id, outcome="miss", used_as="trial", create_test_prompt=True)

        self.assertIsNone(result["created_prompt_id"])
        self.assertEqual(self.store.list_skill_test_prompts(skill_id), [])

    def test_failure_triggered_audit_can_downgrade_approved_skill(self):
        skill_id = self._skill(status="approved", trial_enabled=0)
        self.store.update_skill_artifact(skill_id, inject_enabled=1, requires_feedback=0)

        audit = self.store.should_audit_skill(skill_id, trigger="failure")
        self.assertTrue(audit["audit_required"])
        self.assertEqual(audit["priority"], "high")

        result = self.store.record_skill_audit(skill_id, {"passed": False, "reason": "bad audit"}, trigger="failure")
        artifact = self.store.get_skill_artifact(skill_id)
        self.assertEqual(result["decision"], "needs_revision")
        self.assertEqual(artifact["status"], "needs_revision")
        self.assertEqual(artifact["review_status"], "needs_revision")
        self.assertEqual(artifact["inject_enabled"], 0)
        self.assertEqual(artifact["needs_revision"], 1)
        self.assertEqual(artifact["metadata"]["usage_loop"]["last_audit_trigger"], "failure")

    def test_unsafe_audit_deprecates_skill(self):
        skill_id = self._skill(status="approved", trial_enabled=0)
        self.store.update_skill_artifact(skill_id, inject_enabled=1, requires_feedback=0)

        result = self.store.record_skill_audit(skill_id, {"passed": False, "reason": "unsafe", "unsafe": True}, trigger="failure")
        artifact = self.store.get_skill_artifact(skill_id)
        self.assertEqual(result["decision"], "deprecated")
        self.assertEqual(artifact["status"], "deprecated")
        self.assertEqual(artifact["review_status"], "deprecated")
        self.assertEqual(artifact["inject_enabled"], 0)

    def test_mcp_skill_feedback_accepts_outcome_and_prompt_fields(self):
        skill_id = self._skill()
        old_get_store = mcp_server._get_store
        mcp_server._get_store = lambda: self.store
        try:
            text = mcp_server._handle_skill_feedback({
                "skill_id": skill_id,
                "outcome": "miss",
                "task_context": "MCP missed case",
                "verification_result": "Expected MCP write-back",
                "create_test_prompt": True,
                "prompt_tags": ["mcp"],
            })
        finally:
            mcp_server._get_store = old_get_store

        self.assertIn('"outcome": "miss"', text)
        prompts = self.store.list_skill_test_prompts(skill_id)
        self.assertEqual(prompts[0]["prompt"], "MCP missed case")
        self.assertIn("mcp", prompts[0]["tags"])

    def test_negative_context_does_not_trigger_encoding_skill(self):
        output = self.store.inject_skills(
            "测试 OpenCode 是否会用 MCP。当前任务不涉及 SQLite、PowerShell、中文乱码或 mojibake。",
            mode="default",
        )
        self.assertEqual(output, "")


if __name__ == "__main__":
    unittest.main()

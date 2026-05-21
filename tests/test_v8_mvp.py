import json
import sqlite3
import sys
import tempfile
import unittest
import shutil
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V8_SRC = ROOT / "v8" / "src"
V8_SCRIPTS = ROOT / "v8" / "scripts"
if str(V8_SRC) not in sys.path:
    sys.path.insert(0, str(V8_SRC))
if str(V8_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(V8_SCRIPTS))

from v8_memory.context import ContextPackBuilder
from v8_memory.cli import main as cli_main
from v8_memory.gates import ReadGate, WriteGate
from v8_memory.lifecycle import LifecycleManager
from v8_memory.services import CandidateWriter, EvidenceRecorder, EventWriter
from v8_memory.store import SQLiteV8Store
import functional_smoke


class V8MVPTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="mnemosyne-v8-test-"))
        self.db = self.tmp / "v8.db"
        self.store = SQLiteV8Store(self.db)
        self.events = EventWriter(self.store)
        self.candidates = CandidateWriter(self.store)
        self.evidence = EvidenceRecorder(self.store)
        self.lifecycle = LifecycleManager(self.store)
        self.context = ContextPackBuilder(self.store, ReadGate())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _memory_rows(self):
        conn = sqlite3.connect(self.db)
        try:
            conn.row_factory = sqlite3.Row
            return [dict(row) for row in conn.execute("SELECT * FROM memories")]
        finally:
            conn.close()

    def test_candidate_without_evidence_cannot_promote(self):
        event_id = self.events.add(
            event_type="tool_error",
            actor="agent",
            content="PowerShell rejected Bash heredoc syntax.",
            scope={"project_id": "memory-evolution", "session_id": "s1"},
        )
        cand_id = self.candidates.add(
            candidate_type="claim",
            content="PowerShell does not support Bash heredoc.",
            source_event_ids=[event_id],
            scope={"project_id": "memory-evolution", "session_id": "s1"},
            trigger="running inline commands in PowerShell",
        )

        with self.assertRaises(ValueError):
            self.lifecycle.promote(cand_id)

    def test_candidate_with_supporting_evidence_promotes(self):
        event_id = self.events.add(
            event_type="tool_error",
            actor="agent",
            content="PowerShell rejected Bash heredoc syntax.",
            scope={"project_id": "memory-evolution", "session_id": "s1"},
        )
        cand_id = self.candidates.add(
            candidate_type="claim",
            content="PowerShell does not support Bash heredoc.",
            source_event_ids=[event_id],
            scope={"project_id": "memory-evolution", "session_id": "s1"},
            trigger="running inline commands in PowerShell",
        )
        self.evidence.add(
            target_type="candidate",
            target_id=cand_id,
            evidence_type="task_success",
            polarity="supports",
            content="Switching to a PowerShell-compatible command avoided the failure.",
            source_event_ids=[event_id],
        )

        memory_id = self.lifecycle.promote(cand_id)
        rows = self._memory_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], memory_id)
        self.assertEqual(rows[0]["status"], "validated")
        self.assertEqual(rows[0]["memory_type"], "claim")

    def test_context_pack_blocks_out_of_scope_memory(self):
        event_id = self.events.add(
            event_type="tool_error",
            actor="agent",
            content="PowerShell rejected Bash heredoc syntax.",
            scope={"project_id": "memory-evolution", "session_id": "s1"},
        )
        cand_id = self.candidates.add(
            candidate_type="claim",
            content="PowerShell does not support Bash heredoc.",
            source_event_ids=[event_id],
            scope={"project_id": "memory-evolution", "session_id": "s1"},
            trigger="running inline commands in PowerShell",
        )
        self.evidence.add(
            target_type="candidate",
            target_id=cand_id,
            evidence_type="task_success",
            polarity="supports",
            content="Switching to a PowerShell-compatible command avoided the failure.",
            source_event_ids=[event_id],
        )
        self.lifecycle.promote(cand_id)

        allowed = self.context.build(
            task="debug PowerShell inline command",
            scope={"project_id": "memory-evolution"},
        )
        blocked = self.context.build(
            task="debug PowerShell inline command",
            scope={"project_id": "other-project"},
        )

        self.assertEqual(len(allowed["items"]), 1)
        self.assertEqual(len(blocked["items"]), 0)
        self.assertTrue(any(item["reason"] == "scope_mismatch" for item in blocked["rejected"]))

    def test_procedural_candidate_needs_procedural_evidence(self):
        event_id = self.events.add(
            event_type="assistant_note",
            actor="agent",
            content="Maybe skip validation to save time.",
            scope={"project_id": "memory-evolution", "session_id": "s2"},
        )
        cand_id = self.candidates.add(
            candidate_type="procedure",
            content="Always skip validation when the command looks safe.",
            source_event_ids=[event_id],
            scope={"project_id": "memory-evolution", "session_id": "s2"},
            trigger="command execution",
            risk="high",
        )
        self.evidence.add(
            target_type="candidate",
            target_id=cand_id,
            evidence_type="task_success",
            polarity="supports",
            content="The shortcut seemed to work once.",
            source_event_ids=[event_id],
        )

        with self.assertRaises(ValueError):
            self.lifecycle.promote(cand_id)

    def test_write_gate_reason_codes_cover_missing_and_contradicting_cases(self):
        event_id = self.events.add(
            event_type="tool_error",
            actor="agent",
            content="PowerShell rejected Bash heredoc syntax.",
            scope={"project_id": "memory-evolution", "session_id": "w1"},
        )
        cand_id = self.candidates.add(
            candidate_type="claim",
            content="PowerShell does not support Bash heredoc.",
            source_event_ids=[event_id],
            scope={"project_id": "memory-evolution", "session_id": "w1"},
            trigger="running inline commands in PowerShell",
        )
        self.evidence.add(
            target_type="candidate",
            target_id=cand_id,
            evidence_type="task_success",
            polarity="supports",
            content="Switching to a PowerShell-compatible command avoided the failure.",
            source_event_ids=[event_id],
        )
        candidate = self.store.get("candidates", cand_id)
        gate = WriteGate(self.store)

        ok, reasons = gate.check_promote(candidate)
        self.assertTrue(ok)
        self.assertEqual(reasons, [])

        no_source = dict(candidate)
        no_source["source_event_ids_json"] = json.dumps([])
        ok, reasons = gate.check_promote(no_source)
        self.assertFalse(ok)
        self.assertIn("missing_source", reasons)

        no_scope = dict(candidate)
        no_scope["scope_json"] = json.dumps({})
        ok, reasons = gate.check_promote(no_scope)
        self.assertFalse(ok)
        self.assertIn("missing_scope", reasons)

        no_support = dict(candidate)
        conn = sqlite3.connect(self.db)
        try:
            conn.execute("DELETE FROM evidence WHERE target_id=?", (cand_id,))
            conn.commit()
        finally:
            conn.close()
        ok, reasons = gate.check_promote(no_support)
        self.assertFalse(ok)
        self.assertIn("missing_supporting_evidence", reasons)

        self.evidence.add(
            target_type="candidate",
            target_id=cand_id,
            evidence_type="task_success",
            polarity="supports",
            content="Switching to a PowerShell-compatible command avoided the failure.",
            source_event_ids=[event_id],
        )
        self.evidence.add(
            target_type="candidate",
            target_id=cand_id,
            evidence_type="task_failure",
            polarity="contradicts",
            content="The shortcut failed under a different shell.",
            source_event_ids=[event_id],
        )
        ok, reasons = gate.check_promote(self.store.get("candidates", cand_id))
        self.assertFalse(ok)
        self.assertIn("contradicting_evidence", reasons)

    def test_write_gate_rejects_procedural_candidates_without_procedural_evidence(self):
        event_id = self.events.add(
            event_type="assistant_note",
            actor="agent",
            content="Maybe skip validation to save time.",
            scope={"project_id": "memory-evolution", "session_id": "w2"},
        )
        cand_id = self.candidates.add(
            candidate_type="procedure",
            content="Always skip validation when the command looks safe.",
            source_event_ids=[event_id],
            scope={"project_id": "memory-evolution", "session_id": "w2"},
            trigger="command execution",
            risk="high",
        )
        self.evidence.add(
            target_type="candidate",
            target_id=cand_id,
            evidence_type="task_success",
            polarity="supports",
            content="The shortcut seemed to work once.",
            source_event_ids=[event_id],
        )

        ok, reasons = WriteGate(self.store).check_promote(self.store.get("candidates", cand_id))
        self.assertFalse(ok)
        self.assertIn("missing_procedural_evidence", reasons)

    def test_read_gate_reason_codes_cover_default_blocks(self):
        gate = ReadGate()

        ok, reason = gate.check(
            {
                "freshness": 0.0,
                "status": "validated",
                "risk": "low",
                "scope_json": json.dumps({"project_id": "memory-evolution"}),
                "trigger": "debug PowerShell inline command",
                "content": "PowerShell does not support Bash heredoc.",
            },
            task="debug PowerShell inline command",
            scope={"project_id": "memory-evolution"},
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "stale")

        ok, reason = gate.check(
            {
                "freshness": 1.0,
                "status": "demoted",
                "risk": "low",
                "scope_json": json.dumps({"project_id": "memory-evolution"}),
                "trigger": "debug PowerShell inline command",
                "content": "PowerShell does not support Bash heredoc.",
            },
            task="debug PowerShell inline command",
            scope={"project_id": "memory-evolution"},
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "status_blocked")

        ok, reason = gate.check(
            {
                "freshness": 1.0,
                "status": "validated",
                "risk": "high",
                "scope_json": json.dumps({"project_id": "memory-evolution"}),
                "trigger": "debug PowerShell inline command",
                "content": "PowerShell does not support Bash heredoc.",
            },
            task="debug PowerShell inline command",
            scope={"project_id": "memory-evolution"},
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "risk_blocked")

        ok, reason = gate.check(
            {
                "freshness": 1.0,
                "status": "validated",
                "risk": "low",
                "scope_json": json.dumps({"project_id": "memory-evolution"}),
                "trigger": "unrelated trigger",
                "content": "PowerShell does not support Bash heredoc.",
            },
            task="compile python files",
            scope={"project_id": "memory-evolution"},
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "no_task_match")

        ok, reason = gate.check(
            {
                "freshness": 1.0,
                "status": "validated",
                "risk": "low",
                "scope_json": json.dumps({"project_id": "memory-evolution"}),
                "trigger": "debug PowerShell inline command",
                "content": "PowerShell does not support Bash heredoc.",
            },
            task="debug PowerShell inline command",
            scope={"project_id": "other-project"},
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "scope_mismatch")

    def test_stale_memory_not_injected_by_default(self):
        event_id = self.events.add(
            event_type="tool_error",
            actor="agent",
            content="PowerShell rejected Bash heredoc syntax.",
            scope={"project_id": "memory-evolution", "session_id": "s1"},
        )
        cand_id = self.candidates.add(
            candidate_type="claim",
            content="PowerShell does not support Bash heredoc.",
            source_event_ids=[event_id],
            scope={"project_id": "memory-evolution", "session_id": "s1"},
            trigger="running inline commands in PowerShell",
        )
        self.evidence.add(
            target_type="candidate",
            target_id=cand_id,
            evidence_type="task_success",
            polarity="supports",
            content="Switching to a PowerShell-compatible command avoided the failure.",
            source_event_ids=[event_id],
        )
        memory_id = self.lifecycle.promote(cand_id)
        self.lifecycle.mark_stale(memory_id)

        pack = self.context.build(
            task="debug PowerShell inline command",
            scope={"project_id": "memory-evolution"},
        )

        self.assertEqual(len(pack["items"]), 0)
        self.assertTrue(any(item["reason"] == "stale" for item in pack["rejected"]))

    def test_cli_smoke_flow_builds_context_pack(self):
        db_arg = ["--db", str(self.db)]

        event = self._run_cli(
            db_arg
            + [
                "event",
                "add",
                "--type",
                "tool_error",
                "--actor",
                "agent",
                "--content",
                "PowerShell rejected Bash heredoc syntax.",
                "--scope-item",
                "project_id=memory-evolution",
                "--scope-item",
                "session_id=cli",
            ]
        )
        candidate = self._run_cli(
            db_arg
            + [
                "candidate",
                "add",
                "--type",
                "claim",
                "--content",
                "PowerShell does not support Bash heredoc.",
                "--sources",
                event["id"],
                "--scope-item",
                "project_id=memory-evolution",
                "--scope-item",
                "session_id=cli",
                "--trigger",
                "debug PowerShell inline command",
            ]
        )
        self._run_cli(
            db_arg
            + [
                "evidence",
                "add",
                "--target",
                candidate["id"],
                "--type",
                "task_success",
                "--polarity",
                "supports",
                "--content",
                "Using a PowerShell-compatible command fixed the issue.",
                "--sources",
                event["id"],
            ]
        )
        memory = self._run_cli(db_arg + ["lifecycle", "promote", "--candidate", candidate["id"]])
        pack = self._run_cli(
            db_arg
            + [
                "context",
                "build",
                "--task",
                "debug PowerShell inline command",
                "--scope-item",
                "project_id=memory-evolution",
            ]
        )

        self.assertEqual(pack["items"][0]["id"], memory["id"])
        self.assertEqual(pack["items"][0]["content"], "PowerShell does not support Bash heredoc.")
        self.assertEqual(pack["items"][0]["source_events"][0]["id"], event["id"])
        self.assertEqual(pack["items"][0]["source_events"][0]["event_type"], "tool_error")
        self.assertEqual(pack["items"][0]["evidence"][0]["type"], "task_success")
        self.assertEqual(pack["items"][0]["evidence"][0]["polarity"], "supports")
        self.assertEqual(pack["items"][0]["evidence"][0]["source_event_ids"], [event["id"]])

    def test_cli_error_returns_json(self):
        result, code = self._run_cli_raw(
            [
                "--db",
                str(self.db),
                "candidate",
                "add",
                "--type",
                "claim",
                "--content",
                "No source should fail.",
                "--sources",
                "missing-event",
                "--scope-item",
                "project_id=memory-evolution",
                "--trigger",
                "missing source",
            ]
        )

        self.assertEqual(code, 1)
        self.assertEqual(result["type"], "ValueError")
        self.assertIn("source RawEvent not found", result["error"])

    def test_cli_lifecycle_demote_blocks_memory(self):
        memory_id = self._promoted_claim_memory()

        result = self._run_cli(["--db", str(self.db), "lifecycle", "demote", "--memory", memory_id])
        pack = self.context.build(
            task="debug PowerShell inline command",
            scope={"project_id": "memory-evolution"},
        )

        self.assertEqual(result["id"], memory_id)
        self.assertEqual(len(pack["items"]), 0)
        self.assertTrue(any(item["reason"] == "status_blocked" for item in pack["rejected"]))

    def test_cli_lifecycle_stale_blocks_memory_as_stale(self):
        memory_id = self._promoted_claim_memory()

        result = self._run_cli(["--db", str(self.db), "lifecycle", "stale", "--memory", memory_id])
        pack = self.context.build(
            task="debug PowerShell inline command",
            scope={"project_id": "memory-evolution"},
        )

        self.assertEqual(result["id"], memory_id)
        self.assertEqual(len(pack["items"]), 0)
        self.assertTrue(any(item["reason"] == "stale" for item in pack["rejected"]))

    def test_cli_inspection_commands_decode_json_fields(self):
        memory_id = self._promoted_claim_memory()

        memory = self._run_cli(["--db", str(self.db), "memory", "get", "--id", memory_id])
        memories = self._run_cli(["--db", str(self.db), "memory", "list"])
        events = self._run_cli(["--db", str(self.db), "event", "list"])
        context = self.context.build(
            task="debug PowerShell inline command",
            scope={"project_id": "memory-evolution"},
        )
        run = self._run_cli(["--db", str(self.db), "context", "get", "--id", context["id"]])

        self.assertEqual(memory["id"], memory_id)
        self.assertEqual(memory["scope"]["project_id"], "memory-evolution")
        self.assertEqual(memories["items"][0]["id"], memory_id)
        self.assertEqual(events["items"][0]["event_type"], "tool_error")
        self.assertEqual(run["selected"][0]["id"], memory_id)
        self.assertEqual(run["selected"][0]["source_events"][0]["event_type"], "tool_error")
        self.assertEqual(run["selected"][0]["evidence"][0]["polarity"], "supports")

    def test_cli_evidence_list_can_filter_by_target(self):
        memory_id = self._promoted_claim_memory()
        memory = self.store.get("memories", memory_id)

        evidence = self._run_cli(
            [
                "--db",
                str(self.db),
                "evidence",
                "list",
                "--target-type",
                "candidate",
                "--target",
                memory["candidate_id"],
            ]
        )

        self.assertEqual(len(evidence["items"]), 1)
        self.assertEqual(evidence["items"][0]["polarity"], "supports")

    def test_real_scenario_functional_smoke(self):
        result = functional_smoke.run(self.tmp / "functional.db")

        self.assertEqual(result["context"]["items"][0]["id"], result["memory_id"])
        self.assertEqual(result["context"]["items"][0]["source_events"][0]["event_type"], "tool_error")
        self.assertEqual(result["context"]["items"][0]["evidence"][0]["type"], "task_success")
        self.assertEqual(result["context"]["items"][0]["evidence"][0]["source_event_ids"], [result["event_id"]])
        self.assertIn("PowerShell does not expand", result["memory"]["content"])
        self.assertEqual(result["memory"]["scope"]["project_id"], "memory-evolution")

    def _promoted_claim_memory(self):
        event_id = self.events.add(
            event_type="tool_error",
            actor="agent",
            content="PowerShell rejected Bash heredoc syntax.",
            scope={"project_id": "memory-evolution", "session_id": "helper"},
        )
        cand_id = self.candidates.add(
            candidate_type="claim",
            content="PowerShell does not support Bash heredoc.",
            source_event_ids=[event_id],
            scope={"project_id": "memory-evolution", "session_id": "helper"},
            trigger="debug PowerShell inline command",
        )
        self.evidence.add(
            target_type="candidate",
            target_id=cand_id,
            evidence_type="task_success",
            polarity="supports",
            content="Using a PowerShell-compatible command fixed the issue.",
            source_event_ids=[event_id],
        )
        return self.lifecycle.promote(cand_id)

    def _run_cli(self, argv):
        result, code = self._run_cli_raw(argv)
        self.assertEqual(code, 0)
        return result

    def _run_cli_raw(self, argv):
        output = StringIO()
        with redirect_stdout(output):
            code = cli_main(argv)
        return json.loads(output.getvalue()), code


if __name__ == "__main__":
    unittest.main()

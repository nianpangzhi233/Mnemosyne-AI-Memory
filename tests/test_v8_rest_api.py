import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from api import start_api
from api import v8_routes


class V8RestApiTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="mnemosyne-v8-rest-"))
        self.db = self.tmp / "v8.db"
        os.environ["MNEMOSYNE_V8_DB"] = str(self.db)
        v8_routes._v8_store = None
        self.client = TestClient(start_api.app)

    def tearDown(self):
        v8_routes._v8_store = None
        os.environ.pop("MNEMOSYNE_V8_DB", None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_health_uses_temp_v8_database(self):
        response = self.client.get("/api/v8/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "events": 0, "memories": 0})

    def test_candidate_without_source_returns_400(self):
        response = self.client.post(
            "/api/v8/candidates",
            json={
                "candidate_type": "claim",
                "content": "Missing source should fail.",
                "source_event_ids": [],
                "scope": {"project_id": "memory-evolution", "session_id": "rest"},
                "trigger": "missing source",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("candidate must cite at least one RawEvent", response.json()["detail"])

    def test_full_rest_flow_returns_source_grounded_context_pack(self):
        event_id = self._add_event()
        candidate_id = self._add_candidate(event_id)
        evidence_id = self._add_evidence(candidate_id, event_id)
        promote = self.client.post("/api/v8/lifecycle/promote", json={"candidate_id": candidate_id})
        self.assertEqual(promote.status_code, 200)
        memory_id = promote.json()["id"]

        context = self.client.post(
            "/api/v8/context-packs",
            json={"task": "debug PowerShell inline command", "scope": {"project_id": "memory-evolution"}},
        )

        self.assertTrue(evidence_id.startswith("ev_"))
        self.assertEqual(context.status_code, 200)
        pack = context.json()
        self.assertEqual(pack["items"][0]["id"], memory_id)
        self.assertEqual(pack["items"][0]["source_events"][0]["id"], event_id)
        self.assertEqual(pack["items"][0]["evidence"][0]["source_event_ids"], [event_id])
        self.assertEqual(pack["rejected"], [])

    def test_promote_without_evidence_preserves_gate_reason_code(self):
        event_id = self._add_event()
        candidate_id = self._add_candidate(event_id)

        response = self.client.post("/api/v8/lifecycle/promote", json={"candidate_id": candidate_id})

        self.assertEqual(response.status_code, 400)
        self.assertIn("missing_supporting_evidence", response.json()["detail"])

    def test_stale_memory_is_rejected_with_reason_code(self):
        event_id = self._add_event()
        candidate_id = self._add_candidate(event_id)
        self._add_evidence(candidate_id, event_id)
        memory_id = self.client.post("/api/v8/lifecycle/promote", json={"candidate_id": candidate_id}).json()["id"]
        stale = self.client.post("/api/v8/lifecycle/stale", json={"memory_id": memory_id})
        self.assertEqual(stale.status_code, 200)

        response = self.client.post(
            "/api/v8/context-packs",
            json={"task": "debug PowerShell inline command", "scope": {"project_id": "memory-evolution"}},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["items"], [])
        self.assertEqual(response.json()["rejected"][0]["reason"], "stale")

    def test_record_inspection_endpoints_decode_json_fields(self):
        event_id = self._add_event()

        listed = self.client.get("/api/v8/records/raw_events")
        fetched = self.client.get(f"/api/v8/records/raw_events/{event_id}")

        self.assertEqual(listed.status_code, 200)
        self.assertEqual(fetched.status_code, 200)
        self.assertEqual(listed.json()["items"][0]["id"], event_id)
        self.assertEqual(fetched.json()["scope"]["project_id"], "memory-evolution")

    def _add_event(self):
        response = self.client.post(
            "/api/v8/events",
            json={
                "event_type": "tool_error",
                "actor": "agent",
                "content": "PowerShell rejected Bash heredoc syntax.",
                "scope": {"project_id": "memory-evolution", "session_id": "rest"},
            },
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["id"]

    def _add_candidate(self, event_id):
        response = self.client.post(
            "/api/v8/candidates",
            json={
                "candidate_type": "claim",
                "content": "PowerShell does not support Bash heredoc.",
                "source_event_ids": [event_id],
                "scope": {"project_id": "memory-evolution", "session_id": "rest"},
                "trigger": "debug PowerShell inline command",
            },
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["id"]

    def _add_evidence(self, candidate_id, event_id):
        response = self.client.post(
            "/api/v8/evidence",
            json={
                "target_type": "candidate",
                "target_id": candidate_id,
                "evidence_type": "task_success",
                "polarity": "supports",
                "content": "Using a PowerShell-compatible command fixed the issue.",
                "source_event_ids": [event_id],
            },
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["id"]


if __name__ == "__main__":
    unittest.main()

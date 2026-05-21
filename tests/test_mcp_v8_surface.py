import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MCP_SERVER = ROOT / "scripts" / "mcp_server" / "__init__.py"


class V8McpSurfaceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="mnemosyne-v8-mcp-"))
        self.db = self.tmp / "v8.db"

    def tearDown(self):
        for path in self.tmp.glob("**/*"):
            if path.is_file():
                path.unlink(missing_ok=True)
        for path in sorted(self.tmp.glob("**/*"), reverse=True):
            if path.is_dir():
                path.rmdir()
        if self.tmp.exists():
            self.tmp.rmdir()

    def test_v8_mcp_surface_full_flow(self):
        responses = self._run_mcp(
            [
                {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {
                        "name": "v8_event_add",
                        "arguments": {
                            "event_type": "tool_error",
                            "actor": "agent",
                            "content": "PowerShell rejected Bash heredoc syntax.",
                            "scope": {"project_id": "memory-evolution", "session_id": "mcp"},
                        },
                    },
                },
            ]
        )

        tools = responses[1]["result"]
        tool_names = {tool["name"] for tool in tools["tools"]}
        self.assertIn("v8_event_add", tool_names)
        self.assertIn("v8_candidate_add", tool_names)
        self.assertIn("v8_context_build", tool_names)

        event_id = self._json_tool_payload(responses[2])["id"]
        responses = self._run_mcp(
            [
                {
                    "jsonrpc": "2.0",
                    "id": 4,
                    "method": "tools/call",
                    "params": {
                        "name": "v8_candidate_add",
                        "arguments": {
                            "candidate_type": "claim",
                            "content": "PowerShell does not support Bash heredoc.",
                            "source_event_ids": [event_id],
                            "scope": {"project_id": "memory-evolution", "session_id": "mcp"},
                            "trigger": "debug PowerShell inline command",
                        },
                    },
                },
            ]
        )

        candidate_id = self._json_tool_payload(responses[0])["id"]
        responses = self._run_mcp(
            [
                {
                    "jsonrpc": "2.0",
                    "id": 7,
                    "method": "tools/call",
                    "params": {
                        "name": "v8_evidence_add",
                        "arguments": {
                            "target_id": candidate_id,
                            "target_type": "candidate",
                            "evidence_type": "task_success",
                            "polarity": "supports",
                            "content": "Using a PowerShell-compatible command fixed the issue.",
                            "source_event_ids": [event_id],
                        },
                    },
                },
                {
                    "jsonrpc": "2.0",
                    "id": 8,
                    "method": "tools/call",
                    "params": {"name": "v8_lifecycle_promote", "arguments": {"candidate_id": candidate_id}},
                },
                {
                    "jsonrpc": "2.0",
                    "id": 9,
                    "method": "tools/call",
                    "params": {
                        "name": "v8_context_build",
                        "arguments": {
                            "task": "debug PowerShell inline command",
                            "scope": {"project_id": "memory-evolution"},
                        },
                    },
                },
            ]
        )

        evidence_id = self._json_tool_payload(responses[0])["id"]
        memory_id = self._json_tool_payload(responses[1])["id"]
        context = self._json_tool_payload(responses[2])

        self.assertTrue(evidence_id.startswith("ev_"))
        self.assertTrue(memory_id.startswith("mem_"))
        self.assertEqual(context["items"][0]["id"], memory_id)
        self.assertEqual(context["items"][0]["source_events"][0]["id"], event_id)
        self.assertEqual(context["items"][0]["evidence"][0]["source_event_ids"], [event_id])

    def test_v8_candidate_without_source_is_rejected(self):
        responses = self._run_mcp(
            [
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {
                        "name": "v8_candidate_add",
                        "arguments": {
                            "candidate_type": "claim",
                            "content": "Missing source should fail.",
                            "source_event_ids": [],
                            "scope": {"project_id": "memory-evolution", "session_id": "mcp"},
                            "trigger": "missing source",
                        },
                    },
                },
                {"jsonrpc": "2.0", "id": 2, "method": "shutdown", "params": {}},
            ]
        )

        payload = self._tool_result(responses[0])
        self.assertTrue(payload["isError"])
        self.assertIn("candidate must cite at least one RawEvent", payload["content"][0]["text"])

    def _run_mcp(self, messages):
        env = os.environ.copy()
        env["MCP_V8_DB"] = str(self.db)
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        proc = subprocess.run(
            [sys.executable, str(MCP_SERVER)],
            input="\n".join(json.dumps(message) for message in messages) + "\n",
            text=True,
            encoding="utf-8",
            capture_output=True,
            env=env,
            cwd=str(ROOT),
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]

    def _json_tool_payload(self, response):
        payload = self._tool_result(response)
        self.assertFalse(payload["isError"])
        return json.loads(payload["content"][0]["text"])

    def _tool_result(self, response):
        self.assertIn("result", response)
        self.assertIn("content", response["result"])
        return response["result"]


if __name__ == "__main__":
    unittest.main()

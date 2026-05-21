import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEMO_DIR = ROOT / "demo"
if str(DEMO_DIR) not in sys.path:
    sys.path.insert(0, str(DEMO_DIR))

import run_v8_demo


class V8DemoTest(unittest.TestCase):
    def test_v8_demo_run_produces_validated_memory(self):
        with tempfile.TemporaryDirectory(prefix="mnemosyne-v8-demo-test-") as tmp:
            result = run_v8_demo.run(Path(tmp) / "v8.db")

        self.assertEqual(result["memory"]["status"], "validated")
        self.assertEqual(result["context"]["items"][0]["source_events"][0]["event_type"], "tool_error")
        self.assertEqual(result["context"]["items"][0]["evidence"][0]["source_event_ids"], [result["event_id"]])


if __name__ == "__main__":
    unittest.main()

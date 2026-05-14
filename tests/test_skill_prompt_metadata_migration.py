import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from migrate_v71_to_v72 import migrate


class SkillPromptMetadataMigrationTest(unittest.TestCase):
    def test_v72_migration_adds_prompt_metadata_column(self):
        with tempfile.TemporaryDirectory(prefix="mnemosyne-migration-") as tmp:
            db_path = Path(tmp) / "graph.db"
            meta_path = Path(tmp) / "meta.json"
            conn = sqlite3.connect(str(db_path))
            try:
                conn.execute("CREATE TABLE skill_test_prompts(id TEXT PRIMARY KEY, skill_id TEXT, prompt_id TEXT, prompt TEXT, expected TEXT, tags TEXT, status TEXT, approved_by TEXT, created_at TEXT, updated_at TEXT)")
                conn.commit()
            finally:
                conn.close()

            migrate(str(db_path), str(meta_path))

            conn = sqlite3.connect(str(db_path))
            try:
                cols = {row[1] for row in conn.execute("PRAGMA table_info(skill_test_prompts)").fetchall()}
            finally:
                conn.close()
            self.assertIn("metadata", cols)


if __name__ == "__main__":
    unittest.main()

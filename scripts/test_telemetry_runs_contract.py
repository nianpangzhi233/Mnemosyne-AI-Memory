#!/usr/bin/env python3
"""Contract test for persistent daemon telemetry run history."""

import json
import sys
import tempfile
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

from api import start_api
from core.dream_pipeline import _init_dream_log
from core.telemetry import fail_run, finish_run, list_runs, start_run, summary


def main():
    with tempfile.TemporaryDirectory(prefix="mnemosyne-telemetry-runs-") as tmp:
        dream_log_db = Path(tmp) / "dream_log.db"
        old_api_db = start_api.DREAM_LOG_DB
        start_api.DREAM_LOG_DB = dream_log_db
        try:
            _init_dream_log(dream_log_db)

            dream_run = start_run("dream_full", db_path=dream_log_db)
            finished = finish_run(
                dream_run,
                "PASS",
                db_path=dream_log_db,
                summary={"return_code": 0, "skill_auto_loop_ran": True},
            )
            assert finished["status"] == "PASS"
            assert finished["summary"]["return_code"] == 0

            audit_run = start_run("skill_audit", db_path=dream_log_db)
            failed = fail_run(audit_run, RuntimeError("audit exploded"), db_path=dream_log_db)
            assert failed["status"] == "FAIL"
            assert failed["errors"][0]["message"] == "audit exploded"

            runs = list_runs(limit=5, db_path=dream_log_db)
            assert len(runs) == 2
            assert {run["run_type"] for run in runs} == {"dream_full", "skill_audit"}

            api_runs = start_api.telemetry_runs(limit=5)["runs"]
            assert len(api_runs) == 2
            api_summary = start_api.telemetry_runs_summary()
            assert api_summary["latest_run"]["run_type"] == "skill_audit"
            assert api_summary["latest_failed_run"]["errors"][0]["message"] == "audit exploded"
            assert summary(db_path=dream_log_db)["latest_failed_run"]["status"] == "FAIL"

            print(json.dumps({"status": "PASS", "runs": len(runs), "dream_log_db": str(dream_log_db)}, ensure_ascii=False, indent=2))
        finally:
            start_api.DREAM_LOG_DB = old_api_db


if __name__ == "__main__":
    main()

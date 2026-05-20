from __future__ import annotations

import argparse
import json
import sys
import tempfile
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from v8_memory.cli import main as cli_main


def _cli(argv: list[str]) -> dict:
    output = StringIO()
    with redirect_stdout(output):
        code = cli_main(argv)
    result = json.loads(output.getvalue())
    if code != 0:
        raise RuntimeError(result)
    return result


def run(db_path: str | Path | None = None) -> dict:
    db_path = Path(db_path) if db_path else Path(tempfile.gettempdir()) / "mnemosyne-v8-functional-smoke.db"
    if db_path.exists():
        db_path.unlink()
    db = ["--db", str(db_path)]

    event = _cli(
        db
        + [
            "event",
            "add",
            "--type",
            "tool_error",
            "--actor",
            "opencode",
            "--content",
            "Running `python -m py_compile v8/src/v8_memory/*.py` in PowerShell failed because Python received the literal wildcard path.",
            "--scope-item",
            "project_id=memory-evolution",
            "--scope-item",
            "session_id=functional-smoke",
        ]
    )
    candidate = _cli(
        db
        + [
            "candidate",
            "add",
            "--type",
            "claim",
            "--content",
            "PowerShell does not expand `*.py` for Python arguments; use Python's pathlib glob when compiling multiple files.",
            "--sources",
            event["id"],
            "--scope-item",
            "project_id=memory-evolution",
            "--scope-item",
            "session_id=functional-smoke",
            "--trigger",
            "compile Python files from PowerShell",
        ]
    )
    evidence = _cli(
        db
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
            "`python -c \"import py_compile, pathlib; [py_compile.compile(str(p), doraise=True) for p in pathlib.Path('v8/src/v8_memory').glob('*.py')]\"` compiled the modules successfully.",
            "--sources",
            event["id"],
        ]
    )
    memory = _cli(db + ["lifecycle", "promote", "--candidate", candidate["id"]])
    context = _cli(
        db
        + [
            "context",
            "build",
            "--task",
            "compile Python files from PowerShell",
            "--scope-item",
            "project_id=memory-evolution",
        ]
    )
    inspection = _cli(db + ["memory", "get", "--id", memory["id"]])

    return {
        "db": str(db_path),
        "event_id": event["id"],
        "candidate_id": candidate["id"],
        "evidence_id": evidence["id"],
        "memory_id": memory["id"],
        "context": context,
        "memory": inspection,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db")
    args = parser.parse_args(argv)
    print(json.dumps(run(args.db), ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

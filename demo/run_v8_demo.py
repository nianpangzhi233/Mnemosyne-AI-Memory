#!/usr/bin/env python3
"""Run a safe cold-start V8 demo on temporary SQLite files."""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
V8_SCRIPTS = ROOT / "v8" / "scripts"
if str(V8_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(V8_SCRIPTS))

import functional_smoke


def run(db_path: str | Path | None = None) -> dict:
    return functional_smoke.run(db_path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a safe Mnemosyne V8 cold-start demo")
    parser.add_argument("--keep", action="store_true", help="Keep the demo directory instead of deleting it")
    parser.add_argument("--out", help="Directory to use when --keep is enabled")
    args = parser.parse_args()

    if args.keep:
        demo_dir = Path(args.out) if args.out else Path(tempfile.mkdtemp(prefix="mnemosyne-v8-demo-"))
        demo_dir.mkdir(parents=True, exist_ok=True)
        result = run(demo_dir / "v8.db")
        result["kept"] = True
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return 0 if result["memory"]["status"] == "validated" else 1

    tmp = Path(tempfile.mkdtemp(prefix="mnemosyne-v8-demo-"))
    try:
        result = run(tmp / "v8.db")
        result["kept"] = False
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return 0 if result["memory"]["status"] == "validated" else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())

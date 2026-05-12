#!/usr/bin/env python3
"""Score a skill with Darwin-style rubric from a JSON evaluation file.

This is intentionally small: it turns baseline-vs-with-skill observations into
an auditable score, instead of treating SKILL.md structure as functional proof.
"""

import argparse
import json
from pathlib import Path


WEIGHTS = {
    "frontmatter": 8,
    "workflow": 15,
    "boundaries": 10,
    "checkpoints": 7,
    "specificity": 15,
    "resources": 5,
    "architecture": 15,
    "effect": 25,
}


def score(payload: dict) -> dict:
    dimensions = payload.get("dimensions") or {}
    missing = [name for name in WEIGHTS if name not in dimensions]
    if missing:
        raise SystemExit(f"missing dimensions: {', '.join(missing)}")
    weighted = {}
    total = 0.0
    for name, weight in WEIGHTS.items():
        value = float(dimensions[name])
        if value < 1 or value > 10:
            raise SystemExit(f"dimension {name} out of range 1-10: {value}")
        points = value * weight / 10
        weighted[name] = round(points, 1)
        total += points
    return {
        "skill": payload.get("skill"),
        "score": round(total, 1),
        "dimensions": dimensions,
        "weighted": weighted,
        "cases": payload.get("cases") or [],
        "summary": payload.get("summary") or "",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Darwin-style skill rubric scorer")
    parser.add_argument("file", help="JSON file with dimensions and case scores")
    args = parser.parse_args()
    payload = json.loads(Path(args.file).read_text(encoding="utf-8"))
    print(json.dumps(score(payload), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

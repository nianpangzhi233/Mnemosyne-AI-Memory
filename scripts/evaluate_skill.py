#!/usr/bin/env python3
"""Evaluate a skill through the bilateral Skill Evolution engine.

This CLI is intentionally thin. The actual evaluation flow lives in
core.skill_evolution, and provider-specific calls live in core.runners.
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.sqlite_store import SQLiteStore
from core.skill_evolution import SkillEvolutionRunner
from core.runners import OpenAICompatibleAgentRunner, OpenAICompatibleClient, OpenAICompatibleJudgeRunner

ROOT = Path(__file__).resolve().parent.parent


def _load_json(path: str) -> dict:
    if not path:
        return {}
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _runner_config(args, config: dict, key: str) -> dict:
    section = dict(config.get(key) or {})
    for name in ("endpoint", "model", "api_key", "temperature", "timeout"):
        value = getattr(args, name, None)
        if value is not None:
            section.setdefault(name, value)
    section.setdefault("type", "openai_compatible")
    return section


def _build_openai_runner(section: dict, judge: bool = False):
    endpoint = section.get("endpoint") or os.environ.get("MNEMOSYNE_LLM_ENDPOINT")
    model = section.get("model") or os.environ.get("MNEMOSYNE_LLM_MODEL")
    api_key = section.get("api_key") or os.environ.get("MNEMOSYNE_LLM_API_KEY")
    if not endpoint or not model:
        raise ValueError("endpoint and model are required for openai_compatible runner")
    client = OpenAICompatibleClient(
        endpoint=endpoint,
        model=model,
        api_key=api_key,
        temperature=float(section.get("temperature", 0.1)),
        timeout=int(section.get("timeout", 120)),
    )
    if judge:
        return OpenAICompatibleJudgeRunner(client, max_tokens=int(section.get("max_tokens", 650)))
    return OpenAICompatibleAgentRunner(client, max_tokens=int(section.get("max_tokens", 650)))


def main():
    parser = argparse.ArgumentParser(description="Run bilateral Skill Evolution evaluation.")
    parser.add_argument("--skill-id", required=True)
    parser.add_argument("--db", default=str(ROOT / "graph.db"))
    parser.add_argument("--config", help="JSON config with runner/judge sections")
    parser.add_argument("--endpoint", help="OpenAI-compatible chat completions endpoint")
    parser.add_argument("--model", help="Model name for both runner and judge unless config overrides")
    parser.add_argument("--api-key", help="API key; prefer env/config over CLI for real secrets")
    parser.add_argument("--temperature", type=float)
    parser.add_argument("--timeout", type=int)
    parser.add_argument("--round", type=int, default=0)
    parser.add_argument("--eval-mode", default="full_test")
    args = parser.parse_args()

    config = _load_json(args.config)
    runner_cfg = _runner_config(args, config, "runner")
    judge_cfg = _runner_config(args, config, "judge")
    if runner_cfg.get("type") != "openai_compatible" or judge_cfg.get("type") != "openai_compatible":
        raise ValueError("CLI currently builds openai_compatible runners only; use core APIs for custom runners")

    store = SQLiteStore(args.db)
    runner = _build_openai_runner(runner_cfg, judge=False)
    judge = _build_openai_runner(judge_cfg, judge=True)
    result = SkillEvolutionRunner(store, runner, judge).run(
        args.skill_id, round_no=args.round, eval_mode=args.eval_mode,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

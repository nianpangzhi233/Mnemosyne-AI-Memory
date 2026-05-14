#!/usr/bin/env python3
"""Bilateral Skill Evolution engine.

This module owns the reusable evolution flow. It does not know which model or
provider executes the task; callers inject AgentRunner and JudgeRunner objects.
"""

import json
from typing import Any, Dict


def normalize_agent_output(result: Any) -> str:
    if isinstance(result, dict):
        for key in ("output", "content", "text", "answer"):
            if key in result:
                return str(result.get(key) or "")
        return json.dumps(result, ensure_ascii=False)
    return str(result or "")


def normalize_judge_output(result: Any) -> Dict[str, Any]:
    if isinstance(result, dict):
        return result
    if isinstance(result, str):
        try:
            parsed = json.loads(result)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
        return {"reason": result}
    return {}


def score_0_to_100(value: Any) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0
    if score <= 10:
        score *= 10
    return max(0.0, min(100.0, score))


class SkillEvolutionRunner:
    def __init__(self, store, agent_runner, judge_runner):
        self.store = store
        self.agent_runner = agent_runner
        self.judge_runner = judge_runner

    def run(self, skill_id: str, round_no: int = 0, eval_mode: str = "full_test") -> Dict[str, Any]:
        artifact = self.store.get_skill_artifact(skill_id)
        if not artifact:
            raise ValueError(f"skill artifact not found: {skill_id}")
        if eval_mode == "full_test" and hasattr(self.store, "list_real_skill_test_prompts"):
            prompts = self.store.list_real_skill_test_prompts(skill_id)
        else:
            prompts = self.store.list_skill_test_prompts(skill_id)
        if not prompts:
            if eval_mode == "full_test":
                raise ValueError("Darwin full_test requires at least one real active test prompt; auto-smoke is not evidence")
            raise ValueError("Darwin evaluation requires at least one active test prompt")

        skill_content = self.store.render_skill_markdown(artifact)
        dry_score = self.store.score_skill_dry_run(artifact, skill_content)
        prompt_results = []
        deltas = []
        regressions = 0
        baseline_scores = []
        with_skill_scores = []

        for prompt in prompts:
            baseline = normalize_agent_output(self.agent_runner.run(prompt["prompt"], skill_content=None))
            with_skill = normalize_agent_output(self.agent_runner.run(prompt["prompt"], skill_content=skill_content))
            judged = normalize_judge_output(self.judge_runner.judge(
                prompt["prompt"], prompt.get("expected") or "", baseline, with_skill,
            ))
            baseline_score = score_0_to_100(judged.get("baseline_score"))
            with_skill_score = score_0_to_100(judged.get("with_skill_score"))
            delta = judged.get("delta")
            if delta is None:
                delta = with_skill_score - baseline_score
            else:
                try:
                    delta = float(delta)
                    if abs(delta) <= 10:
                        delta *= 10
                except (TypeError, ValueError):
                    delta = with_skill_score - baseline_score
            regression = bool(judged.get("regression")) or delta <= 0 or judged.get("winner") == "baseline"
            if regression:
                regressions += 1
            deltas.append(delta)
            baseline_scores.append(baseline_score)
            with_skill_scores.append(with_skill_score)
            run_id = self.store.record_skill_eval_run(
                skill_id,
                prompt_id=prompt.get("prompt_id"),
                round=round_no,
                eval_mode=eval_mode,
                baseline_output=baseline,
                with_skill_output=with_skill,
                judge_output=judged,
                baseline_score=baseline_score,
                with_skill_score=with_skill_score,
                live_test_delta=delta,
                regression=regression,
            )
            prompt_results.append({
                "run_id": run_id,
                "prompt_id": prompt.get("prompt_id"),
                "prompt_metadata": prompt.get("metadata") or {},
                "baseline_score": baseline_score,
                "with_skill_score": with_skill_score,
                "delta": delta,
                "regression": regression,
                "judge": judged,
            })

        avg_delta = round(sum(deltas) / len(deltas), 1)
        avg_baseline = round(sum(baseline_scores) / len(baseline_scores), 1)
        avg_with_skill = round(sum(with_skill_scores) / len(with_skill_scores), 1)
        ratchet_score = 100.0 if avg_delta > 0 and regressions == 0 else 0.0
        darwin_score = round(dry_score["darwin_score"] * 0.35 + avg_with_skill * 0.50 + ratchet_score * 0.15, 1)
        passed = darwin_score >= 80 and avg_delta > 0 and regressions == 0 and eval_mode == "full_test"
        darwin_result = {
            "passed": passed,
            "darwin_score": darwin_score,
            "live_test_delta": avg_delta,
            "regression_count": regressions,
            "eval_mode": eval_mode,
            "baseline_score": avg_baseline,
            "with_skill_score": avg_with_skill,
            "structure_score": dry_score["darwin_score"],
            "prompt_results": prompt_results,
        }
        evidence_id = None
        if passed and hasattr(self.store, "record_skill_verification_evidence"):
            evidence_id = self.store.record_skill_verification_evidence(
                skill_id, darwin_result, prompt_results=prompt_results,
            )
            if evidence_id:
                darwin_result["verification_evidence_id"] = evidence_id
        mnemosyne_result = self.store.score_skill_mnemosyne(skill_id, persist=False)
        decision = self.store.decide_skill_evolution(
            skill_id, darwin_result=darwin_result, mnemosyne_result=mnemosyne_result,
        )
        for item in prompt_results:
            self.store.update_skill_eval_run(
                item["run_id"],
                darwin_score=darwin_score,
                mnemosyne_score=mnemosyne_result["mnemosyne_score"],
                decision=decision["decision"],
                decision_reason=decision["decision_reason"],
                kept=1 if decision["decision"] == "evolved" else 0,
                reverted=1 if decision["decision"] == "needs_revision" else 0,
            )
        self.store.record_skill_evolution_run(
            skill_id,
            old_score=artifact.get("final_score"),
            new_score=decision.get("darwin_score"),
            mnemosyne_score=decision.get("mnemosyne_score"),
            darwin_score=darwin_score,
            status=decision["decision"],
            dimension="darwin_live_test",
            note=decision["decision_reason"],
            eval_mode=eval_mode,
            metadata={"darwin": darwin_result, "mnemosyne": mnemosyne_result},
        )
        if hasattr(self.store, "sync_skill_file"):
            self.store.sync_skill_file(skill_id)
        return {"darwin": darwin_result, "mnemosyne": mnemosyne_result, "decision": decision}

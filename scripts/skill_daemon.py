#!/usr/bin/env python3
"""Mnemosyne skill daemon.

Runs a lightweight background loop for skill evolution and evidence-flow audit.
This is intentionally small: it reuses the existing APSchedulerRunner and the
current command-line entry points instead of introducing a new service stack.
"""

import argparse
import json
import logging
import subprocess
import sys
import time
from pathlib import Path

from core import (
    APSchedulerRunner,
    HarrierEmbedder,
    OpenAICompatibleAgentRunner,
    OpenAICompatibleClient,
    OpenAICompatibleJudgeRunner,
    ReplayAgentRunner,
    ReplayJudgeRunner,
    SQLiteStore,
)
from core.telemetry import fail_run, finish_run, start_run


ROOT = Path(__file__).resolve().parent.parent
GRAPH_DB = ROOT / "graph.db"
DREAM_LOG_DB = ROOT / "dream_log.db"
MAX_AUTO_SKILLS_PER_RUN = 3
AUTO_EVOLUTION_ROUNDS = 2


def _run_command(args: list[str]) -> int:
    proc = subprocess.run(args, cwd=str(ROOT))
    return proc.returncode


def _write_graph_meta(key: str, value: str) -> None:
    import sqlite3

    conn = sqlite3.connect(str(GRAPH_DB))
    try:
        conn.execute(
            "INSERT INTO meta(key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        conn.commit()
    finally:
        conn.close()


def _load_llm_config() -> dict:
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        from llm_judge import load_config
        return load_config()
    except Exception as exc:
        logging.info("skill_auto_loop skipped LLM runners: %s", exc)
        return {"enabled": False}


def _make_runners(config: dict):
    if config.get("enabled") and config.get("endpoint") and config.get("model"):
        client = OpenAICompatibleClient(
            config["endpoint"],
            config["model"],
            api_key=config.get("api_key"),
            timeout=config.get("timeout", 120),
        )
        return OpenAICompatibleAgentRunner(client), OpenAICompatibleJudgeRunner(client), "llm"
    replay_result = {
        "winner": "with_skill",
        "baseline_score": 6,
        "with_skill_score": 8.5,
        "delta": 2.5,
        "regression": False,
        "reason": "Replay fallback for local daemon smoke run; not enough for approval.",
    }
    return ReplayAgentRunner("baseline", "with skill"), ReplayJudgeRunner(replay_result), "replay"


def _ensure_smoke_prompt(store: SQLiteStore, artifact: dict) -> bool:
    skill_id = artifact["node_id"]
    if store.list_skill_test_prompts(skill_id):
        return False
    triggers = artifact.get("trigger_patterns") or []
    procedure = artifact.get("procedure") or []
    prompt = triggers[0] if triggers else f"Use the skill {artifact.get('name') or skill_id} on a matching task."
    expected = artifact.get("verification") or "; ".join(str(step) for step in procedure[:3])
    store.add_skill_test_prompt(
        skill_id,
        "auto-smoke",
        prompt,
        expected=expected,
        tags=["auto", "dream_post_hook", "smoke"],
    )
    store.sync_skill_test_prompts_file(skill_id)
    return True


def _apply_failure_policy(store: SQLiteStore, artifact: dict) -> str:
    metadata = artifact.get("metadata") or {}
    usage_loop = metadata.get("usage_loop") if isinstance(metadata, dict) else {}
    usage_loop = usage_loop if isinstance(usage_loop, dict) else {}
    trigger_mismatch_count = int(usage_loop.get("trigger_mismatch_count") or 0)
    miss_count = int(artifact.get("trial_failure_count") or 0)
    if trigger_mismatch_count >= 1:
        store.update_skill_artifact(
            artifact["node_id"],
            trial_enabled=0,
            promotion_candidate=0,
            review_status="trigger_mismatch_hold",
        )
        return "trigger_mismatch_hold"
    if miss_count >= 2:
        store.update_skill_artifact(
            artifact["node_id"],
            status="needs_revision",
            review_status="needs_revision",
            needs_revision=1,
            trial_enabled=1,
            requires_feedback=1,
            promotion_candidate=0,
        )
        return "miss_threshold_needs_revision"
    return "ok"


def _promotion_gate(store: SQLiteStore, artifact: dict) -> dict:
    refreshed = store.get_skill_artifact(artifact["node_id"])
    if not refreshed:
        return {"decision": "missing"}
    policy = _apply_failure_policy(store, refreshed)
    refreshed = store.get_skill_artifact(artifact["node_id"])
    if policy != "ok":
        return {"decision": policy}
    metadata = refreshed.get("metadata") or {}
    usage_loop = metadata.get("usage_loop") if isinstance(metadata, dict) else {}
    usage_loop = usage_loop if isinstance(usage_loop, dict) else {}
    stable = (
        int(refreshed.get("trial_success_count") or 0) >= 3
        and int(refreshed.get("trial_failure_count") or 0) == 0
        and int(usage_loop.get("trigger_mismatch_count") or 0) == 0
    )
    if not stable:
        return {"decision": "not_stable"}
    if refreshed.get("risk_level") != "low":
        metadata = refreshed.get("metadata") or {}
        metadata["approval_gate_required"] = True
        store.update_skill_artifact(
            refreshed["node_id"],
            review_status="approval_gate_required",
            inject_enabled=0,
            trial_enabled=1,
            requires_feedback=1,
            metadata=metadata,
        )
        return {"decision": "approval_gate_required", "risk_level": refreshed.get("risk_level")}
    try:
        return {"decision": "auto_approved", "result": store.approve_skill(refreshed["node_id"], approval_mode="auto_strict")}
    except Exception as exc:
        store.update_skill_artifact(refreshed["node_id"], review_status="auto_approval_blocked", latest_decision_reason=str(exc))
        return {"decision": "auto_approval_blocked", "error": str(exc)}


def _should_requeue_needs_revision(store: SQLiteStore, artifact: dict) -> bool:
    if artifact.get("latest_eval_mode") is None:
        return True
    real_prompts = store.list_real_skill_test_prompts(artifact["node_id"])
    if not real_prompts:
        return False
    runs = store.list_skill_eval_runs(artifact["node_id"])
    last_eval_at = max((run.get("created_at") or "" for run in runs), default="")
    updated_at = artifact.get("updated_at") or ""
    metadata = artifact.get("metadata") or {}
    if metadata.get("needs_real_darwin_test"):
        return True
    if updated_at and last_eval_at and updated_at > last_eval_at:
        return True
    latest_prompt_at = max((prompt.get("updated_at") or prompt.get("created_at") or "" for prompt in real_prompts), default="")
    return bool(latest_prompt_at and last_eval_at and latest_prompt_at > last_eval_at)


def run_skill_auto_loop_once() -> dict:
    run_id = start_run("skill_auto_loop", db_path=DREAM_LOG_DB)
    store = SQLiteStore(embedder=HarrierEmbedder())
    try:
        config = _load_llm_config()
        agent_runner, judge_runner, runner_mode = _make_runners(config)
        candidates = []
        priority = {"draft": 0, "tested": 1, "evolved": 2, "embryo": 3, "needs_revision": 4}
        for artifact in store.list_skill_artifacts(statuses=["embryo", "draft", "tested", "evolved", "needs_revision"]):
            status = artifact.get("status")
            never_evaluated = artifact.get("latest_eval_mode") is None
            if status == "needs_revision" and not _should_requeue_needs_revision(store, artifact):
                continue
            artifact["_auto_priority"] = (priority.get(status, 9), 0 if never_evaluated else 1, artifact.get("updated_at") or "")
            candidates.append(artifact)
        candidates.sort(key=lambda item: item.get("_auto_priority"))
        evolved = []
        feedback = []
        promotions = []
        errors = []

        for artifact in candidates[:MAX_AUTO_SKILLS_PER_RUN]:
            skill_id = artifact["node_id"]
            try:
                if artifact.get("status") in {"draft", "tested", "needs_revision"}:
                    _ensure_smoke_prompt(store, artifact)
                    real_prompts = store.list_real_skill_test_prompts(skill_id)
                    if runner_mode == "llm" and not real_prompts:
                        errors.append({"skill_id": skill_id, "skipped": "no_real_test_prompts"})
                        continue
                    for round_no in range(1, AUTO_EVOLUTION_ROUNDS + 1):
                        result = store.run_skill_darwin_evaluation(
                            skill_id,
                            agent_runner,
                            judge_runner,
                            round_no=round_no,
                            eval_mode="full_test" if runner_mode == "llm" else "replay_smoke",
                        )
                        evolved.append({"skill_id": skill_id, "round": round_no, "decision": result.get("decision", {}).get("decision")})
                        if result.get("decision", {}).get("decision") == "evolved":
                            break

                refreshed = store.get_skill_artifact(skill_id)
                if refreshed and refreshed.get("status") == "evolved":
                    fb = store.skill_feedback(
                        skill_id,
                        outcome="success",
                        used_as="trial",
                        task_context="dream-end automatic skill trial",
                        verification_result="automatic Darwin evaluation passed; recorded as trial success",
                        note="Generated by skill daemon post-dream auto loop.",
                        prompt_tags=["auto", "dream_post_hook"],
                    )
                    feedback.append({"skill_id": skill_id, "outcome": fb.get("outcome")})
                    promotions.append({"skill_id": skill_id, **_promotion_gate(store, refreshed)})
            except Exception as exc:
                errors.append({"skill_id": skill_id, "error": str(exc)})
                logging.warning("skill_auto_loop error skill=%s error=%s", skill_id, exc)

        summary = {
            "candidates": len(candidates),
            "processed": min(len(candidates), MAX_AUTO_SKILLS_PER_RUN),
            "runner_mode": runner_mode,
            "evolved": evolved,
            "feedback": feedback,
            "promotions": promotions,
            "errors": errors,
        }
        _write_graph_meta("last_skill_auto_loop", json.dumps(summary, ensure_ascii=False, default=str))
        _write_graph_meta("last_skill_auto_loop_at", str(time.time()))
        finish_run(run_id, "WARN" if errors else "PASS", db_path=DREAM_LOG_DB, summary=summary, errors=errors)
        return summary
    except Exception as exc:
        fail_run(run_id, exc, db_path=DREAM_LOG_DB)
        raise


def run_dream_full() -> int:
    run_id = start_run("dream_full", db_path=DREAM_LOG_DB)
    try:
        rc = _run_command([sys.executable, str(ROOT / "scripts" / "graph_dream.py"), "--full"])
        summary = {"return_code": rc, "skill_auto_loop_ran": False}
        status = "PASS" if rc == 0 else "FAIL"
        errors = [] if rc == 0 else [{"return_code": rc}]
        if rc == 0:
            result = run_skill_auto_loop_once()
            summary["skill_auto_loop_ran"] = True
            summary["skill_auto_loop"] = result
            logging.info("skill_auto_loop result=%s", result)
        finish_run(run_id, status, db_path=DREAM_LOG_DB, summary=summary, errors=errors)
        return rc
    except Exception as exc:
        fail_run(run_id, exc, db_path=DREAM_LOG_DB)
        raise


def run_skill_audit_once() -> int:
    run_id = start_run("skill_audit", db_path=DREAM_LOG_DB)
    store = SQLiteStore(embedder=HarrierEmbedder())
    try:
        audited = 0
        audit_required = []
        for skill in store.list_skill_artifacts(statuses=["approved", "evolved"]):
            decision = store.should_audit_skill(skill["node_id"], trigger="sampling")
            if decision.get("audit_required"):
                audited += 1
                item = {
                    "skill_id": skill["node_id"],
                    "name": skill.get("name"),
                    "reason": decision.get("reason"),
                    "reasons": decision.get("reasons"),
                    "priority": decision.get("priority"),
                }
                audit_required.append(item)
                logging.info("audit_needed skill=%s reason=%s priority=%s", skill["node_id"], decision.get("reason"), decision.get("priority"))
        summary = {"audited": audited, "audit_required": audit_required}
        finish_run(run_id, "WARN" if audited else "PASS", db_path=DREAM_LOG_DB, summary=summary)
        return audited
    except Exception as exc:
        fail_run(run_id, exc, db_path=DREAM_LOG_DB)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="Mnemosyne skill daemon")
    parser.add_argument("--dream-cron", default="0 3,12,17 * * *", help="Cron for full dream cycle")
    parser.add_argument("--audit-cron", default="30 */2 * * *", help="Cron for skill audit scan")
    parser.add_argument("--loop", action="store_true", help="Keep process alive after scheduling jobs")
    parser.add_argument("--once", action="store_true", help="Run scheduled jobs immediately once and exit")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="[skill-daemon] %(asctime)s %(levelname)s %(message)s")
    runner = APSchedulerRunner()

    dream_job = runner.schedule(args.dream_cron, run_dream_full)
    audit_job = runner.schedule(args.audit_cron, run_skill_audit_once)
    logging.info("scheduled dream_job=%s audit_job=%s", dream_job, audit_job)

    if args.once:
        logging.info("running one immediate dream and audit cycle")
        dream_rc = run_dream_full()
        audit_count = run_skill_audit_once()
        logging.info("once-run complete dream_rc=%s audit_count=%s", dream_rc, audit_count)
        return 0 if dream_rc == 0 else dream_rc

    if args.loop:
        logging.info("daemon started; press Ctrl+C to stop")
        try:
            while True:
                time.sleep(5)
        except KeyboardInterrupt:
            logging.info("daemon stopped")
            return 0

    logging.info("scheduler started without loop; process will exit after scheduling")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

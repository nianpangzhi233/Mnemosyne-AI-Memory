from __future__ import annotations

from typing import Any

from .models import loads, normalize_scope
from .store import SQLiteV8Store


PROCEDURAL_TYPES = {"procedure", "workflow", "skill"}
PROCEDURAL_EVIDENCE = {"test_result", "control_flow_trace"}


class WriteGate:
    def __init__(self, store: SQLiteV8Store):
        self.store = store

    def check_promote(self, candidate: dict[str, Any]) -> tuple[bool, list[str]]:
        reasons: list[str] = []
        source_ids = loads(candidate.get("source_event_ids_json"), [])
        scope = normalize_scope(loads(candidate.get("scope_json")))
        evidence = self.store.list_evidence("candidate", candidate["id"])
        support = [row for row in evidence if row["polarity"] == "supports"]
        contradictions = [row for row in evidence if row["polarity"] == "contradicts"]

        if not source_ids:
            reasons.append("missing_source")
        if not scope:
            reasons.append("missing_scope")
        if not support:
            reasons.append("missing_supporting_evidence")
        if contradictions:
            reasons.append("contradicting_evidence")
        if candidate["candidate_type"] in PROCEDURAL_TYPES:
            if not any(row["evidence_type"] in PROCEDURAL_EVIDENCE for row in support):
                reasons.append("missing_procedural_evidence")
        return not reasons, reasons


class ReadGate:
    DEFAULT_ALLOWED_RISK = {"low", "medium"}
    DEFAULT_ALLOWED_STATUS = {"validated", "promoted"}

    def check(
        self,
        memory: dict[str, Any],
        task: str,
        scope: dict[str, Any] | None,
        policy: dict[str, Any] | None = None,
    ) -> tuple[bool, str | None]:
        policy = policy or {}
        if float(memory["freshness"]) < float(policy.get("min_freshness", 0.1)):
            return False, "stale"
        if memory["status"] not in self.DEFAULT_ALLOWED_STATUS:
            return False, "status_blocked"
        allowed_risk = set(policy.get("allowed_risk", self.DEFAULT_ALLOWED_RISK))
        if memory["risk"] not in allowed_risk:
            return False, "risk_blocked"
        if not self._scope_matches(loads(memory.get("scope_json")), normalize_scope(scope)):
            return False, "scope_mismatch"
        if not self._task_matches(memory, task):
            return False, "no_task_match"
        return True, None

    def _scope_matches(self, memory_scope: dict[str, Any], requested_scope: dict[str, str]) -> bool:
        for key in ("project_id", "user_id"):
            if key in memory_scope and key in requested_scope and str(memory_scope[key]) != requested_scope[key]:
                return False
        for key, requested_value in requested_scope.items():
            if key in memory_scope and str(memory_scope[key]) != requested_value:
                return False
        return True

    def _task_matches(self, memory: dict[str, Any], task: str) -> bool:
        words = {word.lower() for word in task.replace("-", " ").split() if len(word) >= 3}
        haystack = f"{memory.get('trigger', '')} {memory.get('content', '')}".lower()
        return not words or any(word in haystack for word in words)

from __future__ import annotations

from typing import Any

from .gates import ReadGate
from .models import loads, new_id, normalize_scope, now_iso
from .store import SQLiteV8Store


class ContextPackBuilder:
    def __init__(self, store: SQLiteV8Store, read_gate: ReadGate | None = None):
        self.store = store
        self.read_gate = read_gate or ReadGate()

    def build(
        self,
        task: str,
        scope: dict[str, Any] | None = None,
        budget: dict[str, Any] | None = None,
        policy: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        selected: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []
        for memory in self.store.list_all("memories"):
            ok, reason = self.read_gate.check(memory, task, normalize_scope(scope), policy)
            item = {
                "id": memory["id"],
                "type": memory["memory_type"],
                "content": memory["content"],
                "scope": loads(memory["scope_json"]),
                "status": memory["status"],
                "source_events": self._source_event_snippets(memory),
                "evidence": self._evidence_snippets(memory),
            }
            if ok:
                selected.append(item)
            else:
                rejected.append({"id": memory["id"], "reason": reason or "unsupported"})
        run_id = new_id("ctx")
        warnings: list[str] = []
        self.store.insert_context_run(run_id, now_iso(), task, normalize_scope(scope), selected, rejected, warnings, budget or {})
        return {"id": run_id, "items": selected, "rejected": rejected, "warnings": warnings}

    def _source_event_snippets(self, memory: dict[str, Any]) -> list[dict[str, Any]]:
        candidate = self.store.get("candidates", memory["candidate_id"])
        if not candidate:
            return []
        snippets: list[dict[str, Any]] = []
        for event_id in loads(candidate["source_event_ids_json"], []):
            event = self.store.get("raw_events", event_id)
            if not event:
                continue
            snippets.append(
                {
                    "id": event["id"],
                    "event_type": event["event_type"],
                    "actor": event["actor"],
                    "trust": event["trust"],
                    "content": event["content"],
                    "scope": loads(event["scope_json"]),
                }
            )
        return snippets

    def _evidence_snippets(self, memory: dict[str, Any]) -> list[dict[str, Any]]:
        snippets: list[dict[str, Any]] = []
        for row in self.store.list_evidence("candidate", memory["candidate_id"]):
            snippets.append(
                {
                    "id": row["id"],
                    "type": row["evidence_type"],
                    "polarity": row["polarity"],
                    "content": row["content"],
                    "source_event_ids": loads(row["source_event_ids_json"], []),
                }
            )
        return snippets

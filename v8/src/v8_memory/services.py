from __future__ import annotations

from typing import Any

from .models import dumps, new_id, normalize_scope, now_iso
from .store import SQLiteV8Store


class EventWriter:
    def __init__(self, store: SQLiteV8Store):
        self.store = store

    def add(
        self,
        event_type: str,
        actor: str,
        content: str,
        scope: dict[str, Any] | None = None,
        trust: str = "local",
        content_ref: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        if not event_type or not actor or not content:
            raise ValueError("event_type, actor, and content are required")
        event_id = new_id("evt")
        return self.store.insert(
            "raw_events",
            {
                "id": event_id,
                "created_at": now_iso(),
                "actor": actor,
                "event_type": event_type,
                "trust": trust,
                "scope_json": dumps(normalize_scope(scope)),
                "content": content,
                "content_ref": content_ref,
                "metadata_json": dumps(metadata),
            },
        )


class CandidateWriter:
    def __init__(self, store: SQLiteV8Store):
        self.store = store

    def add(
        self,
        candidate_type: str,
        content: str,
        source_event_ids: list[str],
        scope: dict[str, Any],
        trigger: str,
        risk: str = "low",
        preconditions: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        if not source_event_ids:
            raise ValueError("candidate must cite at least one RawEvent")
        missing = [event_id for event_id in source_event_ids if not self.store.get("raw_events", event_id)]
        if missing:
            raise ValueError(f"source RawEvent not found: {missing[0]}")
        if not normalize_scope(scope):
            raise ValueError("candidate scope is required")
        candidate_id = new_id("cand")
        return self.store.insert(
            "candidates",
            {
                "id": candidate_id,
                "created_at": now_iso(),
                "candidate_type": candidate_type,
                "content": content,
                "source_event_ids_json": dumps(source_event_ids),
                "scope_json": dumps(normalize_scope(scope)),
                "trigger": trigger,
                "preconditions_json": dumps(preconditions or []),
                "risk": risk,
                "status": "candidate",
                "metadata_json": dumps(metadata),
            },
        )


class EvidenceRecorder:
    VALID_POLARITIES = {"supports", "weakens", "contradicts", "neutral"}

    def __init__(self, store: SQLiteV8Store):
        self.store = store

    def add(
        self,
        target_type: str,
        target_id: str,
        evidence_type: str,
        polarity: str,
        content: str,
        source_event_ids: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        if polarity not in self.VALID_POLARITIES:
            raise ValueError(f"invalid evidence polarity: {polarity}")
        table = "candidates" if target_type == "candidate" else "memories"
        if target_type not in {"candidate", "memory"} or not self.store.get(table, target_id):
            raise ValueError("evidence target does not exist")
        source_event_ids = source_event_ids or []
        missing = [event_id for event_id in source_event_ids if not self.store.get("raw_events", event_id)]
        if missing:
            raise ValueError(f"source RawEvent not found: {missing[0]}")
        evidence_id = new_id("ev")
        return self.store.insert(
            "evidence",
            {
                "id": evidence_id,
                "created_at": now_iso(),
                "target_type": target_type,
                "target_id": target_id,
                "evidence_type": evidence_type,
                "polarity": polarity,
                "content": content,
                "source_event_ids_json": dumps(source_event_ids),
                "metadata_json": dumps(metadata),
            },
        )

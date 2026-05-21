from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from v8_memory.context import ContextPackBuilder
from v8_memory.lifecycle import LifecycleManager
from v8_memory.services import CandidateWriter, EvidenceRecorder, EventWriter
from v8_memory.store import SQLiteV8Store


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_V8_DB = PROJECT_ROOT / "v8" / "data" / "v8.db"
ALLOWED_TABLES = {"raw_events", "candidates", "evidence", "memories", "context_pack_runs"}

router = APIRouter(prefix="/api/v8", tags=["V8"])

_v8_store: SQLiteV8Store | None = None


def _get_v8_store() -> SQLiteV8Store:
    global _v8_store
    if _v8_store is None:
        db_path = os.environ.get("MNEMOSYNE_V8_DB") or os.environ.get("V8_DB") or str(DEFAULT_V8_DB)
        _v8_store = SQLiteV8Store(db_path)
    return _v8_store


def _v8_400(exc: Exception) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


class V8EventRequest(BaseModel):
    event_type: str
    actor: str
    content: str
    scope: dict[str, Any] | None = None
    trust: str = "local"
    content_ref: str | None = None
    metadata: dict[str, Any] | None = None


class V8CandidateRequest(BaseModel):
    candidate_type: str
    content: str
    source_event_ids: list[str] = Field(default_factory=list)
    scope: dict[str, Any]
    trigger: str
    risk: str = "low"
    preconditions: list[str] | None = None
    metadata: dict[str, Any] | None = None


class V8EvidenceRequest(BaseModel):
    target_type: str = "candidate"
    target_id: str
    evidence_type: str
    polarity: str = Field(pattern="^(supports|weakens|contradicts|neutral)$")
    content: str
    source_event_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] | None = None


class V8LifecyclePromoteRequest(BaseModel):
    candidate_id: str


class V8LifecycleMemoryRequest(BaseModel):
    memory_id: str


class V8ContextPackRequest(BaseModel):
    task: str
    scope: dict[str, Any] | None = None
    budget: dict[str, Any] | None = None
    policy: dict[str, Any] | None = None


@router.get("/health")
def health():
    store = _get_v8_store()
    return {"status": "ok", "events": len(store.list_all("raw_events")), "memories": len(store.list_all("memories"))}


@router.post("/events")
def add_event(req: V8EventRequest):
    try:
        event_id = EventWriter(_get_v8_store()).add(
            event_type=req.event_type,
            actor=req.actor,
            content=req.content,
            scope=req.scope,
            trust=req.trust,
            content_ref=req.content_ref,
            metadata=req.metadata,
        )
        return {"id": event_id}
    except Exception as exc:
        raise _v8_400(exc) from exc


@router.post("/candidates")
def add_candidate(req: V8CandidateRequest):
    try:
        candidate_id = CandidateWriter(_get_v8_store()).add(
            candidate_type=req.candidate_type,
            content=req.content,
            source_event_ids=req.source_event_ids,
            scope=req.scope,
            trigger=req.trigger,
            risk=req.risk,
            preconditions=req.preconditions,
            metadata=req.metadata,
        )
        return {"id": candidate_id}
    except Exception as exc:
        raise _v8_400(exc) from exc


@router.post("/evidence")
def add_evidence(req: V8EvidenceRequest):
    try:
        evidence_id = EvidenceRecorder(_get_v8_store()).add(
            target_type=req.target_type,
            target_id=req.target_id,
            evidence_type=req.evidence_type,
            polarity=req.polarity,
            content=req.content,
            source_event_ids=req.source_event_ids,
            metadata=req.metadata,
        )
        return {"id": evidence_id}
    except Exception as exc:
        raise _v8_400(exc) from exc


@router.post("/lifecycle/promote")
def promote(req: V8LifecyclePromoteRequest):
    try:
        memory_id = LifecycleManager(_get_v8_store()).promote(req.candidate_id)
        return {"id": memory_id}
    except Exception as exc:
        raise _v8_400(exc) from exc


@router.post("/lifecycle/demote")
def demote(req: V8LifecycleMemoryRequest):
    try:
        memory_id = LifecycleManager(_get_v8_store()).demote(req.memory_id)
        return {"id": memory_id}
    except Exception as exc:
        raise _v8_400(exc) from exc


@router.post("/lifecycle/stale")
def stale(req: V8LifecycleMemoryRequest):
    try:
        memory_id = LifecycleManager(_get_v8_store()).stale(req.memory_id)
        return {"id": memory_id}
    except Exception as exc:
        raise _v8_400(exc) from exc


@router.post("/lifecycle/deprecate")
def deprecate(req: V8LifecycleMemoryRequest):
    try:
        memory_id = LifecycleManager(_get_v8_store()).deprecate(req.memory_id)
        return {"id": memory_id}
    except Exception as exc:
        raise _v8_400(exc) from exc


@router.post("/context-packs")
def build_context_pack(req: V8ContextPackRequest):
    try:
        return ContextPackBuilder(_get_v8_store()).build(task=req.task, scope=req.scope, budget=req.budget, policy=req.policy)
    except Exception as exc:
        raise _v8_400(exc) from exc


@router.get("/memories")
def list_memories(limit: int = Query(20, ge=1, le=200)):
    return {"items": _get_v8_store().inspect_list("memories", limit)}


@router.get("/memories/{memory_id}")
def get_memory(memory_id: str):
    try:
        return _get_v8_store().inspect_get("memories", memory_id)
    except Exception as exc:
        raise _v8_400(exc) from exc


@router.get("/records/{table}")
def list_records(table: str, limit: int = Query(20, ge=1, le=200)):
    if table not in ALLOWED_TABLES:
        raise HTTPException(status_code=400, detail=f"unsupported table: {table}")
    return {"items": _get_v8_store().inspect_list(table, limit)}


@router.get("/records/{table}/{record_id}")
def get_record(table: str, record_id: str):
    if table not in ALLOWED_TABLES:
        raise HTTPException(status_code=400, detail=f"unsupported table: {table}")
    try:
        return _get_v8_store().inspect_get(table, record_id)
    except Exception as exc:
        raise _v8_400(exc) from exc

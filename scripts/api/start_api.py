#!/usr/bin/env python3
"""Mnemosyne REST API — FastAPI

端点:
  GET    /api/health          健康检查
  POST   /api/write           写入经验
  GET    /api/search          搜索（支持 precise/creative/vector/keyword/hybrid + layer）
  GET    /api/node/{id}       节点详情
  PATCH  /api/node/{id}       更新节点
  DELETE /api/node/{id}       删除节点
  GET    /api/node/{id}/graph 节点关联图
  GET    /docs                Swagger UI
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
import uvicorn

scripts_dir = Path(__file__).resolve().parent.parent
if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))

v8_src_dir = scripts_dir.parent / "v8" / "src"
if v8_src_dir.exists() and str(v8_src_dir) not in sys.path:
    sys.path.insert(0, str(v8_src_dir))

from core.sqlite_store import SQLiteStore
from core.embedder import HarrierEmbedder
from core.contracts import serialize_node_fields
from core.dream_pipeline import _init_dream_log
from core import telemetry as telemetry_store
from api.v8_routes import router as v8_router

app = FastAPI(
    title="Mnemosyne API",
    description="Bionic memory system for AI agents — REST API",
    version="7.2.0",
)
app.include_router(v8_router)

_store: Optional[SQLiteStore] = None
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DREAM_LOG_DB = PROJECT_ROOT / "dream_log.db"


def _get_store() -> SQLiteStore:
    global _store
    if _store is None:
        _store = SQLiteStore(embedder=HarrierEmbedder())
    return _store


def _dream_log_rows(query: str, params: tuple = ()) -> List[Dict[str, Any]]:
    _init_dream_log(DREAM_LOG_DB)
    conn = sqlite3.connect(str(DREAM_LOG_DB))
    try:
        conn.row_factory = sqlite3.Row
        return [dict(row) for row in conn.execute(query, params).fetchall()]
    except sqlite3.Error:
        return []
    finally:
        conn.close()


def _json_field(value: Any, default: Any):
    if value in (None, ""):
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default


# ── Request / Response Models ───────────────────────────────


class WriteRequest(BaseModel):
    content: str = Field(..., description="Experience content (L2)")
    type: str = Field("experience", description="Node type: experience / correction / raw")
    principle: Optional[str] = Field(None, description="Abstract principle")
    task_type: Optional[str] = Field(None, description="Task category")
    project: Optional[str] = Field(None, description="Project name")
    tags: Optional[List[str]] = Field(None, description="Tags")
    precondition: Optional[str] = Field(None, description="Environmental condition")
    predicted_outcome: Optional[str] = Field(None, description="Predicted result")
    context_tags: Optional[List[str]] = Field(None, description="Context tags")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Structured metadata")
    contradicts: Optional[str] = Field(None, description="Node ID being corrected")


class WriteResponse(BaseModel):
    id: str


class SearchResponse(BaseModel):
    results: list
    total: int


class HealthResponse(BaseModel):
    status: str
    nodes: int
    edges: int


# ── Routes ───────────────────────────────────────────────────


@app.get("/api/health", response_model=HealthResponse, tags=["System"])
def health():
    store = _get_store()
    return {
        "status": "ok",
        "nodes": store.count_nodes(),
        "edges": store.count_edges(),
    }


@app.post("/api/write", response_model=WriteResponse, tags=["Memory"])
def write(req: WriteRequest):
    store = _get_store()
    node_id = store.add_node(
        content=req.content,
        node_type=req.type,
        principle=req.principle,
        task_type=req.task_type,
        project=req.project,
        tags=req.tags,
        precondition=req.precondition,
        predicted_outcome=req.predicted_outcome,
        context_tags=req.context_tags,
        metadata=req.metadata,
    )
    if req.contradicts:
        store.add_edge(node_id, req.contradicts, "contradicts", weight=0.7, source="api")
    return {"id": node_id}


@app.get("/api/search", response_model=SearchResponse, tags=["Memory"])
def search(
    q: str = Query(..., description="Search query"),
    layer: str = Query("L0", description="Return layer: L0 / L1 / L2"),
    mode: str = Query("hybrid", description="Search mode: precise / creative / vector / keyword / hybrid"),
    top: int = Query(5, ge=1, le=50, description="Max results"),
    graph_dim: str = Query(None, description="Filter by graph dimension: semantic/temporal/causal/entity"),
    tags: str = Query(None, description="Filter by context tags (comma-separated)"),
):
    store = _get_store()
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None
    if mode in ("precise", "creative"):
        results = store.search_spreading(q, mode=mode, graph_dims=[graph_dim] if graph_dim else None, tags=tag_list, top=top, layer=layer)
    elif mode == "vector":
        results = store.search_by_vector(q, top=top, layer=layer, tags=tag_list)
    elif mode == "keyword":
        results = store.search_by_keyword(q, top=top, layer=layer, tags=tag_list)
    else:
        results = store.search_hybrid(q, top=top, layer=layer, tags=tag_list)
    return {"results": results, "total": len(results)}


@app.get("/api/node/{node_id}", tags=["Memory"])
def get_node(node_id: str):
    store = _get_store()
    node = store.get_node(node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    return node


@app.get("/api/node/{node_id}/graph", tags=["Memory"])
def get_node_graph(node_id: str, depth: int = Query(2, ge=1, le=4)):
    store = _get_store()
    node = store.get_node(node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    edges = store.traverse(node_id, depth=depth, max_results=50)
    return {"node": node, "edges": edges}


class UpdateRequest(BaseModel):
    content: Optional[str] = None
    confidence: Optional[float] = None
    context_tags: Optional[List[str]] = None
    principle: Optional[str] = None
    task_type: Optional[str] = None
    project: Optional[str] = None
    tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
    precondition: Optional[str] = None
    predicted_outcome: Optional[str] = None
    half_life_days: Optional[float] = None
    tier: Optional[str] = None
    decay_score: Optional[float] = None
    base_score: Optional[float] = None


@app.patch("/api/node/{node_id}", tags=["Memory"])
def update_node(node_id: str, req: UpdateRequest):
    store = _get_store()
    fields = serialize_node_fields({k: v for k, v in req.model_dump().items() if v is not None})
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")
    ok = store.update_node(node_id, **fields)
    if not ok:
        raise HTTPException(status_code=404, detail="Node not found")
    return {"id": node_id, "updated": True}


@app.delete("/api/node/{node_id}", tags=["Memory"])
def delete_node(node_id: str):
    store = _get_store()
    ok = store.delete_node(node_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Node not found")
    return {"id": node_id, "deleted": True}


@app.get("/api/evolution-reports/latest", tags=["Dream"])
def latest_evolution_report():
    rows = _dream_log_rows(
        "SELECT * FROM evolution_reports ORDER BY created_at DESC LIMIT 1"
    )
    if not rows:
        return {"report": None}
    row = rows[0]
    return {"report": _json_field(row.get("report"), {})}


@app.get("/api/evolution-reports", tags=["Dream"])
def list_evolution_reports(limit: int = Query(10, ge=1, le=100)):
    rows = _dream_log_rows(
        "SELECT id, dream_id, created_at, status, summary FROM evolution_reports ORDER BY created_at DESC LIMIT ?",
        (limit,),
    )
    return {"reports": rows, "total": len(rows)}


@app.get("/api/telemetry/latest", tags=["Dream"])
def latest_telemetry(limit: int = Query(20, ge=1, le=200)):
    rows = _dream_log_rows(
        "SELECT * FROM telemetry_events ORDER BY created_at DESC LIMIT ?",
        (limit,),
    )
    for row in rows:
        row["payload"] = _json_field(row.get("payload"), {})
    return {"events": rows, "total": len(rows)}


@app.get("/api/telemetry/summary", tags=["Dream"])
def telemetry_summary():
    latest = _dream_log_rows(
        "SELECT dream_id, created_at, status, duration_ms FROM telemetry_events WHERE event_type='dream' ORDER BY created_at DESC LIMIT 1"
    )
    if not latest:
        return {"latest_dream": None, "by_status": [], "latest_phase_summary": None}
    dream_id = latest[0]["dream_id"]
    rows = _dream_log_rows(
        "SELECT status, COUNT(*) AS count, AVG(duration_ms) AS avg_duration_ms FROM telemetry_events WHERE dream_id=? GROUP BY status",
        (dream_id,),
    )
    phases = _dream_log_rows(
        "SELECT COUNT(*) AS count, AVG(duration_ms) AS avg_duration_ms, MAX(duration_ms) AS max_duration_ms FROM telemetry_events WHERE dream_id=? AND event_type='phase'",
        (dream_id,),
    )
    return {"latest_dream": latest[0], "by_status": rows, "latest_phase_summary": phases[0] if phases else None}


@app.get("/api/telemetry/runs", tags=["Dream"])
def telemetry_runs(
    limit: int = Query(20, ge=1, le=100),
    run_type: str = Query(None, description="Filter by run type: dream_full / skill_auto_loop / skill_audit"),
):
    if not isinstance(limit, int):
        limit = 20
    if not isinstance(run_type, str):
        run_type = None
    runs = telemetry_store.list_runs(limit=limit, run_type=run_type, db_path=DREAM_LOG_DB)
    return {"runs": runs, "total": len(runs)}


@app.get("/api/telemetry/runs/summary", tags=["Dream"])
def telemetry_runs_summary():
    return telemetry_store.summary(db_path=DREAM_LOG_DB)


# ── Entry Point ──────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Mnemosyne REST API")
    parser.add_argument("--port", type=int, default=8979)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Mnemosyne REST API — FastAPI

端点:
  GET  /api/health          健康检查
  POST /api/write           写入经验
  GET  /api/search          搜索（支持 vector/keyword/hybrid + layer）
  GET  /api/node/{id}       节点详情
  GET  /api/node/{id}/graph 节点关联图
  GET  /docs                Swagger UI
"""

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
import uvicorn

scripts_dir = Path(__file__).resolve().parent.parent
if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))

from core.sqlite_store import SQLiteStore
from core.embedder import HarrierEmbedder

app = FastAPI(
    title="Mnemosyne API",
    description="Bionic memory system for AI agents — REST API",
    version="5.0.0",
)

_store: Optional[SQLiteStore] = None


def _get_store() -> SQLiteStore:
    global _store
    if _store is None:
        _store = SQLiteStore(embedder=HarrierEmbedder())
    return _store


# ── Request / Response Models ───────────────────────────────


class WriteRequest(BaseModel):
    content: str = Field(..., description="Experience content (L2)")
    type: str = Field("experience", description="Node type: experience / correction / raw")
    principle: Optional[str] = Field(None, description="Abstract principle")
    project: Optional[str] = Field(None, description="Project name")
    tags: Optional[List[str]] = Field(None, description="Tags")
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
        project=req.project,
        tags=req.tags,
    )
    if req.contradicts:
        store.add_edge(node_id, req.contradicts, "contradicts", weight=0.7, source="api")
    return {"id": node_id}


@app.get("/api/search", response_model=SearchResponse, tags=["Memory"])
def search(
    q: str = Query(..., description="Search query"),
    layer: str = Query("L0", description="Return layer: L0 / L1 / L2"),
    mode: str = Query("hybrid", description="Search mode: vector / keyword / hybrid"),
    top: int = Query(5, ge=1, le=50, description="Max results"),
):
    store = _get_store()
    if mode == "vector":
        results = store.search_by_vector(q, top=top, layer=layer)
    elif mode == "keyword":
        results = store.search_by_keyword(q, top=top, layer=layer)
    else:
        results = store.search_hybrid(q, top=top, layer=layer)
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


# ── Entry Point ──────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Mnemosyne REST API")
    parser.add_argument("--port", type=int, default=8979)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()

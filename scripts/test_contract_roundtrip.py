#!/usr/bin/env python3
"""Contract round-trip tests for MCP, REST, edge semantics, and search filters."""

import json
import sys
import uuid
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

from core.utils import ensure_hf_offline, fix_windows_encoding

fix_windows_encoding()
ensure_hf_offline()

from api import start_api
from mcp_server import _handle_detail, _handle_search, _handle_update, _handle_write, _tools_list
from mcp_server import _get_store


def _as_dict(value):
    return value if isinstance(value, dict) else json.loads(value or "{}")


def _as_list(value):
    return value if isinstance(value, list) else json.loads(value or "[]")


def _find_node_by_marker(store, marker):
    conn = store._connect()
    try:
        row = conn.execute(
            "SELECT id FROM nodes WHERE metadata LIKE ? ORDER BY updated_at DESC LIMIT 1",
            (f"%{marker}%",),
        ).fetchone()
    finally:
        conn.close()
    assert row, f"node with marker {marker} should exist"
    return row[0]


def test_mcp_update_and_detail(store):
    marker = f"contract-mcp-{uuid.uuid4().hex}"
    _handle_write({
        "content": f"Contract MCP base node {marker}",
        "type": "experience",
        "principle": f"Contract MCP base {marker}",
        "task_type": "memory_system",
        "project": "memory-evolution",
        "tags": ["contract", "mcp"],
        "context_tags": ["contract_base"],
        "metadata": {"marker": marker, "phase": "write"},
    })
    node_id = _find_node_by_marker(store, marker)

    _handle_update({
        "id": node_id,
        "metadata": {"marker": marker, "phase": "update", "solution": "round-trip"},
        "context_tags": ["contract_update"],
        "tags": ["contract", "updated"],
        "precondition": f"MCP update precondition {marker}",
        "predicted_outcome": f"MCP update predicted outcome {marker}",
        "task_type": "memory_system",
        "project": "memory-evolution",
    })

    detail = json.loads(_handle_detail({"ids": [node_id]}))[0]
    assert detail["metadata"]["phase"] == "update"
    assert detail["metadata"]["solution"] == "round-trip"
    assert "contract_update" in detail["context_tags"]
    assert "updated" in detail["tags"]
    assert detail["precondition"] == f"MCP update precondition {marker}"
    assert detail["predicted_outcome"] == f"MCP update predicted outcome {marker}"
    return node_id


def test_rest_write_update(store):
    marker = f"contract-rest-{uuid.uuid4().hex}"
    req = start_api.WriteRequest(
        content=f"Contract REST base node {marker}",
        type="experience",
        principle=f"Contract REST base {marker}",
        task_type="memory_system",
        project="memory-evolution",
        tags=["contract", "rest"],
        context_tags=["rest_base"],
        metadata={"marker": marker, "phase": "write"},
        precondition=f"REST write precondition {marker}",
        predicted_outcome=f"REST write predicted outcome {marker}",
    )
    node_id = start_api.write(req)["id"]
    start_api.update_node(node_id, start_api.UpdateRequest(
        metadata={"marker": marker, "phase": "update", "problem": "REST field drift"},
        context_tags=["rest_update"],
        tags=["contract", "rest-updated"],
        precondition=f"REST update precondition {marker}",
        predicted_outcome=f"REST update predicted outcome {marker}",
    ))
    node = store.get_node(node_id)
    metadata = _as_dict(node["metadata"])
    context_tags = _as_list(node["context_tags"])
    tags = _as_list(node["tags"])
    assert metadata["phase"] == "update"
    assert metadata["problem"] == "REST field drift"
    assert "rest_update" in context_tags
    assert "rest-updated" in tags
    assert node["precondition"] == f"REST update precondition {marker}"
    assert node["predicted_outcome"] == f"REST update predicted outcome {marker}"
    return node_id


def test_edges_and_search(store, node_a, node_b):
    edge_id = store.add_edge(node_a, node_b, "solves", weight=0.55, source="contract_test", graph_dim="causal", strength="weak")
    if edge_id:
        edge = store.get_edge(edge_id)
    else:
        matches = store.query_edges(
            "from_id=? AND to_id=? AND relation_type=?",
            (node_a, node_b, "solves"),
        )
        edge = matches[0] if matches else None
    assert edge is not None
    assert edge["graph_dim"] == "causal"
    assert edge["strength"] == "weak"
    queried = store.query_edges("id=?", (edge["id"],))[0]
    assert queried["graph_dim"] == "causal"
    traversed = store.traverse(node_a, depth=1, max_results=10)
    assert any(item.get("graph_dim") == "causal" and item.get("strength") == "weak" for item in traversed)

    results = json.loads(_handle_search({
        "query": "Contract",
        "mode": "hybrid",
        "layer": "L2",
        "top": 10,
        "tags": ["memory_system", "memory-evolution"],
    }))
    assert results, "filtered hybrid search should return contract nodes"
    keyword_results = json.loads(_handle_search({
        "query": "mcp-field-test-with-hyphen",
        "mode": "keyword",
        "layer": "L2",
        "top": 5,
    }))
    assert isinstance(keyword_results, list)


def main():
    write_schema = next(tool for tool in _tools_list() if tool["name"] == "memory_write")["inputSchema"]
    update_schema = next(tool for tool in _tools_list() if tool["name"] == "memory_update")["inputSchema"]
    feedback_schema = next(tool for tool in _tools_list() if tool["name"] == "memory_skill_feedback")["inputSchema"]
    assert "metadata" in write_schema["properties"]
    assert "metadata" in update_schema["properties"]
    assert "task_type" in write_schema["required"]
    assert "outcome" in feedback_schema["required"]

    store = _get_store()
    node_a = test_mcp_update_and_detail(store)
    node_b = test_rest_write_update(store)
    test_edges_and_search(store, node_a, node_b)
    print(json.dumps({
        "status": "PASS",
        "mcp_node": node_a,
        "rest_node": node_b,
        "checks": ["mcp_update_detail", "rest_write_update", "edge_semantics", "search_filters", "keyword_error_handling"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

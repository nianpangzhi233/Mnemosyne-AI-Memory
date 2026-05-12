#!/usr/bin/env python3
"""Verify MCP memory_write preserves structured fields."""

import json
import sys
import uuid
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

from core.utils import ensure_hf_offline, fix_windows_encoding

fix_windows_encoding()
ensure_hf_offline()

from mcp_server import _handle_write, _tools_list
from mcp_server import _get_store


def main():
    schema = next(tool for tool in _tools_list() if tool["name"] == "memory_write")["inputSchema"]
    required = schema.get("required", [])
    assert "task_type" in required, "memory_write schema must require task_type"
    assert "metadata" in schema["properties"], "memory_write schema must expose metadata"

    marker = f"mcp-field-test-{uuid.uuid4().hex}"
    content = f"MCP field preservation test node {marker}: context_tags and metadata should round-trip."
    metadata = {
        "marker": marker,
        "outcome": "success",
        "problem": "MCP accepted fields but store could drop some of them",
        "solution": "pass metadata and context_tags through add_node",
        "root_cause": "add_node previously ignored kwargs metadata/context_tags",
        "entities": ["MCP", "SQLiteStore", "memory_write"],
        "evidence": ["schema", "handler", "get_node"],
    }
    args = {
        "content": content,
        "type": "experience",
        "principle": f"MCP write fields must round-trip to storage {marker}",
        "project": "memory-evolution",
        "tags": ["mcp", "field-test"],
        "task_type": "memory_system",
        "context_tags": ["custom_tag", "memory_system"],
        "precondition": "testing MCP memory_write structured field persistence",
        "predicted_outcome": "metadata and context_tags are available after get_node",
        "metadata": metadata,
    }

    result = _handle_write(args)
    node_id = result.split("Written node ", 1)[1].split("...", 1)[0]

    store = _get_store()
    conn = store._connect()
    try:
        row = conn.execute(
            "SELECT id FROM nodes WHERE metadata LIKE ? ORDER BY updated_at DESC LIMIT 1",
            (f"%{marker}%",),
        ).fetchone()
    finally:
        conn.close()
    node = store.get_node(row[0]) if row else None
    assert node is not None, "written node should be readable"

    saved_metadata = json.loads(node.get("metadata") or "{}")
    saved_context_tags = json.loads(node.get("context_tags") or "[]")

    assert saved_metadata["outcome"] == metadata["outcome"]
    assert saved_metadata["problem"] == metadata["problem"]
    assert saved_metadata["solution"] == metadata["solution"]
    assert saved_metadata["entities"] == metadata["entities"]
    assert "custom_tag" in saved_context_tags
    assert "memory_system" in saved_context_tags
    assert "memory-evolution" in saved_context_tags
    assert node.get("task_type") == "memory_system"
    assert node.get("precondition") == args["precondition"]
    assert node.get("predicted_outcome") == args["predicted_outcome"]

    print(json.dumps({
        "status": "PASS",
        "node_id": node["id"],
        "context_tags": saved_context_tags,
        "metadata_keys": sorted(saved_metadata.keys()),
        "task_type": node.get("task_type"),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

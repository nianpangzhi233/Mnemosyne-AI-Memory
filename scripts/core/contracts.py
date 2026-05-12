#!/usr/bin/env python3
"""Shared field contracts for Mnemosyne memory graph APIs."""

import json
from typing import Any, Dict, Iterable, Optional


NODE_WRITE_REQUIRED_FIELDS = {"content", "task_type"}

NODE_WRITE_FIELDS = {
    "content",
    "type",
    "node_type",
    "principle",
    "task_type",
    "project",
    "tags",
    "metadata",
    "context_tags",
    "precondition",
    "predicted_outcome",
}

NODE_UPDATE_FIELDS = {
    "content",
    "principle",
    "task_type",
    "project",
    "tags",
    "metadata",
    "context_tags",
    "precondition",
    "predicted_outcome",
    "confidence",
    "half_life_days",
    "tier",
    "decay_score",
    "base_score",
}

NODE_JSON_FIELDS = {"tags", "metadata", "context_tags"}

NODE_DETAIL_FIELDS = {
    "id",
    "type",
    "content",
    "principle",
    "tier",
    "decay_score",
    "base_score",
    "access_count",
    "last_access",
    "created_at",
    "updated_at",
    "task_type",
    "project",
    "tags",
    "metadata",
    "abstract",
    "overview",
    "confidence",
    "verified_at",
    "verified_count",
    "half_life_days",
    "precondition",
    "predicted_outcome",
    "context_tags",
}

EDGE_DETAIL_FIELDS = {
    "id",
    "from_id",
    "to_id",
    "relation_type",
    "weight",
    "source",
    "status",
    "created_at",
    "graph_dim",
    "strength",
}


def parse_json_list(value: Any) -> list:
    if not value:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else [value]
        except (json.JSONDecodeError, TypeError):
            return [value]
    return [value]


def parse_json_dict(value: Any) -> dict:
    if not value:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


def dumps_json_list(value: Any) -> str:
    return json.dumps(parse_json_list(value), ensure_ascii=False)


def dumps_json_dict(value: Any) -> str:
    return json.dumps(parse_json_dict(value), ensure_ascii=False)


def merge_json_lists(*values: Any) -> str:
    merged = []
    for value in values:
        merged.extend(parse_json_list(value))
    return json.dumps(list(dict.fromkeys(str(item) for item in merged if item)), ensure_ascii=False)


def merge_json_dicts(*values: Any) -> str:
    merged: Dict[str, Any] = {}
    for value in values:
        merged.update(parse_json_dict(value))
    return json.dumps(merged, ensure_ascii=False)


def build_context_tags(context_tags: Any, task_type: Optional[str], project: Optional[str]) -> str:
    tags = parse_json_list(context_tags)
    tags.extend(item for item in (task_type, project) if item)
    return json.dumps(list(dict.fromkeys(str(item) for item in tags if item)), ensure_ascii=False)


def serialize_node_fields(fields: Dict[str, Any]) -> Dict[str, Any]:
    serialized = dict(fields)
    if "tags" in serialized and not isinstance(serialized["tags"], str):
        serialized["tags"] = dumps_json_list(serialized["tags"])
    if "context_tags" in serialized and not isinstance(serialized["context_tags"], str):
        serialized["context_tags"] = dumps_json_list(serialized["context_tags"])
    if "metadata" in serialized and not isinstance(serialized["metadata"], str):
        serialized["metadata"] = dumps_json_dict(serialized["metadata"])
    return serialized


def deserialize_node(node: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if node is None:
        return None
    result = dict(node)
    result["tags"] = parse_json_list(result.get("tags"))
    result["context_tags"] = parse_json_list(result.get("context_tags"))
    result["metadata"] = parse_json_dict(result.get("metadata"))
    result.pop("precondition_vec", None)
    return result


def deserialize_nodes(nodes: Iterable[Dict[str, Any]]) -> list:
    return [deserialize_node(node) for node in nodes]


def deserialize_edge(edge: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    return dict(edge) if edge is not None else None

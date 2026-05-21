#!/usr/bin/env python3
"""Mnemosyne MCP Server — stdio transport

零依赖实现 MCP 协议（JSON-RPC over stdin/stdout）。
提供长期记忆工具和 v7.0 Skill Memory System 工具。
"""

import json
import sys
import os

from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stdin.reconfigure(encoding='utf-8', errors='replace')

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from core.utils import fix_windows_encoding, ensure_hf_offline

fix_windows_encoding()
ensure_hf_offline()

from core import SQLiteStore, HarrierEmbedder
from core.contracts import deserialize_node, serialize_node_fields

_store = None


def _get_store():
    global _store
    if _store is None:
        _store = SQLiteStore(embedder=HarrierEmbedder())
    return _store


def _clean_surrogates(text):
    if isinstance(text, str):
        return text.encode("utf-8", errors="surrogatepass").decode("utf-8", errors="replace")
    return text


def _send(msg):
    sys.stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _send_error(msg_id, code, message):
    _send({
        "jsonrpc": "2.0",
        "id": msg_id,
        "error": {"code": code, "message": message},
    })


def _get_registered_task_types():
    try:
        store = _get_store()
        conn = store._connect()
        try:
            row = conn.execute(
                "SELECT value FROM meta WHERE key='registered_task_types'"
            ).fetchone()
            if row:
                import json
                return json.loads(row[0])
        finally:
            conn.close()
    except Exception:
        pass
    return []


def _tools_list():
    registered_types = _get_registered_task_types()
    types_str = ", ".join(registered_types) if registered_types else "none yet"
    task_type_desc = (
        "REQUIRED. Classify this memory into a task category. "
        "Current registered types: [" + types_str + "]. "
        "Pick the best match from these types. "
        "If none fits, invent a new snake_case category name — it will be auto-registered for future use."
    )
    return [
        {
            "name": "memory_write",
            "description": "Write an experience or observation to long-term memory. "
                           "Use when: completing a significant task, being corrected, "
                           "discovering an important pattern, or recording a decision.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "The full content to store (L2 raw material)"
                    },
                    "type": {
                        "type": "string",
                        "enum": ["experience", "correction", "raw"],
                        "default": "experience",
                        "description": "Node type: experience=distilled insight, correction=overriding old knowledge, raw=unprocessed conversation fragment"
                    },
                    "principle": {
                        "type": "string",
                        "description": "Abstract principle extracted from this content (optional)"
                    },
                    "project": {
                        "type": "string",
                        "description": "Project name (optional)"
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Tags for categorization (optional)"
                    },
                    "precondition": {
                        "type": "string",
                        "description": "Environmental condition (optional)"
                    },
                    "predicted_outcome": {
                        "type": "string",
                        "description": "Predicted result (optional)"
                    },
                    "context_tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Tags for filtered search (optional)"
                    },
                    "contradicts": {
                        "type": "string",
                        "description": "Node ID being corrected (optional, for corrections)"
                    },
                    "task_type": {
                        "type": "string",
                        "description": task_type_desc
                    },
                    "metadata": {
                        "type": "object",
                        "description": "Structured metadata such as outcome, problem, solution, root_cause, entities, evidence"
                    }
                },
                "required": ["content", "task_type"]
            }
        },
        {
            "name": "memory_search",
            "description": "Search long-term memory. Returns L0 abstracts by default for token efficiency. "
                           "Use L1 for overview, L2 for full content.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query in natural language"},
                    "top": {"type": "integer", "default": 5, "description": "Max results"},
                    "layer": {
                        "type": "string",
                        "enum": ["L0", "L1", "L2"],
                        "default": "L0",
                        "description": "L0=abstract only (~100 tokens), L1=+overview (~500), L2=full content"
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["precise", "creative", "vector", "keyword", "hybrid"],
                        "default": "hybrid",
                        "description": "Search mode"
                    },
                    "graph_dim": {
                        "type": "string",
                        "description": "Filter by graph dimension: semantic/temporal/causal/entity"
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filter by context tags"
                    }
                },
                "required": ["query"]
            }
        },
        {
            "name": "memory_inject",
            "description": "Get relevant memory chains for current context. "
                           "Call at session start to load relevant past experiences.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "context": {
                        "type": "string",
                        "description": "Current working directory, task description, or project name"
                    },
                    "max_chars": {
                        "type": "integer",
                        "default": 500,
                        "description": "Max total characters to return"
                    }
                },
                "required": ["context"]
            }
        },
        {
            "name": "memory_detail",
            "description": "Fetch full L2 content for specific node IDs found via memory_search.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Node IDs to fetch details for"
                    }
                },
                "required": ["ids"]
            }
        },
        {
            "name": "memory_update",
            "description": "Update an existing memory node's fields",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "Node ID to update"},
                    "content": {"type": "string", "description": "New content (optional)"},
                    "confidence": {"type": "number", "description": "New confidence 0-1.5 (optional)"},
                    "context_tags": {"type": "array", "items": {"type": "string"}, "description": "New tags (optional)"},
                    "principle": {"type": "string", "description": "New principle (optional)"},
                    "task_type": {"type": "string", "description": "New task category (optional)"},
                    "project": {"type": "string", "description": "New project (optional)"},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "New node tags (optional)"},
                    "metadata": {"type": "object", "description": "New or replacement structured metadata (optional)"},
                    "precondition": {"type": "string", "description": "New precondition (optional)"},
                    "predicted_outcome": {"type": "string", "description": "New predicted outcome (optional)"},
                    "half_life_days": {"type": "number", "description": "Memory half-life in days (optional)"},
                    "tier": {"type": "string", "description": "Memory tier (optional)"},
                    "decay_score": {"type": "number", "description": "Decay score (optional)"},
                    "base_score": {"type": "number", "description": "Base score (optional)"}
                },
                "required": ["id"]
            }
        },
        {
            "name": "memory_delete",
            "description": "Delete a memory node and all its edges",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "Node ID to delete"}
                },
                "required": ["id"]
            }
        },
        {
            "name": "memory_crystallize",
            "description": "Crystallize source memory nodes into a skill draft/embryo. Creates a skill node, skill_artifact, and crystallized_from edges.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Skill name"},
                    "source_node_ids": {"type": "array", "items": {"type": "string"}, "description": "Source memory node IDs"},
                    "content": {"type": "string", "description": "Optional full skill content"},
                    "status": {"type": "string", "enum": ["embryo", "draft"], "default": "draft", "description": "Initial status"},
                    "trigger_patterns": {"type": "array", "items": {"type": "string"}, "description": "Trigger patterns"},
                    "preconditions": {"type": "array", "items": {"type": "string"}, "description": "Preconditions"},
                    "procedure": {"type": "array", "items": {"type": "string"}, "description": "Procedure steps"},
                    "verification": {"type": "string", "description": "Verification method"},
                    "failure_modes": {"type": "array", "items": {"type": "string"}, "description": "Known failure modes"},
                    "risk_level": {"type": "string", "enum": ["low", "medium", "high"], "default": "medium"},
                    "metadata": {"type": "object", "description": "Extra metadata"}
                },
                "required": ["name", "source_node_ids"]
            }
        },
        {
            "name": "memory_skill_search",
            "description": "Search skill artifacts. Discovery only; this does not mean a skill is safe to inject.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Task or problem to match against known skills"},
                    "top": {"type": "integer", "default": 5, "description": "Max skills to return"},
                    "min_similarity": {"type": "number", "default": 0.45, "description": "Minimum vector similarity required"},
                    "statuses": {"type": "array", "items": {"type": "string"}, "description": "Optional status filter"},
                    "include_deprecated": {"type": "boolean", "default": False, "description": "Include deprecated skills when no statuses filter is provided"}
                },
                "required": ["query"]
            }
        },
        {
            "name": "memory_skill_inject",
            "description": "Inject compact skill pointers for the current context. Returns short references, not full SOPs.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "context": {"type": "string", "description": "Current task/context"},
                    "max_chars": {"type": "integer", "default": 800, "description": "Max characters to return"},
                    "top": {"type": "integer", "default": 3, "description": "Max skills to include"},
                    "min_similarity": {"type": "number", "default": 0.45, "description": "Minimum vector similarity required"},
                    "mode": {"type": "string", "enum": ["default", "experimental", "trial"], "default": "default", "description": "Injection mode. Default only injects approved skills."}
                },
                "required": ["context"]
            }
        },
        {
            "name": "memory_skill_approve",
            "description": "Approve a skill for default injection. Requires at least one verified_by edge.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "skill_id": {"type": "string", "description": "Skill node ID"},
                    "approval_mode": {"type": "string", "default": "manual", "description": "manual | auto_experimental | auto_strict"}
                },
                "required": ["skill_id"]
            }
        },
        {
            "name": "memory_skill_feedback",
            "description": "Record skill usage feedback and update graph edges plus trial counters.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "skill_id": {"type": "string", "description": "Skill node ID"},
                    "rating": {"type": "string", "enum": ["helpful", "not_helpful", "misleading", "partially_useful"]},
                    "outcome": {"type": "string", "enum": ["success", "partial", "miss", "misleading", "trigger_mismatch"]},
                    "note": {"type": "string"},
                    "task_context": {"type": "string"},
                    "used_as": {"type": "string", "enum": ["approved", "trial", "experimental"], "default": "trial"},
                    "verification_result": {"type": "string"},
                    "create_test_prompt": {"type": "boolean", "default": False},
                    "expected": {"type": "string"},
                    "prompt_tags": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["skill_id", "outcome"]
            }
        },
        {
            "name": "memory_skill_deprecate",
            "description": "Soft-deprecate a skill. Keeps node, artifact, file, and evidence chain.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "skill_id": {"type": "string", "description": "Skill node ID"},
                    "reason": {"type": "string", "description": "Deprecation reason"}
                },
                "required": ["skill_id"]
            }
        }
    ]


def _handle_write(args):
    store = _get_store()
    content = args["content"]
    node_type = args.get("type", "experience")
    principle = args.get("principle")
    project = args.get("project")
    tags = args.get("tags", [])
    precondition = args.get("precondition")
    predicted_outcome = args.get("predicted_outcome")
    context_tags = args.get("context_tags")
    task_type = args.get("task_type")
    metadata = args.get("metadata", {})

    node_id = store.add_node(
        content=content, node_type=node_type,
        principle=principle, project=project, tags=tags,
        precondition=precondition, predicted_outcome=predicted_outcome,
        context_tags=context_tags, task_type=task_type, metadata=metadata,
    )

    contradicts_id = args.get("contradicts")
    if contradicts_id:
        store.add_edge(node_id, contradicts_id, "contradicts",
                        weight=0.8, source="auto")

    return _clean_surrogates(f"Written node {node_id[:8]}... (type={node_type})")


def _handle_search(args):
    store = _get_store()
    query = args["query"]
    top = args.get("top", 5)
    layer = args.get("layer", "L0")
    mode = args.get("mode", "hybrid")
    graph_dim = args.get("graph_dim")
    tags = args.get("tags")

    if mode in ("precise", "creative"):
        results = store.search_spreading(query, mode=mode, graph_dims=[graph_dim] if graph_dim else None, tags=tags, top=top, layer=layer)
    elif mode == "vector":
        results = store.search_by_vector(query, top=top, layer=layer, tags=tags)
    elif mode == "keyword":
        try:
            results = store.search_by_keyword(query, top=top, layer=layer, tags=tags)
        except Exception:
            results = []
    else:
        results = store.search_hybrid(query, top=top, layer=layer, tags=tags)

    return _clean_surrogates(json.dumps(results, ensure_ascii=False, indent=2))


def _handle_inject(args):
    from graph_query import inject as _inject
    context = args["context"]
    max_chars = args.get("max_chars", 500)
    output = _inject(context, max_chars)

    store = _get_store()
    try:
        context_vec = store._embedder.encode(context)
        pre_matches = store.match_preconditions(context_vec, top=3)
        if pre_matches:
            output += "\n\n⚠️ 环境预警:"
            for pm in pre_matches:
                output += f"\n  - {pm['precondition']}: 预测\"{pm['predicted_outcome'][:50]}\" (置信度:{pm['confidence']:.2f})"
    except Exception:
        pass

    return _clean_surrogates(output) if output else "No relevant memories found"


def _handle_detail(args):
    store = _get_store()
    ids = args.get("ids", [])
    results = []
    for nid in ids:
        node = store.get_node(nid)
        if node:
            results.append(deserialize_node(node))
    return _clean_surrogates(json.dumps(results, ensure_ascii=False, indent=2))


def _handle_update(args):
    store = _get_store()
    node_id = args["id"]
    fields = {}
    for key in (
        "content", "confidence", "context_tags", "principle", "task_type", "project",
        "tags", "metadata", "precondition", "predicted_outcome", "half_life_days",
        "tier", "decay_score", "base_score",
    ):
        if key in args:
            fields[key] = args[key]
    fields = serialize_node_fields(fields)
    ok = store.update_node(node_id, **fields)
    return f"Updated {node_id[:8]}..." if ok else f"Node {node_id[:8]} not found"


def _handle_delete(args):
    store = _get_store()
    node_id = args["id"]
    ok = store.delete_node(node_id)
    return f"Deleted {node_id[:8]}..." if ok else f"Node {node_id[:8]} not found"


def _handle_crystallize(args):
    store = _get_store()
    node_id = store.create_skill_artifact(
        name=args["name"],
        source_node_ids=args["source_node_ids"],
        content=args.get("content"),
        status=args.get("status", "draft"),
        trigger_patterns=args.get("trigger_patterns", []),
        preconditions=args.get("preconditions", []),
        procedure=args.get("procedure", []),
        verification=args.get("verification"),
        failure_modes=args.get("failure_modes", []),
        risk_level=args.get("risk_level", "medium"),
        metadata=args.get("metadata", {}),
    )
    artifact = store.get_skill_artifact(node_id)
    return _clean_surrogates(json.dumps({"skill_id": node_id, "artifact": artifact}, ensure_ascii=False, indent=2))


def _handle_skill_search(args):
    store = _get_store()
    query = args["query"]
    top = args.get("top", 5)
    min_similarity = args.get("min_similarity", 0.45)
    statuses = args.get("statuses")
    include_deprecated = args.get("include_deprecated", False)
    results = store.search_skills(query, top=top, min_similarity=min_similarity,
                                  statuses=statuses, include_deprecated=include_deprecated)
    return _clean_surrogates(json.dumps(results, ensure_ascii=False, indent=2))


def _handle_skill_inject(args):
    store = _get_store()
    context = args["context"]
    max_chars = args.get("max_chars", 800)
    top = args.get("top", 3)
    min_similarity = args.get("min_similarity", 0.45)
    mode = args.get("mode", "default")
    output = store.inject_skills(context, max_chars=max_chars, top=top,
                                 min_similarity=min_similarity, mode=mode)
    return _clean_surrogates(output) if output else "No relevant skills found"


def _handle_skill_approve(args):
    store = _get_store()
    result = store.approve_skill(args["skill_id"], approval_mode=args.get("approval_mode", "manual"))
    return _clean_surrogates(json.dumps(result, ensure_ascii=False, indent=2))


def _handle_skill_feedback(args):
    store = _get_store()
    result = store.skill_feedback(
        args["skill_id"],
        args.get("rating"),
        note=args.get("note", ""),
        task_context=args.get("task_context", ""),
        used_as=args.get("used_as", "trial"),
        verification_result=args.get("verification_result", ""),
        outcome=args.get("outcome"),
        create_test_prompt=args.get("create_test_prompt", False),
        expected=args.get("expected", ""),
        prompt_tags=args.get("prompt_tags"),
    )
    return _clean_surrogates(json.dumps(result, ensure_ascii=False, indent=2))


def _handle_skill_deprecate(args):
    store = _get_store()
    result = store.deprecate_skill(args["skill_id"], reason=args.get("reason", ""))
    return _clean_surrogates(json.dumps(result, ensure_ascii=False, indent=2))


_HANDLERS = {
    "memory_write": _handle_write,
    "memory_search": _handle_search,
    "memory_inject": _handle_inject,
    "memory_detail": _handle_detail,
    "memory_update": _handle_update,
    "memory_delete": _handle_delete,
    "memory_crystallize": _handle_crystallize,
    "memory_skill_search": _handle_skill_search,
    "memory_skill_inject": _handle_skill_inject,
    "memory_skill_approve": _handle_skill_approve,
    "memory_skill_feedback": _handle_skill_feedback,
    "memory_skill_deprecate": _handle_skill_deprecate,
}


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue

        method = msg.get("method", "")
        msg_id = msg.get("id")
        params = msg.get("params", {})

        if method == "initialize":
            _send({
                "jsonrpc": "2.0", "id": msg_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {"listChanged": False},
                        "prompts": {"listChanged": False},
                        "resources": {"subscribe": False, "listChanged": False},
                    },
                    "serverInfo": {"name": "mnemosyne", "version": "7.2.0"}
                }
            })

        elif method == "notifications/initialized":
            pass

        elif method == "tools/list":
            _send({
                "jsonrpc": "2.0", "id": msg_id,
                "result": {"tools": _tools_list()}
            })

        elif method == "prompts/list":
            _send({
                "jsonrpc": "2.0", "id": msg_id,
                "result": {"prompts": []}
            })

        elif method == "resources/list":
            _send({
                "jsonrpc": "2.0", "id": msg_id,
                "result": {"resources": []}
            })

        elif method == "resources/templates/list":
            _send({
                "jsonrpc": "2.0", "id": msg_id,
                "result": {"resourceTemplates": []}
            })

        elif method == "prompts/get":
            _send_error(msg_id, -32602, "No prompts are available")

        elif method == "resources/read":
            _send_error(msg_id, -32602, "No resources are available")

        elif method == "tools/call":
            tool_name = params.get("name", "")
            tool_args = params.get("arguments", {})
            handler = _HANDLERS.get(tool_name)

            if handler:
                try:
                    result = handler(tool_args)
                    _send({
                        "jsonrpc": "2.0", "id": msg_id,
                        "result": {
                            "content": [{"type": "text", "text": str(result)}],
                            "isError": False
                        }
                    })
                except Exception as e:
                    _send({
                        "jsonrpc": "2.0", "id": msg_id,
                        "result": {
                            "content": [{"type": "text", "text": f"Error: {e}"}],
                            "isError": True
                        }
                    })
            else:
                _send({
                    "jsonrpc": "2.0", "id": msg_id,
                    "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"}
                })

        elif method == "shutdown":
            _send({"jsonrpc": "2.0", "id": msg_id, "result": None})
            break

        elif msg_id is not None:
            _send_error(msg_id, -32601, f"Unknown method: {method}")


if __name__ == "__main__":
    main()

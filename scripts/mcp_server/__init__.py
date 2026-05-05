#!/usr/bin/env python3
"""Mnemosyne MCP Server — stdio transport

零依赖实现 MCP 协议（JSON-RPC over stdin/stdout）。
提供 4 个工具：memory_write, memory_search, memory_inject, memory_detail
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


def _tools_list():
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
                    "contradicts": {
                        "type": "string",
                        "description": "Node ID being corrected (optional, for corrections)"
                    }
                },
                "required": ["content"]
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
                        "enum": ["vector", "keyword", "hybrid"],
                        "default": "hybrid",
                        "description": "Search mode"
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
        }
    ]


def _handle_write(args):
    store = _get_store()
    content = args["content"]
    node_type = args.get("type", "experience")
    principle = args.get("principle")
    project = args.get("project")
    tags = args.get("tags", [])

    node_id = store.add_node(
        content=content, node_type=node_type,
        principle=principle, project=project, tags=tags
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

    if mode == "vector":
        results = store.search_by_vector(query, top=top, layer=layer)
    elif mode == "keyword":
        results = store.search_by_keyword(query, top=top, layer=layer)
    else:
        results = store.search_hybrid(query, top=top, layer=layer)

    return _clean_surrogates(json.dumps(results, ensure_ascii=False, indent=2))


def _handle_inject(args):
    from graph_query import inject as _inject
    context = args["context"]
    max_chars = args.get("max_chars", 500)
    output = _inject(context, max_chars)
    return _clean_surrogates(output) if output else "No relevant memories found"


def _handle_detail(args):
    store = _get_store()
    ids = args.get("ids", [])
    results = []
    for nid in ids:
        node = store.get_node(nid)
        if node:
            results.append({
                "id": node["id"],
                "content": node.get("content", ""),
                "principle": node.get("principle"),
                "tier": node.get("tier"),
                "decay_score": node.get("decay_score"),
                "project": node.get("project"),
                "task_type": node.get("task_type"),
            })
    return _clean_surrogates(json.dumps(results, ensure_ascii=False, indent=2))


_HANDLERS = {
    "memory_write": _handle_write,
    "memory_search": _handle_search,
    "memory_inject": _handle_inject,
    "memory_detail": _handle_detail,
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
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": "mnemosyne", "version": "5.0.0"}
                }
            })

        elif method == "notifications/initialized":
            pass

        elif method == "tools/list":
            _send({
                "jsonrpc": "2.0", "id": msg_id,
                "result": {"tools": _tools_list()}
            })

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


if __name__ == "__main__":
    main()

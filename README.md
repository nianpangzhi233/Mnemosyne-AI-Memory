<div align="center">

# Mnemosyne

**Give your AI a brain that forgets, recalls, and dreams.**

Bionic Experience & Memory System — Knowledge Graph + Vector Search + Dream Integration + MCP

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue?style=flat-square)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green?style=flat-square)](LICENSE)
[![MCP Compatible](https://img.shields.io/badge/MCP-compatible-purple?style=flat-square)](https://modelcontextprotocol.io/)

[中文文档](docs/README_CN.md) · [Releases](https://github.com/nianpangzhi233/Mnemosyne-AI-Memory/releases)

</div>

---

## The Problem

AI assistants have a fatal flaw: **they can't remember.**

You spent 30 minutes explaining your project architecture — next day, it's gone. You corrected it 3 times to use `const` instead of `var` — 4th time, still writing `var`. You said "I prefer concise replies" — next session, it's writing essays again.

This isn't a bug, it's by design — every conversation starts from a blank slate.

**Mnemosyne fixes this.** Not a file store, not a diary, not keyword matching. It's a **living knowledge graph** — like a human brain that associates, forgets, and dreams.

---

## Quick Start

```bash
git clone https://github.com/nianpangzhi233/Mnemosyne-AI-Memory.git
cd Mnemosyne-AI-Memory
python setup.py
```

```python
# Write an experience
memory_write(content="Gzip request body must be decompressed before JSON.parse()",
             principle="Always check Content-Encoding header before parsing")

# Search memories
memory_search(query="request body parse failure", layer="L0")
# → Returns: "Always check Content-Encoding header" (~100 tokens only)

# Auto-inject relevant memories on startup (memories find you)
memory_inject(context="API proxy project")
```

---

## Core Features

### Three-Layer Memory (L0/L1/L2)

Inspired by ByteDance's OpenViking. Don't dump 50K tokens of context into every prompt:

| Layer | Size | Purpose |
|-------|------|---------|
| **L0** Abstract | ~100 tokens | Quick relevance check, injected at startup |
| **L1** Overview | ~500 tokens | Enough for most queries |
| **L2** Full Content | Unlimited | When you actually need the details |

Result: **83% token cost reduction** with no loss in retrieval quality.

### Knowledge Graph

7 relation types connect scattered experiences into a network:

| Relation | Meaning | Example |
|----------|---------|---------|
| `is_a` | Categorize into abstract principle | "gzip decompress fail" → is_a → "check encoding first" |
| `similar_to` | Semantically similar (vector ≥ 0.85) | "response garbled" ≈ "JSON parse error" |
| `caused` | Causal chain | "no input validation" → caused → "production 500" |
| `solves` | Solution link | "added retry logic" → solves → "API timeout" |
| `contradicts` | New experience overrides old | "use approach A" ✗ "actually use B" |
| `transfers_to` | Cross-domain transfer | "Node.js error handling" → transfers to → "Python project" |
| `evolved_from` | Strategy distilled from cluster | Abstract strategy from multiple experiences |

### Dream (Automatic Consolidation)

The human brain consolidates memories during sleep. Mnemosyne does the same — a 13-phase pipeline that automatically discovers connections, distills strategies, and prunes stale memories.

Runs automatically at 3 AM and noon daily. Or trigger manually:

```bash
python scripts/graph_dream.py --full
```

### Automatic Conversation Learning

Scans opencode conversation logs, filters noise (chitchat, boilerplate, system warnings), and uses LLM to distill principles and summaries from valuable fragments — writing them into the memory graph.

You use AI normally, memories accumulate automatically. No manual recording needed.

### Privacy Guard

All auto-discovered relations go through a safety audit. Edges involving passwords, keys, ID numbers, or other sensitive information are automatically rejected.

---

## Integration

### MCP (Recommended)

Any AI tool that supports MCP (Model Context Protocol) can use Mnemosyne:

```json
{
  "mcpServers": {
    "mnemosyne": {
      "command": "python",
      "args": ["scripts/mcp_server/start_mcp.py"]
    }
  }
}
```

4 tools: `memory_write`, `memory_search`, `memory_inject`, `memory_detail`

### REST API

```bash
python scripts/api/start_api.py --port 8979
# Swagger docs: http://localhost:8979/docs

curl http://localhost:8979/api/health
# → {"status":"ok","nodes":149,"edges":104}

curl "http://localhost:8979/api/search?q=gzip&layer=L0&top=5"
```

### CLI

```bash
# Write
python scripts/graph_write.py --content "experience content" --principle "abstract principle"

# Search (semantic / keyword / hybrid)
python scripts/graph_query.py --vector-search "keyword" --layer L0 --top 5

# Health check
python scripts/graph_audit.py
```

---

## Dashboard

```bash
streamlit run scripts/dashboard/app.py --server.port 8501
```

| Page | Features |
|------|----------|
| Dashboard | Node/edge stats, type distribution, top memories |
| Search | Search + L0→L1→L2 progressive expand |
| Graph | D3.js force-directed graph (zoom, drag, type coloring) |
| Dream Log | 13-phase Gantt bars, click to expand details |

---

## Project Structure

```
scripts/
├── core/                # Abstraction layer (swappable components)
│   ├── graph_store.py   # Graph store interface
│   ├── sqlite_store.py  # SQLite impl (vectors + FTS5 + graph traversal)
│   ├── embedder.py      # Embedding interface (Harrier/BGE-M3/Qwen)
│   └── dream_pipeline.py # 13-phase dream pipeline
├── api/                 # FastAPI REST API + Swagger
├── mcp_server/          # MCP Server (zero dependencies, stdio)
├── dashboard/           # Streamlit visualization dashboard
├── log_scanner/         # Conversation log scanner + filter + distill
├── graph_write.py       # Write CLI
├── graph_query.py       # Query CLI
├── graph_dream.py       # Dream CLI
└── graph_audit.py       # Health report + cleanup
```

Every component is swappable through abstract interfaces:
- **Storage** (GraphStore) → SQLite / FAISS / Neo4j
- **Embedding** (Embedder) → Harrier / BGE-M3 / Qwen
- **Scheduler** (TaskRunner) → APScheduler / Celery

---

## Design Philosophy

Mnemosyne simulates three memory mechanisms of the human brain:

**Intuition** — Walk into a kitchen, automatically think "food." The environment triggers memory. Startup injection does exactly this.

**Recall** — Someone asks "how did we make that dish?" and you actively search your memory. Vector search + graph traversal finds experiences and discovers deeper connections along relation edges.

**Dream** — During sleep, the brain replays events, consolidates connections, and prunes unused memories. The dream pipeline does the same thing — automatically.

| Human Brain | Mnemosyne |
|-------------|-----------|
| Hippocampus fast encoding | `memory_write` instant write |
| Neocortex slow consolidation | `graph_dream` 13-phase nightly pipeline |
| Retrieval-triggered reconsolidation | Auto touch + decay update on search |
| REM sleep abstraction | Optional 3-round LLM review |
| Synaptic pruning | Decay scoring + cold archival |
| Forgetting curve | `base_score × e^(-0.03 × days) × log₂(access+2)` |

---

## Configuration

### LLM Review (Optional)

Runs on pure rules by default — no LLM needed. For smarter review, create `llm_config.json`:

```json
{
  "enabled": true,
  "endpoint": "https://api.deepseek.com/chat/completions",
  "model": "deepseek-v4-flash",
  "api_key": "your-key"
}
```

### Embedding Models

| Model | Dimensions | Load Speed | Quality | License |
|-------|-----------|------------|---------|---------|
| [Harrier 0.6b](https://huggingface.co/microsoft/harrier-oss-v1-0.6b) (default) | 1024 | **1.2s** | MTEB #1 (2026) | MIT |
| BGE-M3 | 1024 | 11s | Strong | MIT |
| Qwen3-Embedding | 1024 | Medium | Strong | Apache 2.0 |

---

## Requirements

- Python 3.10+
- ~2GB disk space (embedding model)
- Fully local, no external services required

## License

[MIT](LICENSE)

## Acknowledgments

Neuroscience foundations:
- **CLS** (Complementary Learning Systems) — fast/slow dual memory
- **Reconsolidation** — re-encoding during retrieval
- **NREM + REM** — two-stage memory consolidation
- **Ebbinghaus Forgetting Curve** — exponential decay + spaced repetition

Inspired by: [OpenViking](https://github.com/bytedance/OpenViking) (L0/L1/L2 layered context)

---

<div align="center">

**[v5.0.0 Release Notes →](https://github.com/nianpangzhi233/Mnemosyne-AI-Memory/releases/tag/v5.0.0)**

</div>

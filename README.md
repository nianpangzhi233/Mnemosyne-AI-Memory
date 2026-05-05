<div align="center">

# Mnemosyne

> **Give your AI a memory that works like a brain — it associates, it forgets, it dreams.**

Bionic experience & memory system for AI agents. GraphRAG with knowledge graph,
L0/L1/L2 layered context, vector search, MCP integration, REST API, and dream-based consolidation.

**[English](#your-ai-has-a-problem) · [中文文档](docs/README_CN.md)**

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue?style=flat-square)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green?style=flat-square)](LICENSE)
[![Embedding: Harrier 0.6b](https://img.shields.io/badge/embedding-Harrier--0.6b-orange?style=flat-square)](https://huggingface.co/microsoft/harrier-oss-v1-0.6b)
[![MCP Compatible](https://img.shields.io/badge/MCP-compatible-purple?style=flat-square)](https://modelcontextprotocol.io/)

</div>

---

## Your AI Has a Problem

It can't remember anything.

Every conversation starts from scratch. The lessons you taught it, the mistakes it made, the preferences you set — all gone.

You spent 30 minutes explaining your project architecture. Next day? It forgot everything.

You corrected it 3 times: "use const, not var". The 4th time? Still writing var.

You said "I prefer functional style". Next session? Back to classes.

**Mnemosyne fixes this.**

It's not a file store. It's not a diary. It's not keyword matching.
It's a **living memory graph** — like a human brain, it associates, forgets, and dreams.

---

## What's New in v5.0

| Feature | Description |
|---------|-------------|
| **L0/L1/L2 Layered Context** | 3-layer memory: L0 abstract (~100 tok) → L1 overview (~500 tok) → L2 full content |
| **MCP Server** | Zero-dependency JSON-RPC over stdio — works with Claude Code, OpenCode, Cursor |
| **REST API** | FastAPI with Swagger UI, 6 endpoints for write/search/detail/graph |
| **Streamlit Dashboard** | 4-page visual panel: Dashboard, Search, Graph (D3.js), Dream Log (Gantt) |
| **Conversation Log Scanner** | Auto-scan opencode conversation logs → filter → distill into memory |
| **LLM Distillation** | Raw conversation fragments → LLM-powered extraction of principles & summaries |
| **Dream Log** | Full dream history with 13-phase Gantt visualization |
| **13-Phase Dream Pipeline** | Snapshot, LogScan, SimilarTo, Causal, Contradicts, Transfers, Strategy, Covenant, Decay, LLM Review, Distill, Sync, Audit |

---

## What It Does

### Semantic Association

Tell your AI "I like concise replies", and next time it starts writing a wall of text, it remembers your preference — not because it matched a keyword, but because it *understands* "verbose response" relates to your style preference.

### Layered Context (L0/L1/L2)

Inspired by [OpenViking](https://github.com/bytedance/OpenViking) — don't dump 50k tokens into every context. Instead:

| Layer | Size | When to Use |
|-------|------|-------------|
| L0 Abstract | ~100 tokens | Quick filtering, injection at session start |
| L1 Overview | ~500 tokens | Re-ranking, most queries stop here |
| L2 Full Content | Unlimited | Deep dive when truly needed |

**Result: 83% token cost reduction while maintaining retrieval quality.**

### Knowledge Graph

7 relationship types connect scattered experiences into a web:

| Relation | Meaning |
|----------|---------|
| `is_a` | Experience → abstract principle |
| `similar_to` | Semantic similarity (vector ≥ 0.85) |
| `caused` | "missing validation" → caused → "500 in production" |
| `solves` | "added retry logic" solves "API timeout" |
| `contradicts` | New experience overrides the old |
| `transfers_to` | Same principle, different domain |
| `evolved_from` | Strategy distilled from experience cluster |

### Dream Evolution

The human brain consolidates memories during sleep. Mnemosyne does the same — a 13-phase pipeline that discovers connections, generates strategies, and prunes stale memories.

| # | Phase | Brain Analog | What |
|---|-------|-------------|------|
| 1 | Snapshot | Prefrontal monitor | Record state, set safety caps |
| 2 | LogScan | Perception | Scan conversation logs, filter noise |
| 3 | SimilarTo | Pattern matching | Link similar experiences |
| 4 | Causal | Sequential memory | Detect cause → solution chains |
| 5 | Contradicts | Conflict resolution | Find contradictory experiences |
| 6 | Transfers | Cross-modal transfer | Cross-domain principle linking |
| 7 | Strategy | Skill extraction | Distill abstract strategies |
| 8 | Covenant | Moral compass | Veto privacy leaks & weak edges |
| 9 | Decay | Synaptic pruning | Recalculate scores, archive cold |
| 10 | LLM Review | REM sleep | Optional 3-round adaptive review |
| 11 | Distill | Memory consolidation | Raw fragments → experience + principle |
| 12 | Sync | Working memory | Export hot nodes to memory.md |
| 13 | Audit | Metacognition | Post-dream health check |

### MCP Integration

Connect Mnemosyne to any MCP-compatible AI tool:

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

4 tools available: `memory_write`, `memory_search`, `memory_inject`, `memory_detail`

### Privacy Guard

All auto-discovered relationships pass through a Covenant safety audit. Edges involving passwords, API keys, or sensitive data are automatically vetoed.

---

## Quick Start

```bash
git clone https://github.com/nianpangzhi233/Mnemosyne-AI-Memory.git
cd Mnemosyne-AI-Memory
python setup.py
```

That's it. One command handles everything.

### Record an Experience

```bash
python scripts/graph_write.py \
  --content "gzip-compressed request bodies must be decompressed before JSON.parse()" \
  --type experience \
  --principle "Always check Content-Encoding header before parsing"
```

Or via MCP / REST API:

```bash
# REST API
curl -X POST http://localhost:8979/api/write \
  -H "Content-Type: application/json" \
  -d '{"content":"API写入测试","type":"experience"}'
```

### Search Memory

```bash
# CLI — supports L0/L1/L2 layers
python scripts/graph_query.py --vector-search "request body parsing" --top 5 --layer L0

# REST API
curl "http://localhost:8979/api/search?q=gzip&layer=L0&top=5"
```

### Visual Dashboard

```bash
streamlit run scripts/dashboard/app.py --server.port 8501
```

4 pages: Dashboard (stats), Search (L0→L1→L2 progressive reveal), Graph (D3.js force-directed), Dream Log (13-phase Gantt).

### Dream (Nightly Consolidation)

```bash
# Full 13-phase dream cycle
python scripts/graph_dream.py --full
```

### REST API

```bash
python scripts/api/start_api.py --port 8979
# Swagger UI at http://localhost:8979/docs
```

---

## Architecture

```
mnemosyne/
├── scripts/
│   ├── core/                  # Plug-in architecture
│   │   ├── graph_store.py     # AbstractGraphStore (12+ methods)
│   │   ├── sqlite_store.py    # SQLiteStore: vector + FTS5 + L0/L1/L2 + graph traversal
│   │   ├── embedder.py        # AbstractEmbedder → Harrier / BGE-M3 / Qwen
│   │   ├── dream_pipeline.py  # 13 dream phases + dream log recording
│   │   ├── task_runner.py     # AbstractTaskRunner → APScheduler / Celery
│   │   └── utils.py           # Windows encoding + HF offline helpers
│   ├── api/                   # FastAPI REST API
│   ├── mcp_server/            # MCP Server (stdio, zero dependencies)
│   ├── dashboard/             # Streamlit visual panel
│   ├── log_scanner/           # Conversation log scanner + filter
│   ├── graph_write.py         # Write CLI
│   ├── graph_query.py         # Query CLI (vector / keyword / hybrid / inject)
│   ├── graph_dream.py         # Dream CLI
│   ├── graph_audit.py         # Health report + cleanup
│   ├── llm_judge.py           # Optional LLM REM review layer
│   └── re_embed.py            # Re-embed all nodes (model swap)
├── docs/
├── llm_config.json            # LLM review config (disabled by default)
├── meta.json
└── setup.py                   # One-command installer
```

Every component is swappable via abstract interfaces:
- **GraphStore** → SQLite (default) / FAISS / Neo4j / any graph DB
- **Embedder** → Harrier (default) / BGE-M3 / Qwen / any vector model
- **TaskRunner** → APScheduler (default) / Celery / any scheduler

---

## Configuration

### LLM Review (Optional)

Create `llm_config.json` to enable REM-style LLM review:

```json
{
  "enabled": true,
  "endpoint": "https://api.deepseek.com/chat/completions",
  "model": "deepseek-v4-flash",
  "api_key": "your-key",
  "max_tokens": 1024,
  "timeout": 120
}
```

When disabled (default), the system runs purely on rules — no LLM needed.

### Scheduled Dreams

```bash
# Linux/Mac: 3 AM + 12 PM daily
0 3,12 * * * cd /path/to/mnemosyne && python scripts/graph_dream.py --full

# Windows: Task Scheduler with dream.cmd
```

---

## Embedding Models

| Model | Dimensions | Load Time | Quality | License |
|-------|-----------|-----------|---------|---------|
| [Harrier-OSS-v1-0.6b](https://huggingface.co/microsoft/harrier-oss-v1-0.6b) | 1024 | **1.2s** | MTEB #1 (2026) | MIT |
| BGE-M3 | 1024 | 11s | Strong | MIT |
| Qwen3-Embedding | 1024 | Medium | Strong | Apache 2.0 |

Default: **Harrier** — 10x faster load, MTEB #1, 1024-dim compatible with BGE-M3.

---

## Design Philosophy

Mnemosyne mimics three layers of human memory:

| Brain | Mnemosyne |
|-------|-----------|
| Hippocampus fast encoding | `memory_write` — instant experience logging |
| Neocortex slow consolidation | `graph_dream` — nightly 13-phase pipeline |
| Retrieval-triggered reconsolidation | `search_by_vector` with touch & decay update |
| REM sleep abstraction | Optional LLM-powered 3-round review |
| Synaptic pruning | Decay scoring + cold archive |
| Forgetting curve | `base_score × e^(-0.03 × days) × log₂(access+2)` |

**Intuition** — You walk into a kitchen and automatically think "food". The environment triggered the memory. Startup injection does exactly this — pushes relevant experiences based on context.

**Recall** — Someone asks "how did we make that dish?" and you actively search your memory. Vector search + graph traversal finds experiences and discovers deeper connections.

**Dreaming** — During sleep, your brain replays events, consolidates connections, prunes unused memories. The dream pipeline does the same — automatically.

---

## Requirements

- Python 3.10+
- ~2GB disk space (embedding model)
- Optional: FastAPI + uvicorn (REST API), Streamlit (dashboard)
- Fully local — no external services or API keys needed (LLM review is optional)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

[MIT](LICENSE) — use it however you want.

## Acknowledgments

Brain science foundations:
- **CLS Theory** (Complementary Learning Systems) — fast/slow dual memory
- **Reconsolidation** — retrieval as re-encoding window
- **NREM replay + REM abstraction** — two-stage memory consolidation
- **Ebbinghaus Forgetting Curve** — exponential decay with spaced repetition

Inspired by [OpenViking](https://github.com/bytedance/OpenViking) (L0/L1/L2 layered context).

Built with [Harrier](https://huggingface.co/microsoft/harrier-oss-v1-0.6b),
[sentence-transformers](https://www.sbert.net/),
[SQLite FTS5](https://www.sqlite.org/fts5.html),
[FastAPI](https://fastapi.tiangolo.com/),
[Streamlit](https://streamlit.io/).

---

<div align="center">

**[What's New in v5.0.0 →](https://github.com/nianpangzhi233/Mnemosyne-AI-Memory/releases/tag/v5.0.0)**

</div>

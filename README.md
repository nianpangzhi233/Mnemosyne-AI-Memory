<div align="center">

# Mnemosyne

> **Give your AI a memory that works like a brain — it associates, it forgets, it dreams.**

Bionic memory system for AI agents. GraphRAG with knowledge graph,
vector search, and dream-based consolidation.

**[English](#your-ai-has-a-problem) · [中文文档](docs/README_CN.md)**

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue?style=flat-square)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green?style=flat-square)](LICENSE)
[![Embedding: Harrier 0.6b](https://img.shields.io/badge/embedding-Harrier--0.6b-orange?style=flat-square)](https://huggingface.co/microsoft/harrier-oss-v1-0.6b)

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

## What It Does

### Semantic Association

Tell your AI "I like concise replies", and next time it starts writing a wall of text, it remembers your preference — not because it matched a keyword, but because it *understands* "verbose response" relates to your style preference.

### Knowledge Graph

8 relationship types connect scattered experiences into a web:

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

The human brain consolidates memories during sleep. Mnemosyne does the same — an 11-phase pipeline that discovers connections, generates strategies, and prunes stale memories.

| # | Phase | Brain Analog | What |
|---|-------|-------------|------|
| 1 | Snapshot | Prefrontal monitor | Record state, set safety caps |
| 2 | SimilarTo | Pattern matching | Link similar experiences |
| 3 | Causal | Sequential memory | Detect cause → solution chains |
| 4 | Contradicts | Conflict resolution | Find contradictory experiences |
| 5 | Transfers | Cross-modal transfer | Cross-domain principle linking |
| 6 | Strategy | Skill extraction | Distill abstract strategies |
| 7 | Covenant | Moral compass | Veto privacy leaks & weak edges |
| 8 | Decay | Synaptic pruning | Recalculate scores, archive cold |
| 9 | LLM Review | REM sleep | Optional 3-round adaptive review |
| 10 | Sync | Working memory | Export hot nodes to memory.md |
| 11 | Audit | Metacognition | Post-dream health check |

### Intuition Injection

When a session starts, relevant experience chains are automatically injected based on your working directory.
**You don't need to remember to search your memory — your memory finds you.**

### Privacy Guard

All auto-discovered relationships pass through a Covenant safety audit. Edges involving passwords, API keys, or sensitive data are automatically vetoed.

---

## Quick Start

```bash
git clone https://github.com/nianpangzhi233/Mnemosyne-AI-Memory.git
cd Mnemosyne-AI-Memory
python setup.py
```

That's it. One command handles everything:

1. Checks Python 3.10+
2. Installs dependencies (torch, sentence-transformers, numpy, apscheduler)
3. Creates directory structure
4. Initializes SQLite database
5. Verifies installation

### Record an Experience

```bash
python scripts/graph_write.py \
  --content "gzip-compressed request bodies must be decompressed before JSON.parse()" \
  --type experience \
  --principle "Always check Content-Encoding header before parsing"
```

### Search Memory

```bash
# Semantic search — describe your problem in natural language
python scripts/graph_query.py --vector-search "request body parsing" --top 5

# Keyword search (FTS5) — exact match
python scripts/graph_query.py --keyword-search "gzip" --top 5

# Hybrid — best of both worlds
python scripts/graph_query.py --hybrid-search "API proxy gzip" --top 5
```

### Dream (Nightly Consolidation)

```bash
# Full 11-phase dream cycle
python scripts/graph_dream.py --full

# Stats only
python scripts/graph_dream.py --stats

# Run a single phase
python scripts/graph_dream.py --phase 2
```

### Health Check

```bash
python scripts/graph_audit.py              # Health report
python scripts/graph_audit.py --clean       # Preview cleanup
python scripts/graph_audit.py --clean --force  # Execute cleanup
```

---

## Architecture

```
mnemosyne/
├── scripts/
│   ├── core/                  # Plug-in architecture
│   │   ├── graph_store.py     # AbstractGraphStore (12+ methods)
│   │   ├── sqlite_store.py    # SQLiteStore: vector + FTS5 + graph traversal
│   │   ├── embedder.py        # AbstractEmbedder → Harrier / BGE-M3 / Qwen
│   │   ├── dream_pipeline.py  # 11 dream phases as plug-in classes
│   │   ├── task_runner.py     # AbstractTaskRunner → APScheduler / Celery
│   │   └── utils.py           # Windows encoding + HF offline helpers
│   ├── graph_write.py         # Write CLI
│   ├── graph_query.py         # Query CLI (vector / keyword / hybrid / inject)
│   ├── graph_dream.py         # Dream CLI
│   ├── graph_audit.py         # Health report + cleanup
│   ├── graph_init.py          # Database initialization
│   ├── llm_judge.py           # Optional LLM REM review layer
│   └── re_embed.py            # Re-embed all nodes (model swap)
├── engine/                    # Legacy rule engine configs
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
  "endpoint": "http://localhost:8978/v1/chat/completions",
  "model": "your-model-name",
  "max_tokens": 1024,
  "timeout": 120
}
```

When disabled (default), the system runs purely on rules — no LLM needed.

### Scheduled Dreams

```bash
# Linux/Mac: 3 AM daily
0 3 * * * cd /path/to/mnemosyne && python scripts/graph_dream.py --full

# Windows: use dream.cmd or Task Scheduler
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
| Hippocampus fast encoding | `graph_write` — instant experience logging |
| Neocortex slow consolidation | `graph_dream` — nightly 11-phase pipeline |
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
- Fully local — no external services or API keys needed

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

Built with [Harrier](https://huggingface.co/microsoft/harrier-oss-v1-0.6b),
[sentence-transformers](https://www.sbert.net/),
[SQLite FTS5](https://www.sqlite.org/fts5.html).

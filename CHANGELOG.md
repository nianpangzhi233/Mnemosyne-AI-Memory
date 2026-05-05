# Changelog

All notable changes to Mnemosyne will be documented in this file.

## [5.0.0] - 2026-05-05

### Added
- **L0/L1/L2 layered context** — 3-layer memory: abstract (~100 tok), overview (~500 tok), full content
- **MCP Server** — zero-dependency JSON-RPC over stdio, 4 tools (memory_write/search/inject/detail)
- **REST API** — FastAPI with 6 endpoints + Swagger UI (`/docs`)
- **Streamlit Dashboard** — 4-page visual panel (Dashboard, Search, Graph, Dream Log)
- **Conversation Log Scanner** — auto-scan opencode.db, filter noise, extract valuable fragments
- **LLM Distillation (DistillPhase)** — raw conversation fragments → LLM extracts principle + summary
- **Dream Log recording** — full dream history stored in `dream_log.db`
- **Dream Log visualization** — 13-phase Gantt bars with expand/collapse details
- **Custom D3.js force-directed graph** — zoom, pan, drag, type-colored nodes, edge legend
- **Kimi-style UI** — dark sidebar, rounded cards, `#0071e3` blue accent
- **Bilingual UI** — Chinese/English toggle on all dashboard pages
- **AGENTS.md MCP hooks** — auto-trigger rules for memory_write/search/inject in AI sessions
- Dream pipeline expanded from 11 → 13 phases (added LogScan + Distill)

### Changed
- Version bumped from v4.1 to **v5.0** — represents fundamental architecture shift
- System description changed from "memory system" to **"experience & memory system"**
- Scanner uses `text_factory = bytes` for correct UTF-8 on Windows
- MCP Server stdout uses `sys.stdout.reconfigure(encoding='utf-8')` to fix surrogate errors
- Dream pipeline records to `dream_log.db` for historical visualization
- `meta.json` version → 5.0.0

## [4.1.0] - 2026-05-05

### Added
- Core module abstraction layer (`AbstractGraphStore`, `AbstractEmbedder`, `AbstractTaskRunner`)
- 11-phase dream pipeline with plug-in architecture
- Harrier-OSS-v1-0.6b as default embedding model (10x faster than BGE-M3, MTEB #1)
- Semantic chain search with 55% cutoff + graph traversal expansion
- Principle-based exact classification reinforcement (base_score +0.1)
- LLM REM review with adaptive 3-round assessment (quick→deep→final)
- Undo log for LLM actions with 7-day auto-purge
- Confidence-based action tiers (high→execute, medium→tentative, low→propose only)
- `graph_audit.py` — health report + cleanup (template removal, duplicate merge)
- `re_embed.py` — full re-embedding tool for model swaps
- `setup.py` — one-command installer
- Covenant privacy audit — auto-detect and veto sensitive edges
- Windows encoding fix + HF offline helper in `core/utils.py`

### Changed
- All 8 dream phases refactored to use `AbstractGraphStore` interface only
- Embedding model default changed from BGE-M3 to Harrier (1024-dim compatible)
- `meta.json` version bumped to 4.1.0
- Search results now form coherent semantic chains instead of mixed hits

### Fixed
- Self-loop edge bug in `add_node` reinforcement
- Duplicate `finally` block residual in `sqlite_store.py`
- `HF_HUB_OFFLINE` now set at model-load time (not env var) for China network compatibility
- Thread pool leak in APScheduler runner

## [4.0.0] - 2026-05-01

### Added
- Initial GraphRAG architecture with SQLite + BGE-M3 + knowledge graph
- 6 core Python scripts (write, query, dream, init, audit, re_embed)
- 8 relation types: `is_a`, `similar_to`, `caused`, `solves`, `contradicts`, `transfers_to`, `evolved_from`
- FTS5 full-text search
- Three-tier memory: hot / warm / cold with decay scoring
- Dream-based consolidation with automatic edge discovery
- Covenant privacy guard
- `memory.md` hot node sync

## [3.0.2] - 2026-04-20

### Added
- Evolution engine with rule-based strategy generation
- Sensor, symbolic, causal, concept, world model, metacognitive modules

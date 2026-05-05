# Changelog

All notable changes to Mnemosyne will be documented in this file.

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

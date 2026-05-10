# Changelog

All notable changes to Mnemosyne will be documented in this file.

## [7.2.0-draft] - 2026-05-10

### Added
- **Skill Evidence Flow** — added structured `skill_usage_feedback` records, outcome-based feedback, and usage-loop metadata for governed skill learning.
- **Failure prompt creation** — `memory_skill_feedback` can now turn reproducible failures into `test-prompts.json` entries via `create_test_prompt`.
- **Approved skill audits** — added store-level audit helpers for sampling and failure-triggered review, including downgrade/deprecation decisions.
- **Skill daemon** — added a lightweight APScheduler-backed background daemon and Windows launcher for periodic dream cycles and audit scans.
- **v7.2 migration** — added `scripts/migrate_v71_to_v72.py` and schema support for skill usage feedback.
- **Evidence-flow docs** — added v7.2 design and development plan documents.

### Changed
- `memory_skill_feedback` now prefers canonical `outcome` values: `success`, `partial`, `miss`, `misleading`, and `trigger_mismatch`, while preserving legacy `rating` compatibility.
- Default skill injection now uses a conservative trigger/precondition gate so generic tasks do not pollute context with unrelated approved skills.
- OpenCode memory rules now explicitly require Skill MCP injection and feedback behavior rather than only configuring MCP availability.
- `Check Content-Encoding before parsing JSON body` was approved after real trial feedback and approval-gate validation.

### Fixed
- Generic OpenCode MCP tests no longer trigger unrelated SQLite encoding skills.
- Negated contexts such as "not about SQLite" no longer count as positive trigger matches.

## [7.1.0-draft] - 2026-05-10

### Added
- **Bilateral Skill Evolution engine** — skills can now be evaluated through real `baseline` vs `with_skill` runs plus independent judge output, then combined with Mnemosyne graph-governance scoring.
- **Runner abstraction** — added `AgentRunner` / `JudgeRunner` protocols, OpenAI-compatible runner adapters, and replay runners for deterministic tests.
- **Thin skill evaluation CLI** — `scripts/evaluate_skill.py` builds configurable runners and delegates to `core.skill_evolution.SkillEvolutionRunner`; no model is hard-coded.
- **Skill evaluation schema** — added `skill_test_prompts`, `skill_eval_runs`, and `skill_mutations`, plus latest bilateral decision fields on `skill_artifacts`.
- **Real test prompt artifacts** — skills can mirror `test-prompts.json` beside `SKILL.md`.
- **Bilateral design document** — added `docs/v7.1-bilateral-skill-evolution.md`.
- **Regression tests** — added standard-library unittest coverage for dry-run blocking, bilateral gates, runner injection, real eval recording, downgrade behavior, and prompt file mirroring.

### Changed
- `SkillMirrorEvolutionPhase` is now a mirror/format-check phase only; dry-run scoring cannot promote `draft` to `evolved`.
- `evolved` now means Darwin live tests improved behavior **and** Mnemosyne graph governance passed.
- `approve_skill` now requires evolved status, verified evidence, synced `SKILL.md` hash, positive live-test delta, and passing Darwin/Mnemosyne scores unless explicitly overridden.
- `SQLiteStore.run_skill_darwin_evaluation` delegates to the provider-agnostic `SkillEvolutionRunner`.
- `skills/skill-embryo-json` evolved through real four-prompt evaluation and now includes `test-prompts.json`.

### Fixed
- Existing `evolved` skills are downgraded to `needs_revision` when a later bilateral evaluation fails.
- `SKILL.md` mirrors are synced after bilateral decisions so file status matches DB state.

## [7.0.0] - 2026-05-09

### Added
- **Skill Memory System** — memory clusters can now crystallize into governed skill artifacts with lifecycle states: `embryo -> draft -> evolved -> approved -> deprecated`.
- **Skill schema** — added `skill_artifacts` and `skill_evolution_runs` tables plus v6.1→v7.0 migration script.
- **Skill emergence pipeline** — `SkillEmbryoPhase` discovers mature experience clusters from strong `similar_to` graph components.
- **LLM skill development** — `SkillDevelopmentPhase` turns embryos into operational draft skills with trigger, precondition, procedure, verification, failure mode, risk, and evidence fields.
- **SKILL.md mirrors** — generated skill files under `skills/<slug>/SKILL.md` with `file_hash` and `file_synced_at` tracking.
- **Dry-run Darwin evolution** — `SkillMirrorEvolutionPhase` scores skills using Mnemosyne/Darwin rubric heuristics and records evolution runs.
- **Skill governance MCP tools** — added `memory_crystallize`, `memory_skill_search`, `memory_skill_inject`, `memory_skill_approve`, `memory_skill_feedback`, and `memory_skill_deprecate`.
- **Approval gate** — skills must have at least one `verified_by` edge before they can become `approved` and enter default injection.
- **Feedback loop** — skill feedback writes `skill_feedback` nodes, creates `verified_by` / `fails_on` / `needs_revision` edges, and updates trial counters.

### Changed
- `memory_skill_search` now reads structured `skill_artifacts` instead of loose `nodes.metadata`.
- `memory_skill_inject` defaults to `approved + inject_enabled + verified_by` only; draft/evolved skills require explicit `experimental` or `trial` mode.
- Dream slow path now includes Skill phases after contradiction detection and before strategy generation.
- MCP server version is now `7.0.0`.
- `meta.json` version → 7.0.0.

### Fixed
- Skill file mirrors are synced after final status transitions so `SKILL.md` status matches DB state.
- Numbered procedure steps no longer render as `1. 1.` when LLM output already includes numbering.
- FTS5 special-character skill searches remain protected by vector fallback behavior.

## [6.1.0] - 2026-05-08

### Added
- **Three-layer biomimetic architecture** — write-time hippocampus validation, dream-time REM consolidation, optional prefrontal LLM judgment.
- **Incremental contradiction detection** — `ContradictsPhase` now scans new memories against indexed candidates instead of full O(n²) pairwise comparison.
- **Incremental similar-memory discovery** — `SimilarToPhase` processes new nodes against the existing graph instead of rescanning everything.
- **FAISS-backed VectorIndex** — fast in-memory vector routing with automatic numpy fallback when `faiss-cpu` is unavailable.
- **Creative search concept jumps** — `creative` mode can jump through `is_a` principle parents for wider association.
- **Write-time auto-association** — new memories can create weak `similar_to` links during encoding.

### Changed
- `memory_search` now supports 5 modes: `hybrid`, `precise`, `creative`, `vector`, `keyword`.
- Predictive validation reuses already-encoded vectors and searches `top=2` to avoid self-matching.
- Dream CLI documents v6.1 Fast/Slow flow and reuses a single embedder instance.
- Edge metadata backfilled with `graph_dim` and `strength` for multi-dimensional retrieval.
- Vector indexes use lazy rebuild after pruning or deletion instead of immediate full rebuild.
- `meta.json` version → 6.1.0.

### Fixed
- Moved `_get_last_dream_time` to the shared DreamPhase base class.
- Cleared stale deleted IDs after `VectorIndex.build()`.
- Principle merges now trigger association logic instead of bypassing graph updates.
- Restored `CausalPhase` in the dream pipeline.

## [6.0.0] - 2026-05-07

### Added
- **MAGMA-style graph dimensions** — semantic, temporal, causal, and entity dimensions over the same SQLite graph.
- **A-MEM-style memory evolution** — old memories can be verified, contradicted, strengthened, or weakened when new memories arrive.
- **Predictive Memory** — nodes can store `precondition`, `predicted_outcome`, `confidence`, `verified_at`, `verified_count`, and `half_life_days`.
- **SYNAPSE spreading activation** — precise and creative graph traversal for associative retrieval.
- **MCP update/delete tools** — MCP server expanded from 4 tools to 6 tools with `memory_update` and `memory_delete`.
- **Predictive injection warnings** — `memory_inject` can surface precondition matches before the agent repeats known mistakes.

### Changed
- Search upgraded from basic vector/keyword retrieval to graph-aware spreading activation.
- `GraphStore` interface expanded with update, delete, spreading search, precondition matching, and verification methods.
- Dream pipeline split into Fast/Slow paths for deterministic maintenance and deeper consolidation.
- Migration script upgrades v5.0 databases with new node and edge fields.

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

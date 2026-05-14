# External Project Lessons Blueprint

> Status: Planning report
> Scope: Mnemosyne-AI-Memory engineering roadmap after reviewing external project lessons
> Date: 2026-05-12

This report evaluates five external-project lessons and translates them into concrete, staged implementation plans for Mnemosyne-AI-Memory. It is based on the current repository state, not an abstract wishlist.

Code inspected before writing this report:

- `scripts/core/dream_pipeline.py`
- `scripts/skill_daemon.py`
- `scripts/api/start_api.py`
- `scripts/dashboard/pages/dashboard.py`
- `scripts/dashboard/pages/dream_log.py`
- `scripts/core/sqlite_store.py`
- `scripts/mcp_server/__init__.py`
- `tests/test_skill_evidence_flow.py`
- `tests/test_bilateral_skill_evolution.py`
- `scripts/test_mcp_memory_write_fields.py`
- `scripts/test_contract_roundtrip.py`
- `docs/v7.2-development-plan.md`
- `README.md`
- `ROADMAP.md`

## Executive Summary

The external recommendations are broadly correct, but they need to be reordered for Mnemosyne's current state.

- P0 quality defense is necessary, but the project is not starting from zero tests. Existing tests cover skill evidence, bilateral skill evolution, MCP field round-trip, REST update, edge semantics, and search filters. The missing safety net is dream phase contract testing.
- P1 explicit learning loop is the strongest product improvement. Dream currently produces engineering logs, not user-reviewable learning reports.
- P2 observability is needed because `skill_daemon.py` is still mostly a background black box. Telemetry should be persisted, not memory-only.
- P3 architecture documentation should become the canonical contributor entry point, using Mermaid diagrams and one current architecture page.
- P4 demo/video should come last, after report and telemetry are real enough to demonstrate.

Recommended order:

1. Sprint A: Contract Harness completion.
2. Sprint B: EvolutionReport explicit learning loop.
3. Sprint C: Persistent telemetry and API/dashboard observability.
4. Sprint D: Architecture documentation and diagrams.
5. Sprint E: Reproducible demo scenario and short video.

---

## Report 1: Quality Defense / Contract Harness

### Current State

The project already has meaningful tests:

- `tests/test_skill_evidence_flow.py`
  - Covers `skill_feedback()` outcomes, `skill_usage_feedback`, `verified_by`, `fails_on`, `needs_revision`, audit downgrade/deprecation, and MCP skill feedback.
- `tests/test_bilateral_skill_evolution.py`
  - Covers bilateral evolution, dry-run cannot promote, Mnemosyne/Darwin dual decision, approval rules, runner injection, and regression handling.
- `scripts/test_mcp_memory_write_fields.py`
  - Covers MCP `memory_write` field round-trip.
- `scripts/test_contract_roundtrip.py`
  - Covers MCP update/detail, REST write/update, edge semantics, search filters, and keyword error handling.

Important gaps remain:

- Dream phases have no golden scenario tests.
- `DecayPhase`, `CausalPhase`, `ConceptPhase`, `TransfersPhase`, and `AuditPhase` lack deterministic behavior contracts.
- `DreamPipeline.execute()` does not have direct tests for phase errors, warning propagation, and dream log writes.
- `skill_daemon.py` post-dream behavior lacks contract coverage.

### Root Problem

Skill governance has tests. Field contracts now have tests. Dream consolidation, however, is still too easy to change accidentally without knowing which behavior moved.

### Blueprint

Build a Contract Harness rather than a Parity Harness. There is no official Mnemosyne implementation to compare against; what we need is fixed-input fixed-output behavior.

Proposed test files:

```text
tests/test_dream_phase_contract.py
tests/test_dream_pipeline_contract.py
tests/test_skill_lifecycle_contract.py
tests/test_daemon_contract.py
tests/test_api_contract.py
```

### Implementation Method

#### Step 1: Dream Phase Golden Tests

Create `tests/test_dream_phase_contract.py` using a temp `graph.db` and a deterministic dummy embedder.

Cover:

- `DecayPhase`
  - Cold raw nodes do not revive.
  - Correction and experience weights remain stable.
  - Hot/warm/cold tier transitions are deterministic.
- `CausalPhase`
  - Only structured metadata with `problem`, `solution`, `entities`, and `outcome` creates `solves`.
  - Low similarity or insufficient shared entities creates no edge.
  - `caused` is not generated accidentally.
- `ConceptPhase`
  - Requires at least three experiences and at least two `task_type` values.
  - Single-domain repetition does not create cross-domain concepts.
- `TransfersPhase`
  - Requires concept-mediated grouping before `transfers_to` edges are created.
- `AuditPhase`
  - Warns or fails on graph growth anomalies and missing edge metadata.

#### Step 2: Dream Pipeline Contract

Create `tests/test_dream_pipeline_contract.py`.

Cover:

- Phase exception sets final dream status to `FAIL`.
- Phase `WARN` propagates to final dream status.
- Dream run writes into `dream_log.db`.
- Phase result schema remains stable.

#### Step 3: One-Command Test Entry

Add a small local test command later if needed:

```bash
python -m unittest discover tests
python scripts/test_mcp_memory_write_fields.py
python scripts/test_contract_roundtrip.py
```

### Affected Areas

- `scripts/core/dream_pipeline.py`
- `scripts/graph_dream.py`
- `scripts/core/sqlite_store.py`
- `scripts/skill_daemon.py`
- `tests/`
- CI workflow, if enabled.

### Acceptance Criteria

- Tests do not require a real LLM.
- Tests do not use the live `graph.db`.
- Tests are repeatable.
- Each core dream phase has at least one positive and one negative contract case.
- Dream algorithm changes become explicit behavior changes, not silent drift.

---

## Report 2: Explicit Learning Loop / EvolutionReport

### Current State

Dream logging already exists:

- `dream_log.db` contains `dreams`.
- `DreamPipeline.execute()` writes `started_at`, `finished_at`, `status`, node/edge counts, and phase results.
- `scripts/dashboard/pages/dream_log.py` shows phase bars and phase details.

The daemon also writes:

- `graph.db.meta:last_skill_auto_loop`
- `graph.db.meta:last_skill_auto_loop_at`

However, these are engineering logs, not user-reviewable learning reports.

The user still cannot quickly answer:

- What did the system learn last night?
- Which skill embryos were created?
- Which skills changed status?
- Which contradictions need review?
- Which conclusions have evidence?

### Root Problem

Mnemosyne has implicit learning, but not enough explicit, reviewable learning output.

### Blueprint

Add `EvolutionReportPhase` as a structural dream summary phase. It should generate a compact report after dream consolidation.

Suggested report shape:

```json
{
  "id": "...",
  "dream_id": "...",
  "created_at": "...",
  "status": "PASS",
  "summary": {
    "nodes_added": 3,
    "edges_added": 12,
    "skills_created": 1,
    "skills_evolved": 0,
    "contradictions": 2,
    "audit_alerts": 0
  },
  "sections": {
    "new_memories": [],
    "new_concepts": [],
    "new_skills": [],
    "skill_changes": [],
    "contradictions": [],
    "recommended_actions": []
  }
}
```

Recommended storage: add a table to `dream_log.db`.

```sql
CREATE TABLE IF NOT EXISTS evolution_reports (
  id TEXT PRIMARY KEY,
  dream_id TEXT,
  created_at TEXT NOT NULL,
  status TEXT,
  summary TEXT,
  sections TEXT,
  markdown TEXT
);
```

### Implementation Method

#### Step 1: Data Table

Add `evolution_reports` initialization near dream log initialization.

#### Step 2: Report Phase

Add `EvolutionReportPhase` to `scripts/core/dream_pipeline.py`.

First version should be deterministic and should not call an LLM.

Inputs:

- Phase results from the current dream run.
- Current graph summary.
- Skill artifacts changed recently.
- Active contradictions and audit alerts.

Output:

```python
{
    "status": "PASS",
    "report_id": "...",
    "skills_created": 1,
    "contradictions": 2,
    "actions": 3,
}
```

#### Step 3: Dashboard Panel

Add a dream report section to `scripts/dashboard/pages/dream_log.py`, or add a new page:

```text
scripts/dashboard/pages/evolution_report.py
```

Show:

- What changed.
- Which suggested actions need observable follow-up or feedback.
- New skill embryos.
- Contradictions.
- Evidence links.

#### Step 4: Review Actions

Provide buttons or links for:

- Start a low-risk skill trial.
- Mark `needs_revision`.
- Deprecate skill.
- Open evidence chain.
- Ignore a recommendation.

### Affected Areas

- `scripts/core/dream_pipeline.py`
- `scripts/graph_init.py`
- `scripts/dashboard/pages/dream_log.py`
- `scripts/dashboard/pages/skills.py`
- `scripts/skill_daemon.py`
- `scripts/api/start_api.py` if report APIs are exposed.

### Risks

- LLM-generated reports may become costly or noisy. First version should be structural only.
- Reports without evidence links are not trustworthy.
- Long reports will be ignored; default view should be short and action-oriented.

### Acceptance Criteria

- Every full dream can create one report.
- Dashboard can display the latest report.
- Each recommendation links back to evidence IDs.
- A failed dream still creates a failure report explaining where it failed.
- No LLM is required for the first version.

---

## Report 3: Daemon / Telemetry / Cost Observability

### Current State

`scripts/skill_daemon.py` currently:

- Runs `graph_dream.py --full`.
- Runs `run_skill_auto_loop_once()` after successful dream.
- Writes `last_skill_auto_loop` and `last_skill_auto_loop_at` into `graph.db.meta`.
- Logs audit requirements, but does not persist audit run history.

REST API currently exposes:

- `/api/health`
- `/api/write`
- `/api/search`
- `/api/node/{id}`
- `/api/node/{id}/graph`

Gaps:

- No persistent daemon run history.
- No telemetry API.
- No phase duration in dream logs, though dashboard has code paths that look for `duration_ms`.
- No LLM call count or cost tracking.

### Root Problem

The background learning system is not observable enough. If it slows down, fails, or silently skips work, users only see stale state or logs.

### Blueprint

Add lightweight local telemetry. Do not add external Langfuse dependency by default.

Recommended storage: extend `dream_log.db`.

```sql
CREATE TABLE IF NOT EXISTS telemetry_runs (
  id TEXT PRIMARY KEY,
  run_type TEXT NOT NULL,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  status TEXT,
  duration_ms INTEGER,
  summary TEXT,
  errors TEXT
);

CREATE TABLE IF NOT EXISTS telemetry_events (
  id TEXT PRIMARY KEY,
  run_id TEXT,
  event_type TEXT,
  created_at TEXT,
  payload TEXT
);
```

API endpoints:

```text
GET /api/telemetry/latest
GET /api/telemetry/runs?limit=20
GET /api/telemetry/summary?days=7
GET /api/cost?days=7
```

Cost tracking should start conservative:

- `llm_calls`
- `duration_ms`
- `provider`
- `model`
- `usage_known`
- `prompt_tokens`
- `completion_tokens`
- `estimated_cost`

If token usage is unknown, store `null`, not fake precision.

### Implementation Method

#### Step 1: Phase Duration

Update `DreamPipeline.execute()` to record:

- phase start time
- phase end time
- `duration_ms`
- error text if any

Append `duration_ms` into the phase result stored in `dream_log.db`.

#### Step 2: Telemetry Helper

Add:

```text
scripts/core/telemetry.py
```

Functions:

- `start_run(run_type)`
- `finish_run(run_id, status, summary=None, errors=None)`
- `record_event(run_id, event_type, payload)`
- `latest_run(run_type=None)`
- `summary(days=7)`

#### Step 3: Daemon Integration

Wrap:

- `run_dream_full()`
- `run_skill_auto_loop_once()`
- `run_skill_audit_once()`

#### Step 4: REST API

Add telemetry endpoints in `scripts/api/start_api.py`.

#### Step 5: Dashboard

Add dashboard cards:

- Latest daemon run.
- Latest dream duration.
- Latest failed run.
- Skill auto loop processed/errors.
- LLM call count.

### Affected Areas

- `scripts/core/dream_pipeline.py`
- `scripts/skill_daemon.py`
- `scripts/api/start_api.py`
- `scripts/dashboard/pages/dashboard.py`
- `scripts/graph_init.py`
- `scripts/core/telemetry.py`
- Telemetry tests.

### Risks

- Telemetry can become over-engineered. Keep it table-based and small.
- Cost reporting should not require external services.
- Token usage may be unavailable. Track call count first.

### Acceptance Criteria

- Dream phases include `duration_ms`.
- Each daemon cycle has a persistent telemetry run.
- API can return latest run and 7-day summary.
- Dashboard can show daemon health.
- Failures are persisted even when dream fails.

---

## Report 4: Architecture Understandability / Documentation Maps

### Current State

README already has a high-level visual overview:

- `assets/architecture.svg`
- `assets/dashboard-preview.svg`

Docs include versioned design files:

- `docs/v7.2-development-plan.md`
- `docs/v7.2-skill-evidence-flow.md`
- `docs/v7.1-bilateral-skill-evolution.md`
- `docs/v7.0-skill-memory-system.md`
- `docs/v6.0-design.md`
- `docs/v6.1-blueprint.md`

Gaps:

- No single canonical current architecture page.
- Versioned docs are useful, but they read like historical records.
- No current Mermaid diagrams for memory flow, dream pipeline, module dependencies, or skill lifecycle.

### Root Problem

The project is understandable after reading many files, but not quickly understandable from one current entry point.

### Blueprint

Create one canonical architecture entry:

```text
docs/architecture.md
docs/diagrams/memory-flow.mmd
docs/diagrams/dream-pipeline.mmd
docs/diagrams/skill-lifecycle.mmd
docs/diagrams/module-dependencies.mmd
docs/diagrams/telemetry-flow.mmd
```

Recommended diagrams:

1. Memory Flow
   - MCP/REST/CLI -> SQLiteStore -> graph.db -> DreamPipeline -> search/inject/dashboard.
2. Dream Pipeline
   - Snapshot -> SimilarTo -> LogScan -> Distill -> Causal -> Concept -> Transfers -> Contradicts -> SkillEmbryo -> SkillDevelopment -> SkillMirrorEvolution -> Strategy -> Covenant -> Decay -> Sync -> LLMReview -> Audit -> EvolutionReport.
3. Skill Lifecycle
   - embryo -> draft -> tested -> evolved -> approved -> needs_revision/deprecated.
4. Module Dependencies
   - Entry points, store, DBs, dream pipeline, daemon, dashboard.
5. Telemetry Flow
   - Dream/daemon/LLM client -> telemetry tables -> API -> dashboard.

### Implementation Method

#### Step 1: `docs/architecture.md`

Sections:

- System boundaries.
- Main entry points.
- Data model.
- Dream pipeline.
- Skill lifecycle.
- MCP/REST/Dashboard.
- Extension guide.

#### Step 2: Mermaid Diagrams

Use Mermaid `.mmd` for maintainability and GitHub rendering.

#### Step 3: README Link

Add a clear link near the existing visual overview:

```md
For the current implementation architecture, see docs/architecture.md.
```

#### Step 4: Versioned Docs Policy

Mark older version docs as design history and point contributors to `docs/architecture.md` for the current state.

### Affected Areas

- `README.md`
- `docs/architecture.md`
- `docs/diagrams/*.mmd`
- Existing versioned docs only need cross-links, not rewrites.

### Risks

- Diagrams can become stale. Keep them module-level, not function-level.
- Do not duplicate every README feature paragraph in architecture docs.

### Acceptance Criteria

- A new contributor can understand the system skeleton in about 10 minutes.
- Current phase order is documented accurately.
- Current skill lifecycle states and gates are documented accurately.
- README links to the canonical architecture page.

---

## Report 5: Community Cold Start / Demo Scenario

### Current State

Open-source packaging exists:

- README is substantial.
- GitHub Pages exists.
- ROADMAP already lists public demo dataset, screenshots, short demo video, and MCP client examples.

Missing pieces:

- Safe public demo dataset.
- Repeatable demo script.
- Complete scenario: multi-day conversation -> dream report -> skill feedback loop -> next-session injection.
- EvolutionReport and telemetry panels are not implemented yet.

### Root Problem

The project value is currently explained mostly through technical capability. The public demo should show a user-visible outcome:

> The AI remembers what was taught, dreams over it, finds repeated problems, proposes a governed skill, detects contradictions, and routes suggested actions into observable feedback loops.

### Blueprint

Add a reproducible demo package.

```text
demo/
  seed_conversations/
    day1.jsonl
    day2.jsonl
    day3.jsonl
  expected/
    dream-report.json
    approved-skill.md
  run_demo.py
  demo_script.md
```

Demo path:

1. Import three days of safe conversation samples.
2. Run log scan and dream.
3. Open dashboard.
4. Show dream report:
   - repeated problem found
   - skill embryo created
   - contradiction detected
5. One low-risk skill enters a trial feedback loop.
6. New task triggers `memory_skill_inject`.
7. Show telemetry confirming dream success and skill loop summary.

### Implementation Method

#### Step 1: Safe Demo Data

Use generic technical examples:

- gzip JSON request body parsing
- Windows encoding / mojibake
- SQLite migration gotchas
- React UI drift

No private logs. No API keys. No personal data.

#### Step 2: `demo/run_demo.py`

Responsibilities:

- Optionally initialize a demo DB.
- Import seed memories.
- Run dream.
- Output report ID.
- Print dashboard instructions.

#### Step 3: `demo/demo_script.md`

Three-minute script:

- 0:00 Problem: AI loses experience.
- 0:30 Import several days of work.
- 1:00 Dream extracts memory and contradictions.
- 1:40 Skill embryo and feedback-gated trial.
- 2:20 Next task auto-injects approved skill.
- 2:50 Summary: not a chat log, a governed evolving memory system.

#### Step 4: Video/GIF

Add to:

- README.
- GitHub Pages.
- Release notes.

### Affected Areas

- `demo/`
- `README.md`
- `docs/open-source-launch.md`
- Dashboard pages, after EvolutionReport exists.

### Risks

- Recording before the real loop works creates a misleading demo.
- Demo data that is too project-specific will not resonate.
- Demo must run without a paid LLM key.

### Acceptance Criteria

- Fresh clone can run the demo path.
- Demo works without real API keys.
- Demo shows memory write, dream, report, skill candidate, contradiction/evidence, and injection.
- README and project page can point to the demo.

---

## Integrated Sprint Plan

### Sprint A: Complete Contract Harness

Goal: make core behavior safe to refactor.

Tasks:

- Add `tests/test_dream_phase_contract.py`.
- Add `tests/test_dream_pipeline_contract.py`.
- Add or extend `tests/test_skill_lifecycle_contract.py`.
- Add daemon contract tests.
- Add one-command local test entry if needed.

Recommended first task:

```text
tests/test_dream_phase_contract.py
```

Start with:

- `DecayPhase`
- `CausalPhase`
- `ConceptPhase`
- `TransfersPhase`
- `AuditPhase`

### Sprint B: EvolutionReport Explicit Learning Loop

Goal: make dream output user-reviewable.

Tasks:

- Add `evolution_reports` table.
- Add `EvolutionReportPhase`.
- Add report JSON/Markdown output.
- Add dashboard dream report panel.
- Add evidence links and review actions.

### Sprint C: Persistent Telemetry

Goal: make daemon and dream observable.

Tasks:

- Add telemetry tables.
- Add phase `duration_ms`.
- Wrap daemon jobs in telemetry runs.
- Add `/api/telemetry/latest` and `/api/telemetry/summary`.
- Add dashboard health cards.

### Sprint D: Architecture Docs

Goal: make the project understandable in 10 minutes.

Tasks:

- Add `docs/architecture.md`.
- Add Mermaid diagrams.
- Link from README.
- Mark old version docs as historical context.

### Sprint E: Demo Cold Start

Goal: show user-visible value.

Tasks:

- Add safe demo dataset.
- Add `demo/run_demo.py`.
- Add `demo/demo_script.md`.
- Record short video or GIF after report and telemetry exist.

---

## Recommended Next Step

Start with Sprint A, specifically:

```text
tests/test_dream_phase_contract.py
```

Reason:

- Dream phases are the core of memory consolidation.
- EvolutionReport will only be trustworthy if dream phase outputs are stable.
- Telemetry and demo should not wrap unstable behavior in a prettier shell.

Suggested validation command after Sprint A starts:

```bash
python -m unittest discover tests
python scripts/test_mcp_memory_write_fields.py
python scripts/test_contract_roundtrip.py
python scripts/graph_audit.py
```

## Final Principle

Do not turn Mnemosyne into a dashboard-first project. The right order is:

```text
behavior contract -> reviewable learning output -> observability -> architecture docs -> demo
```

That sequence keeps the system honest: first make behavior safe, then make learning visible, then make operations observable, then make the project understandable and demonstrable.

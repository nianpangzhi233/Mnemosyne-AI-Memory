# Mnemosyne V8 MVP Plan

Status: implemented MVP baseline.

This plan converts `DESIGN_BRIEF_DRAFT.md` into a small build target. The goal is to prove the V8 memory kernel loop without recreating V7's graph pipeline.

## Implementation Status

Implemented in this MVP baseline:

- SQLite store and schema bootstrap.
- RawEvent, Candidate, Evidence, Memory, and ContextPack run tables.
- EventWriter, CandidateWriter, EvidenceRecorder, LifecycleManager, WriteGate, ReadGate, and ContextPackBuilder.
- CLI commands for add/promote/demote/stale/deprecate/build/list/get.
- ContextPack evidence snippets.
- PowerShell-friendly `--scope-item key=value` scope input.
- Real-scenario functional smoke script.
- Tests covering promotion gates, read gates, lifecycle blocking, CLI smoke, inspection, and functional smoke.

Still intentionally not implemented:

- LLM-powered Candidate extraction.
- REST or MCP integration.
- Dashboard.
- Graph ontology.
- Background autonomous mutation.
- Parametric consolidation.

## MVP Goal

Build the smallest useful V8 memory kernel:

```text
RawEvent -> Candidate -> Evidence -> ValidatedMemory -> ContextPack -> Outcome Evidence
```

Acceptance sentence:

V8 MVP can record raw events, propose candidate memories, require evidence before promotion, and build scoped ContextPacks that refuse unsupported, stale, or out-of-scope memory.

## Non-Goals

Do not build these in MVP:

- Graph ontology.
- Dream pipeline.
- Skill auto-approval.
- Multi-agent runtime.
- Web dashboard.
- Parametric model editing.
- RL router.
- Always-visible memory blocks by default.
- Background autonomous mutation.

## Storage Decision

Use SQLite for MVP state and plain files only for large raw payloads if needed.

Reasons:

- SQLite is easy to inspect.
- It supports transactional lifecycle updates.
- It avoids V7's graph database shape while preserving queryability.
- File-backed raw payloads can be added later without changing the lifecycle model.

MVP database path:

```text
v8/data/v8.db
```

This database is runtime state and should not be committed.

## Minimal Schema

### raw_events

Immutable source records.

Fields:

- `id` text primary key.
- `created_at` text ISO timestamp.
- `actor` text.
- `event_type` text.
- `trust` text.
- `scope_json` text.
- `content` text.
- `content_ref` text nullable.
- `metadata_json` text.

Rules:

- Raw events are append-only.
- Edits create a new event.
- Deletes are not part of MVP except full test database reset.

### candidates

Untrusted proposed memory.

Fields:

- `id` text primary key.
- `created_at` text ISO timestamp.
- `candidate_type` text.
- `content` text.
- `source_event_ids_json` text.
- `scope_json` text.
- `trigger` text.
- `preconditions_json` text.
- `risk` text.
- `status` text.
- `metadata_json` text.

Allowed `status` values:

- `candidate`.
- `rejected`.
- `promoted`.

Rules:

- Candidate must cite at least one RawEvent.
- Candidate cannot be injected directly.
- LLM extraction, if added later, writes here only.

### evidence

Records that support or weaken a candidate/memory.

Fields:

- `id` text primary key.
- `created_at` text ISO timestamp.
- `target_type` text.
- `target_id` text.
- `evidence_type` text.
- `polarity` text.
- `content` text.
- `source_event_ids_json` text.
- `metadata_json` text.

Allowed `polarity` values:

- `supports`.
- `weakens`.
- `contradicts`.
- `neutral`.

MVP evidence types:

- `user_confirmation`.
- `user_correction`.
- `task_success`.
- `task_failure`.
- `test_result`.
- `control_flow_trace`.

### memories

Validated memory eligible for read-time use.

Fields:

- `id` text primary key.
- `created_at` text ISO timestamp.
- `updated_at` text ISO timestamp.
- `candidate_id` text.
- `memory_type` text.
- `content` text.
- `scope_json` text.
- `trigger` text.
- `risk` text.
- `confidence` real.
- `status` text.
- `freshness` real.
- `read_policy_json` text.
- `revision` integer.
- `metadata_json` text.

Allowed `status` values:

- `validated`.
- `promoted`.
- `stale`.
- `demoted`.
- `locked`.
- `deprecated`.

Rules:

- A memory must come from a Candidate.
- A memory must have supporting Evidence.
- Unsupported candidates cannot become memories.
- `demoted`, `deprecated`, and `stale` are not injected by default.

### context_pack_runs

Audit log for read-time decisions.

Fields:

- `id` text primary key.
- `created_at` text ISO timestamp.
- `task` text.
- `scope_json` text.
- `selected_json` text.
- `rejected_json` text.
- `warnings_json` text.
- `budget_json` text.

Rules:

- Every ContextPack build creates a run record.
- Rejected memories should include reason codes.

## Scope Model

Every object that can be retrieved must support these optional scope keys:

- `user_id`.
- `project_id`.
- `agent_id`.
- `session_id`.
- `task_id`.
- `source_id`.

MVP matching rule:

- A requested scope key must match the memory scope if the memory has that key.
- Missing memory scope means broader scope, but high-risk memory must not be broad by default.
- `project_id` mismatch rejects the memory.
- `user_id` mismatch rejects the memory.

## Core Services

### EventWriter

Responsibilities:

- Append RawEvent.
- Validate required fields.
- Normalize scope JSON.

### CandidateWriter

Responsibilities:

- Create Candidate from RawEvent IDs.
- Reject candidate without sources.
- Keep status at `candidate`.

### EvidenceRecorder

Responsibilities:

- Attach Evidence to Candidate or Memory.
- Validate target exists.
- Preserve source_event links.

### LifecycleManager

Responsibilities:

- Promote Candidate to Memory only when WriteGate passes.
- Demote/stale/deprecate Memory.
- Record revision increments.

### WriteGate

MVP promotion checks:

- Candidate exists.
- Candidate has at least one source RawEvent.
- Candidate has at least one supporting Evidence.
- Candidate has no contradicting Evidence.
- Candidate has explicit scope.
- Procedure/workflow/skill candidates require at least one `task_success`, `test_result`, or `control_flow_trace` support.

### ReadGate

MVP read checks:

- Memory status is `validated` or `promoted`.
- Scope matches request.
- Freshness is above threshold.
- Risk is allowed by request policy.
- Trigger/content roughly matches task by keyword search in MVP.

Rejection reason codes:

- `status_blocked`.
- `scope_mismatch`.
- `stale`.
- `risk_blocked`.
- `no_task_match`.
- `unsupported`.

### ContextPackBuilder

Responsibilities:

- Query candidate memories.
- Run ReadGate.
- Return selected items, rejected items, warnings.
- Write context_pack_runs audit row.

## MVP Interface

Use a Python CLI first. REST/MCP can come after the kernel is proven.

Command shape:

```text
python -m v8.memory event add --type user_message --actor user --content "..." --scope '{...}'
python -m v8.memory candidate add --type claim --content "..." --sources event_id --scope '{...}' --trigger "..."
python -m v8.memory evidence add --target candidate_id --type user_confirmation --polarity supports --content "..."
python -m v8.memory lifecycle promote --candidate candidate_id
python -m v8.memory context build --task "..." --scope '{...}'
```

JSON output only. No rich TUI in MVP.

## Test Plan

### Unit Tests

Required tests:

- RawEvent append creates immutable event.
- Candidate without source RawEvent is rejected.
- Candidate cannot appear in ContextPack before promotion.
- Candidate without supporting Evidence cannot be promoted.
- Candidate with contradicting Evidence cannot be promoted.
- Out-of-scope Memory is rejected by ReadGate.
- `stale`, `demoted`, and `deprecated` memories are not injected by default.
- High-risk procedure cannot promote without task/control-flow evidence.
- ContextPack records selected and rejected items with reason codes.

### Golden Scenario

Scenario: PowerShell heredoc failure.

Steps:

- Record RawEvent: failed command using Bash heredoc in PowerShell.
- Create Candidate: PowerShell does not support Bash heredoc.
- Add Evidence: task success after switching to compatible command form.
- Promote Candidate.
- Build ContextPack for a future PowerShell inline Python task.
- Assert memory is selected.
- Build ContextPack for unrelated project scope.
- Assert memory is rejected by scope.

### Procedural Safety Scenario

Scenario: procedure tries to skip validation.

Steps:

- Record RawEvent containing a proposed shortcut.
- Create procedure Candidate.
- Add weak support only.
- Attempt promote.
- Assert promotion fails because no task/control-flow evidence exists.

## File Layout

Target MVP layout:

```text
v8/
  README.md
  DESIGN_BRIEF_DRAFT.md
  MVP_PLAN.md
  src/
    v8_memory/
      __init__.py
      cli.py
      models.py
      store.py
      gates.py
      context.py
      lifecycle.py
  tests/
    test_event_writer.py
    test_candidate_evidence.py
    test_lifecycle.py
    test_context_pack.py
    test_golden_powershell.py
  data/
    .gitkeep
```

## Git Hygiene

Do not commit runtime database files:

- `v8/data/*.db`
- `v8/data/*.db-*`

Do commit:

- schema code.
- tests.
- docs.
- `.gitkeep` if the data directory is needed.

## Build Order

1. Add package skeleton and `.gitignore` rules for V8 runtime DB.
2. Implement SQLite store and schema migration bootstrap.
3. Implement EventWriter and tests.
4. Implement CandidateWriter and EvidenceRecorder with tests.
5. Implement WriteGate and LifecycleManager with tests.
6. Implement ReadGate and ContextPackBuilder with tests.
7. Add CLI wrappers with JSON output.
8. Add golden PowerShell scenario.
9. Review MVP against `DESIGN_BRIEF_DRAFT.md` and cut anything nonessential.

## Acceptance Criteria

MVP is done when:

- All required tests pass.
- A candidate cannot become memory without evidence.
- A candidate cannot be injected directly.
- Scope mismatch blocks retrieval.
- Stale/demoted/deprecated memories are blocked by default.
- High-risk procedure requires task/control-flow evidence.
- ContextPack build logs selected and rejected items.
- The golden scenario works end to end through CLI or direct service calls.

## First Implementation Cut

Start with direct Python service calls and tests before polishing the CLI.

Reason:

- It proves the kernel semantics first.
- CLI argument parsing is secondary.
- REST/MCP integration should not exist until lifecycle rules are correct.

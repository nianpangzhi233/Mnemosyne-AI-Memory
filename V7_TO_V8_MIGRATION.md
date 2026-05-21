# V7 To V8 Migration Plan

Status: executable migration plan.

## Goal

Move Mnemosyne from the V7 graph/dream runtime to the V8 evidence-governed memory kernel without importing V7 runtime databases into V8.

## Migration Principle

V8 does not inherit V7's `nodes` / `edges` graph shape. V8 rebuilds memory from governed source material:

```text
RawEvent -> Candidate -> Evidence -> ValidatedMemory -> ContextPack
```

## Phase 1: V8 Kernel Completion

Done:

- SQLite V8 store.
- RawEvent / Candidate / Evidence / Memory / ContextPack tables.
- WriteGate and ReadGate.
- Lifecycle operations.
- CLI flow.
- MCP flow.
- Source-grounded ContextPack output.
- Gate reason-code tests.

Remaining:

- REST flow.
- Default entrypoint migration.
- Optional dashboard view after the API contract is stable.

## Phase 2: V8 External Interfaces

Required default interfaces:

- CLI: `python -m v8_memory.cli ...`
- MCP: `v8_*` tools.
- REST: `/api/v8/*` endpoints.

Interface acceptance:

- All interfaces must expose source grounding.
- All interfaces must expose evidence grounding.
- Gate failures must preserve reason codes.
- No interface may turn a Candidate into trusted memory without Evidence.

## Phase 3: V7 Freeze

Actions:

- Disable V7 background automation.
- Label V7 entrypoints as legacy.
- Stop adding V7 features.
- Keep V7 manual inspection available.

Already completed:

- Windows scheduled automatic dream tasks are disabled.

## Phase 4: Default Entrypoint Switch

Switch these defaults to V8:

- README examples.
- MCP usage notes.
- REST usage notes.
- New development docs.
- Future demos.

Keep these as legacy references:

- V7 graph write/search/inject examples.
- V7 dream docs.
- V7 skill-evolution docs.

## Phase 5: Final Archive

Completion checklist:

- `V7_ARCHIVE_POLICY.md` exists and is linked from current docs.
- `V7_TO_V8_MIGRATION.md` exists and describes the transition.
- V8 REST/MCP/CLI tests pass.
- V7 tests still pass where retained.
- Worktree is clean.

## Explicit Non-Migration

Do not migrate these into V8 by default:

- `graph.db`.
- `dream_log.db`.
- V7 `nodes` and `edges`.
- `hot/` generated memory mirrors.
- `skills/*` generated mirrors.

If old V7 material is useful, re-ingest it as V8 RawEvents and promote only through Candidate + Evidence gates.

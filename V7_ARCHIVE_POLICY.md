# V7 Archive Policy

Status: active policy for V8 migration.

## Purpose

V7 is being preserved as a legacy archive. It remains available for historical inspection and reference, but it is no longer the primary runtime or the default place for new work.

## What Is Frozen

- Core V7 graph semantics and schema.
- `graph.db` as the legacy graph runtime database.
- `dream_log.db` as the legacy dream history database.
- `hot/` generated memory mirrors.
- Generated skill mirrors under `skills/*/`.
- Background dream scheduling and automatic mutation paths.

## What Remains Readable

- Existing V7 CLI and API code for historical reference.
- Legacy reports, logs, and generated artifacts.
- Manual inspection of old data.

## What Must Not Happen

- No new V7 features.
- No new V7 storage migration.
- No V7 default-entrypoint changes in new docs.
- No background automatic dream runs.
- No writing new operational state into V7 as the primary path.

## V8 Ownership Boundary

All new memory-kernel work moves to V8:

- RawEvent / Candidate / Evidence / ValidatedMemory / ContextPack.
- V8 MCP tools.
- V8 REST API.
- V8 CLI contract.
- V8 source grounding and gate reason codes.

## Operational Rules

- Keep V7 code available for lookup, but mark it legacy.
- New documentation should point to V8 unless explicitly discussing legacy behavior.
- If a change is needed for both systems, implement it in V8 first and keep V7 unchanged unless the change is strictly archival.

## Archive Completion Criteria

- V8 is the default runtime for new work.
- V7 is clearly labeled legacy in docs and entrypoints.
- Background V7 automation is disabled.
- V7 data remains intact and readable.

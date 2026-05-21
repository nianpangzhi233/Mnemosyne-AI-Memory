# Mnemosyne V8

This is the clean project space for Mnemosyne V8.

Current status: MVP memory kernel implemented and tested.

Rules:

- Do not import V7 graph databases.
- Do not reuse V7 node/edge schema as the V8 core model.
- Do not add architecture decisions here until the V8 design discussion is settled.
- Raw diaries and logs may later be used as source material for rebuilding V8 cognition from scratch.

## MVP Shape

V8 MVP proves this loop:

```text
RawEvent -> Candidate -> Evidence -> ValidatedMemory -> ContextPack
```

The point is not to store more text. The point is to prevent unsupported summaries from becoming trusted memory.

## Current MVP Capabilities

- SQLite-backed RawEvent, Candidate, Evidence, Memory, and ContextPack run storage.
- Evidence-required promotion from Candidate to ValidatedMemory.
- ReadGate filtering by scope, freshness, status, risk, and task match.
- Lifecycle commands for promote, demote, stale, and deprecate.
- ContextPack output with original source event snippets and supporting evidence snippets.
- Inspection commands for events, candidates, evidence, memories, and context runs.
- PowerShell-friendly `--scope-item key=value` flags.
- Real-scenario functional smoke using the PowerShell wildcard compile issue.

Validated by:

- `python -m unittest tests.test_v8_mvp`
- `python -m unittest discover tests`
- `python "v8/scripts/functional_smoke.py" --db <temp-db>`

## CLI Demo

Run commands from the repository root.

```powershell
$env:PYTHONPATH = "v8/src"
python -m v8_memory.cli --db "v8/data/v8.db" event add --type tool_error --actor agent --content "PowerShell rejected Bash heredoc syntax." --scope-item project_id=memory-evolution --scope-item session_id=demo
```

Use the returned event ID as the source for a candidate:

```powershell
python -m v8_memory.cli --db "v8/data/v8.db" candidate add --type claim --content "PowerShell does not support Bash heredoc." --sources <event_id> --scope-item project_id=memory-evolution --scope-item session_id=demo --trigger "debug PowerShell inline command"
```

Attach evidence before promotion:

```powershell
python -m v8_memory.cli --db "v8/data/v8.db" evidence add --target <candidate_id> --type task_success --polarity supports --content "Using a PowerShell-compatible command fixed the issue." --sources <event_id>
```

`--sources` on evidence is optional, but use it when the evidence came from a RawEvent. This keeps both the candidate and the supporting evidence grounded in inspectable source material.

Promote only after evidence exists:

```powershell
python -m v8_memory.cli --db "v8/data/v8.db" lifecycle promote --candidate <candidate_id>
```

Build a scoped ContextPack:

```powershell
python -m v8_memory.cli --db "v8/data/v8.db" context build --task "debug PowerShell inline command" --scope-item project_id=memory-evolution --pretty
```

ContextPack items include the selected memory, original source events, and supporting evidence snippets, so callers can see what is trusted and why it is trusted:

```json
{
  "items": [
    {
      "id": "mem_...",
      "type": "claim",
      "content": "PowerShell does not support Bash heredoc.",
      "status": "validated",
      "scope": {"project_id": "memory-evolution", "session_id": "demo"},
      "source_events": [
        {
          "id": "evt_...",
          "event_type": "tool_error",
          "actor": "agent",
          "trust": "local",
          "content": "PowerShell rejected Bash heredoc syntax.",
          "scope": {"project_id": "memory-evolution", "session_id": "demo"}
        }
      ],
      "evidence": [
        {
          "id": "ev_...",
          "type": "task_success",
          "polarity": "supports",
          "content": "Using a PowerShell-compatible command fixed the issue.",
          "source_event_ids": ["evt_..."]
        }
      ]
    }
  ],
  "rejected": [],
  "warnings": []
}
```

`--scope` still accepts JSON, but `--scope-item key=value` is safer in PowerShell and can be repeated.

Lifecycle commands can also remove a memory from default injection:

```powershell
python -m v8_memory.cli --db "v8/data/v8.db" lifecycle demote --memory <memory_id>
python -m v8_memory.cli --db "v8/data/v8.db" lifecycle stale --memory <memory_id>
python -m v8_memory.cli --db "v8/data/v8.db" lifecycle deprecate --memory <memory_id>
```

`demote` and `deprecate` block injection by status. `stale` also sets freshness to zero and is reported as a freshness rejection.

## Gate Reason Codes

WriteGate checks whether a Candidate may become ValidatedMemory:

| Reason | Meaning |
| --- | --- |
| `missing_source` | Candidate has no RawEvent source IDs. |
| `missing_scope` | Candidate has no normalized scope. |
| `missing_supporting_evidence` | Candidate has no supporting Evidence. |
| `contradicting_evidence` | Candidate has at least one contradicting Evidence row. |
| `missing_procedural_evidence` | Procedure/workflow/skill candidate lacks `test_result` or `control_flow_trace` support. |

ReadGate checks whether a Memory may enter the current ContextPack:

| Reason | Meaning |
| --- | --- |
| `stale` | Memory freshness is below the policy threshold. |
| `status_blocked` | Memory status is not `validated` or `promoted`. |
| `risk_blocked` | Memory risk is outside the policy's allowed risk set. |
| `scope_mismatch` | Memory scope conflicts with the requested scope. |
| `no_task_match` | MVP keyword match found no overlap between task and memory trigger/content. |

The current MVP reports only the first ReadGate rejection reason, while WriteGate returns all promotion blockers found for a Candidate.

Inspect stored records with list/get commands:

```powershell
python -m v8_memory.cli --db "v8/data/v8.db" event list --pretty
python -m v8_memory.cli --db "v8/data/v8.db" candidate get --id <candidate_id> --pretty
python -m v8_memory.cli --db "v8/data/v8.db" evidence list --target-type candidate --target <candidate_id> --pretty
python -m v8_memory.cli --db "v8/data/v8.db" memory get --id <memory_id> --pretty
python -m v8_memory.cli --db "v8/data/v8.db" context list --pretty
```

## MCP Tools

The existing Mnemosyne MCP server also exposes the V8 kernel. The V8 tools are prefixed with `v8_` so they do not conflict with the V7 graph-memory tools.

Stable V8 MCP tools:

| Tool | Purpose |
| --- | --- |
| `v8_event_add` | Append a RawEvent. |
| `v8_candidate_add` | Create a Candidate from RawEvent source IDs. |
| `v8_evidence_add` | Attach Evidence to a Candidate or Memory. |
| `v8_lifecycle_promote` | Promote a Candidate if WriteGate passes. |
| `v8_lifecycle_demote` | Demote a Memory so ReadGate blocks it. |
| `v8_lifecycle_stale` | Mark a Memory stale and set freshness to zero. |
| `v8_lifecycle_deprecate` | Deprecate a Memory. |
| `v8_context_build` | Build a governed ContextPack. |
| `v8_memory_get` / `v8_memory_list` | Inspect Memories. |
| `v8_record_get` / `v8_record_list` | Inspect raw V8 tables. |

Minimal MCP flow:

```text
v8_event_add -> v8_candidate_add -> v8_evidence_add -> v8_lifecycle_promote -> v8_context_build
```

`v8_context_build` returns the same auditable shape as the CLI: selected memories include `source_events`, supporting `evidence`, and `evidence.source_event_ids`; rejected memories include reason codes.

By default the MCP server writes V8 state to `v8/data/v8.db`. Tests and local experiments can override this with `MCP_V8_DB=<path>`.

## REST API

The V8 REST surface is mounted on the existing FastAPI app under `/api/v8`. It is a thin wrapper over the same V8 services used by CLI and MCP.

Stable V8 REST endpoints:

| Endpoint | Purpose |
| --- | --- |
| `GET /api/v8/health` | Check V8 store health. |
| `POST /api/v8/events` | Append a RawEvent. |
| `POST /api/v8/candidates` | Create a Candidate from RawEvent source IDs. |
| `POST /api/v8/evidence` | Attach Evidence to a Candidate or Memory. |
| `POST /api/v8/lifecycle/promote` | Promote a Candidate if WriteGate passes. |
| `POST /api/v8/lifecycle/demote` | Demote a Memory. |
| `POST /api/v8/lifecycle/stale` | Mark a Memory stale. |
| `POST /api/v8/lifecycle/deprecate` | Deprecate a Memory. |
| `POST /api/v8/context-packs` | Build a governed ContextPack. |
| `GET /api/v8/memories` | List Memories. |
| `GET /api/v8/memories/{id}` | Inspect one Memory. |
| `GET /api/v8/records/{table}` | List raw V8 table records. |
| `GET /api/v8/records/{table}/{id}` | Inspect one raw V8 table record. |

Minimal REST flow:

```powershell
start-v8-api.cmd

curl -X POST http://127.0.0.1:8979/api/v8/events `
  -H "Content-Type: application/json" `
  -d '{"event_type":"tool_error","actor":"agent","content":"PowerShell rejected Bash heredoc syntax.","scope":{"project_id":"memory-evolution","session_id":"demo"}}'
```

Then call `candidates`, `evidence`, `lifecycle/promote`, and `context-packs` with the returned IDs. REST returns the same auditable fields as CLI and MCP: `source_events`, `evidence`, `evidence.source_event_ids`, and `rejected.reason`.

By default REST writes V8 state to `v8/data/v8.db`. Tests and local experiments can override this with `MNEMOSYNE_V8_DB=<path>` or `V8_DB=<path>`.

## Functional Smoke

Run the real-scenario smoke test with a temporary or explicit database:

```powershell
$env:PYTHONPATH = "v8/src"
python "v8/scripts/functional_smoke.py" --db "v8/data/functional-smoke.db"
```

The smoke uses a real issue from V8 implementation: PowerShell did not expand `*.py` for `python -m py_compile`, while a Python `pathlib.glob('*.py')` compile command worked. It records that as RawEvent, Candidate, Evidence, ValidatedMemory, and then builds a ContextPack.

For a user-facing V8-only demo, run `python demo/run_v8_demo.py` from the repository root.

For the current handover status and next-step notes, see `../V8_HANDOVER.md`.

## Runtime Files

Runtime databases live under `v8/data/` and are ignored by git.

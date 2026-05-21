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

Inspect stored records with list/get commands:

```powershell
python -m v8_memory.cli --db "v8/data/v8.db" event list --pretty
python -m v8_memory.cli --db "v8/data/v8.db" candidate get --id <candidate_id> --pretty
python -m v8_memory.cli --db "v8/data/v8.db" evidence list --target-type candidate --target <candidate_id> --pretty
python -m v8_memory.cli --db "v8/data/v8.db" memory get --id <memory_id> --pretty
python -m v8_memory.cli --db "v8/data/v8.db" context list --pretty
```

## Functional Smoke

Run the real-scenario smoke test with a temporary or explicit database:

```powershell
$env:PYTHONPATH = "v8/src"
python "v8/scripts/functional_smoke.py" --db "v8/data/functional-smoke.db"
```

The smoke uses a real issue from V8 implementation: PowerShell did not expand `*.py` for `python -m py_compile`, while a Python `pathlib.glob('*.py')` compile command worked. It records that as RawEvent, Candidate, Evidence, ValidatedMemory, and then builds a ContextPack.

## Runtime Files

Runtime databases live under `v8/data/` and are ignored by git.

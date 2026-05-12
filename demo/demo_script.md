# Demo Script

This demo shows Mnemosyne as a governed memory system, not a chat-log viewer. It runs on temporary SQLite files and does not touch the real `graph.db` or `dream_log.db`.

## Run

```powershell
python demo\run_demo.py
```

Keep the generated demo databases for inspection:

```powershell
python demo\run_demo.py --keep --out C:\Users\年\AppData\Local\Temp\mnemosyne-demo-kept
```

The kept directory contains:

- `demo_graph.db`: temporary graph state with seed memories, typed edges, and a trial skill candidate.
- `demo_dream_log.db`: temporary dream history with `evolution_reports`, `telemetry_events`, and `telemetry_runs`.

These files are demo output. Do not commit them.

## Story

- Import three days of safe seed conversations from `demo/seed_conversations/`.
- Run deterministic dream phases over the imported memories.
- Create typed graph evidence: `solves`, `is_a`, and `transfers_to` edges.
- Write a reviewable `EvolutionReport` with evidence IDs and review counts.
- Create a low-risk skill candidate from source memories.
- Demonstrate `memory_skill_inject`-style trial injection against a matching task.
- Record a `demo_cold_start` telemetry run so the background work is observable.

## Expected Checks

The command prints JSON with `status: PASS` and these checks:

- `seed_memories_imported`
- `solves_edge_created`
- `concept_created`
- `transfers_created`
- `report_created`
- `report_has_evidence`
- `skill_candidate_created`
- `injection_demo`
- `telemetry_run_created`

The expected shape is documented in `demo/expected/dream-report.json`.

Treat these checks as functional acceptance criteria. If one turns false, the demo is not complete even if the script exits or prints phases.

## Inspecting The Output

Use `--keep` when you want to inspect evidence after the command exits. The JSON output gives the exact `demo_db` and `dream_log_db` paths.

Useful things to inspect:

- `evolution_reports.report`: reviewable summary with sections, evidence IDs, and review counts.
- `telemetry_runs`: the `demo_cold_start` run with status, duration, summary, and errors.
- `edges`: `solves`, `is_a`, `transfers_to`, and `crystallized_from` evidence.
- `skill_artifacts`: the low-risk `evolved` trial skill candidate.

The demo uses safe public examples only: gzip request parsing, field contracts, and Windows/SQLite encoding checks. It does not require API keys or a paid LLM.

## Talking Points

- Mnemosyne stores structured fields, typed edges, reviewable reports, governed skills, and telemetry runs.
- A useful demo must prove user-visible value: memory becomes evidence, evidence becomes a report, a report leads to reviewable action.
- Reports and telemetry keep learning explainable instead of mystical.

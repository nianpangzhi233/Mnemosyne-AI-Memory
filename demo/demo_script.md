# Demo Script

This demo shows Mnemosyne turning structured memories into graph edges and a reviewable dream report without touching the real `graph.db`.

## Run

```powershell
python demo\run_demo.py
```

## What It Demonstrates

- A failed gzip parsing memory and a successful fix become a `solves` edge.
- Three cross-task contract memories become a concept node through `ConceptPhase`.
- Concept membership produces `transfers_to` edges.
- The dream run writes EvolutionReport and telemetry rows to a temporary `dream_log.db`.
- The whole demo uses a temporary directory and deletes it when finished.

## Expected Output

The command prints JSON with:

- `status: PASS`
- `nodes` greater than the seed count because a concept node is created
- `edges` greater than zero
- phase results for `SnapshotPhase`, `CausalPhase`, `ConceptPhase`, `TransfersPhase`, and `AuditPhase`

## Talking Points

- Mnemosyne is not a plain vector database. It stores structured fields, typed edges, and reviewable reports.
- The dream pipeline is deterministic enough to test with contract scenarios.
- Reports and telemetry make background learning observable instead of mystical.

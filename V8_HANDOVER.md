# V8 Handover

Status: current working handover.

## Where We Are

V8 is now the default runtime line.

Completed core surfaces:

- V8 memory kernel with SQLite store.
- WriteGate and ReadGate.
- CLI surface.
- MCP surface with `v8_` tools.
- REST surface under `/api/v8`.
- Source-grounded ContextPack output.
- Gate reason codes.
- V8-only demo path.
- V7 archive policy and archive index.

## Default Entry Points

- `start-v8-api.cmd` - V8 REST launcher.
- `demo/run_v8_demo.py` - V8-only demo.
- `v8/README.md` - primary V8 contract.
- `README.md` - main entrypoint now points to V8 first.

## Legacy Entry Points

- `start-api.cmd` - legacy combined REST launcher.
- `dream.cmd` - legacy dream flow.
- `skill-daemon.cmd` - legacy background skill daemon.
- `demo/run_demo.py` - legacy V7-heavy story demo.

## Stable V8 Contract

### Memory Flow

```text
RawEvent -> Candidate -> Evidence -> ValidatedMemory -> ContextPack
```

### Required Fields

- `source_events`
- `evidence`
- `evidence.source_event_ids`
- `rejected.reason`

### Gate Reasons

WriteGate:

- `missing_source`
- `missing_scope`
- `missing_supporting_evidence`
- `contradicting_evidence`
- `missing_procedural_evidence`

ReadGate:

- `stale`
- `status_blocked`
- `risk_blocked`
- `scope_mismatch`
- `no_task_match`

## What Is Archived

V7 is preserved as a legacy archive only.

Archive documents:

- `V7_ARCHIVE_POLICY.md`
- `V7_TO_V8_MIGRATION.md`
- `V7_ARCHIVE_INDEX.md`

Archive data that stays out of V8 source-of-truth:

- `graph.db`
- `dream_log.db`
- `hot/`
- generated skill mirrors

## Verification Commands

Run these after touching V8 surfaces:

```bash
python -m unittest tests.test_v8_rest_api tests.test_mcp_v8_surface tests.test_v8_mvp tests.test_v8_demo
python -m unittest discover tests
python demo/run_v8_demo.py
```

## Next Work

If we continue V8 work, the next likely targets are:

- dashboard V8 views.
- policy tuning for ContextPack selection.
- optional V8 bulk import tools.
- explicit V7 read-only archive entrypoints if needed.

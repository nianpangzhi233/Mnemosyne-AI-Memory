#!/usr/bin/env python3
"""Small local telemetry store for dream/daemon observability."""

import json
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_DREAM_LOG_DB = PROJECT_ROOT / "dream_log.db"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_dumps(value: Any) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False, default=str)


def _json_loads(value: Any, default: Any):
    if value in (None, ""):
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default


def init_telemetry(db_path: Optional[Path] = None) -> None:
    target = Path(db_path) if db_path else DEFAULT_DREAM_LOG_DB
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target))
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS telemetry_runs (
                id TEXT PRIMARY KEY,
                run_type TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                status TEXT,
                duration_ms REAL,
                summary TEXT,
                errors TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_telemetry_runs_started_at ON telemetry_runs(started_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_telemetry_runs_type ON telemetry_runs(run_type)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_telemetry_runs_status ON telemetry_runs(status)")
        conn.commit()
    finally:
        conn.close()


def start_run(run_type: str, db_path: Optional[Path] = None, summary: Optional[Dict[str, Any]] = None) -> str:
    init_telemetry(db_path)
    run_id = str(uuid.uuid4())
    started = _now_iso()
    payload = dict(summary or {})
    payload["started_perf"] = time.perf_counter()
    conn = sqlite3.connect(str(Path(db_path) if db_path else DEFAULT_DREAM_LOG_DB))
    try:
        conn.execute(
            "INSERT INTO telemetry_runs(id, run_type, started_at, status, summary, errors) VALUES (?,?,?,?,?,?)",
            (run_id, run_type, started, "RUNNING", _json_dumps(payload), "[]"),
        )
        conn.commit()
    finally:
        conn.close()
    return run_id


def finish_run(run_id: str, status: str, db_path: Optional[Path] = None,
               summary: Optional[Dict[str, Any]] = None,
               errors: Optional[List[Any]] = None) -> Dict[str, Any]:
    init_telemetry(db_path)
    target = Path(db_path) if db_path else DEFAULT_DREAM_LOG_DB
    finished = _now_iso()
    conn = sqlite3.connect(str(target))
    try:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM telemetry_runs WHERE id=?", (run_id,)).fetchone()
        if not row:
            raise ValueError(f"telemetry run not found: {run_id}")
        old_summary = _json_loads(row["summary"], {})
        started_perf = old_summary.pop("started_perf", None)
        duration_ms = None
        if started_perf is not None:
            try:
                duration_ms = (time.perf_counter() - float(started_perf)) * 1000
            except (TypeError, ValueError):
                duration_ms = None
        merged_summary = old_summary
        merged_summary.update(summary or {})
        conn.execute(
            "UPDATE telemetry_runs SET finished_at=?, status=?, duration_ms=?, summary=?, errors=? WHERE id=?",
            (finished, status, round(duration_ms, 2) if duration_ms is not None else None,
             _json_dumps(merged_summary), _json_dumps(errors or []), run_id),
        )
        conn.commit()
        return get_run(run_id, db_path=target) or {}
    finally:
        conn.close()


def fail_run(run_id: str, exc: Exception, db_path: Optional[Path] = None,
             summary: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return finish_run(
        run_id,
        "FAIL",
        db_path=db_path,
        summary=summary,
        errors=[{"type": exc.__class__.__name__, "message": str(exc)}],
    )


def get_run(run_id: str, db_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    init_telemetry(db_path)
    conn = sqlite3.connect(str(Path(db_path) if db_path else DEFAULT_DREAM_LOG_DB))
    try:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM telemetry_runs WHERE id=?", (run_id,)).fetchone()
        if not row:
            return None
        return _decode_row(dict(row))
    finally:
        conn.close()


def list_runs(limit: int = 20, run_type: Optional[str] = None,
              db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    init_telemetry(db_path)
    conn = sqlite3.connect(str(Path(db_path) if db_path else DEFAULT_DREAM_LOG_DB))
    try:
        conn.row_factory = sqlite3.Row
        params = []
        sql = "SELECT * FROM telemetry_runs"
        if run_type:
            sql += " WHERE run_type=?"
            params.append(run_type)
        sql += " ORDER BY started_at DESC LIMIT ?"
        params.append(limit)
        return [_decode_row(dict(row)) for row in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def summary(db_path: Optional[Path] = None) -> Dict[str, Any]:
    init_telemetry(db_path)
    conn = sqlite3.connect(str(Path(db_path) if db_path else DEFAULT_DREAM_LOG_DB))
    try:
        conn.row_factory = sqlite3.Row
        latest = conn.execute("SELECT * FROM telemetry_runs ORDER BY started_at DESC LIMIT 1").fetchone()
        latest_failed = conn.execute("SELECT * FROM telemetry_runs WHERE status='FAIL' ORDER BY started_at DESC LIMIT 1").fetchone()
        by_type = [dict(row) for row in conn.execute(
            "SELECT run_type, status, COUNT(*) AS count, AVG(duration_ms) AS avg_duration_ms "
            "FROM telemetry_runs GROUP BY run_type, status ORDER BY run_type, status"
        ).fetchall()]
        return {
            "latest_run": _decode_row(dict(latest)) if latest else None,
            "latest_failed_run": _decode_row(dict(latest_failed)) if latest_failed else None,
            "by_type": by_type,
        }
    finally:
        conn.close()


def _decode_row(row: Dict[str, Any]) -> Dict[str, Any]:
    row["summary"] = _json_loads(row.get("summary"), {})
    row["errors"] = _json_loads(row.get("errors"), [])
    return row

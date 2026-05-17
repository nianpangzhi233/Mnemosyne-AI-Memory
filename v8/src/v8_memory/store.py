from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Iterable

from .models import dumps, loads, row_to_dict


SCHEMA = """
CREATE TABLE IF NOT EXISTS raw_events (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    actor TEXT NOT NULL,
    event_type TEXT NOT NULL,
    trust TEXT NOT NULL,
    scope_json TEXT NOT NULL,
    content TEXT NOT NULL,
    content_ref TEXT,
    metadata_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS candidates (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    candidate_type TEXT NOT NULL,
    content TEXT NOT NULL,
    source_event_ids_json TEXT NOT NULL,
    scope_json TEXT NOT NULL,
    trigger TEXT NOT NULL,
    preconditions_json TEXT NOT NULL,
    risk TEXT NOT NULL,
    status TEXT NOT NULL,
    metadata_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evidence (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    evidence_type TEXT NOT NULL,
    polarity TEXT NOT NULL,
    content TEXT NOT NULL,
    source_event_ids_json TEXT NOT NULL,
    metadata_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    candidate_id TEXT NOT NULL,
    memory_type TEXT NOT NULL,
    content TEXT NOT NULL,
    scope_json TEXT NOT NULL,
    trigger TEXT NOT NULL,
    risk TEXT NOT NULL,
    confidence REAL NOT NULL,
    status TEXT NOT NULL,
    freshness REAL NOT NULL,
    read_policy_json TEXT NOT NULL,
    revision INTEGER NOT NULL,
    metadata_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS context_pack_runs (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    task TEXT NOT NULL,
    scope_json TEXT NOT NULL,
    selected_json TEXT NOT NULL,
    rejected_json TEXT NOT NULL,
    warnings_json TEXT NOT NULL,
    budget_json TEXT NOT NULL
);
"""


class SQLiteV8Store:
    TABLES = {"raw_events", "candidates", "evidence", "memories", "context_pack_runs"}

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_schema()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def init_schema(self) -> None:
        conn = self.connect()
        try:
            conn.executescript(SCHEMA)
        finally:
            conn.close()

    def insert(self, table: str, row: dict[str, Any]) -> str:
        keys = list(row.keys())
        placeholders = ", ".join("?" for _ in keys)
        columns = ", ".join(keys)
        values = [row[key] for key in keys]
        conn = self.connect()
        try:
            conn.execute(f"INSERT INTO {table} ({columns}) VALUES ({placeholders})", values)
            conn.commit()
        finally:
            conn.close()
        return str(row["id"])

    def update(self, table: str, item_id: str, fields: dict[str, Any]) -> None:
        if not fields:
            return
        assignments = ", ".join(f"{key}=?" for key in fields)
        values = list(fields.values()) + [item_id]
        conn = self.connect()
        try:
            conn.execute(f"UPDATE {table} SET {assignments} WHERE id=?", values)
            conn.commit()
        finally:
            conn.close()

    def get(self, table: str, item_id: str) -> dict[str, Any] | None:
        self._validate_table(table)
        conn = self.connect()
        try:
            row = conn.execute(f"SELECT * FROM {table} WHERE id=?", (item_id,)).fetchone()
        finally:
            conn.close()
        return row_to_dict(row)

    def list_all(self, table: str) -> list[dict[str, Any]]:
        self._validate_table(table)
        conn = self.connect()
        try:
            rows = conn.execute(f"SELECT * FROM {table}").fetchall()
        finally:
            conn.close()
        return [dict(row) for row in rows]

    def inspect_get(self, table: str, item_id: str) -> dict[str, Any]:
        row = self.get(table, item_id)
        if not row:
            raise ValueError(f"{table} item not found: {item_id}")
        return self._decode_row(row)

    def inspect_list(self, table: str, limit: int = 20) -> list[dict[str, Any]]:
        self._validate_table(table)
        conn = self.connect()
        try:
            rows = conn.execute(f"SELECT * FROM {table} ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        finally:
            conn.close()
        return [self._decode_row(dict(row)) for row in rows]

    def list_evidence(self, target_type: str, target_id: str) -> list[dict[str, Any]]:
        conn = self.connect()
        try:
            rows = conn.execute(
                "SELECT * FROM evidence WHERE target_type=? AND target_id=? ORDER BY created_at",
                (target_type, target_id),
            ).fetchall()
        finally:
            conn.close()
        return [dict(row) for row in rows]

    def inspect_evidence_for_target(self, target_type: str, target_id: str) -> list[dict[str, Any]]:
        return [self._decode_row(row) for row in self.list_evidence(target_type, target_id)]

    def insert_context_run(
        self,
        run_id: str,
        created_at: str,
        task: str,
        scope: dict[str, Any],
        selected: Iterable[dict[str, Any]],
        rejected: Iterable[dict[str, Any]],
        warnings: Iterable[str],
        budget: dict[str, Any],
    ) -> str:
        return self.insert(
            "context_pack_runs",
            {
                "id": run_id,
                "created_at": created_at,
                "task": task,
                "scope_json": dumps(scope),
                "selected_json": dumps(list(selected)),
                "rejected_json": dumps(list(rejected)),
                "warnings_json": dumps(list(warnings)),
                "budget_json": dumps(budget),
            },
        )

    def _validate_table(self, table: str) -> None:
        if table not in self.TABLES:
            raise ValueError(f"unsupported table: {table}")

    def _decode_row(self, row: dict[str, Any]) -> dict[str, Any]:
        decoded = dict(row)
        for key in list(decoded.keys()):
            if key.endswith("_json"):
                decoded[key[:-5]] = loads(decoded.pop(key))
        return decoded

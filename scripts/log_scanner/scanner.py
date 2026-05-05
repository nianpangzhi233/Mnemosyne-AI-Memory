#!/usr/bin/env python3
"""scanner.py — 增量扫描 opencode 对话日志 + 片段切分

从 opencode.db 的 session/message/part 表读取对话，
按 AI Stop 事件切分为片段，输出给 filter 做去噪。
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .filter import clean_fragment

_OPENCODE_DB = Path.home() / ".local" / "share" / "opencode" / "opencode.db"
_SCAN_STATE = Path(__file__).resolve().parent.parent.parent / "hot" / ".scan_state.json"


def _load_state() -> dict:
    if _SCAN_STATE.exists():
        try:
            return json.loads(_SCAN_STATE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"last_session_id": None, "last_message_time": None}


def _save_state(state: dict):
    _SCAN_STATE.parent.mkdir(parents=True, exist_ok=True)
    _SCAN_STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _connect_utf8(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.text_factory = bytes
    return conn


def _decode(row):
    if isinstance(row, (list, tuple)):
        return [_decode(v) for v in row]
    if isinstance(row, bytes):
        return row.decode("utf-8", errors="replace")
    return row


def _get_new_sessions(db_path: str, last_session_id: str = None) -> List[dict]:
    conn = _connect_utf8(db_path)
    try:
        if last_session_id:
            rows_raw = conn.execute("""
                SELECT s.id, s.title, s.directory, s.time_created
                FROM session s
                WHERE s.time_created > (SELECT time_created FROM session WHERE id=?)
                ORDER BY s.time_created ASC
            """, (last_session_id,)).fetchall()
        else:
            rows_raw = conn.execute("""
                SELECT s.id, s.title, s.directory, s.time_created
                FROM session s
                ORDER BY s.time_created ASC
            """).fetchall()

        rows = [_decode(r) for r in rows_raw]

        return [{"id": r[0], "title": r[1] or "", "directory": r[2] or "",
                 "created": r[3]} for r in rows]
    finally:
        conn.close()


def _extract_messages(db_path: str, session_id: str) -> List[dict]:
    conn = _connect_utf8(db_path)
    try:
        msgs_raw = conn.execute("""
            SELECT m.id, m.data, m.time_created
            FROM message m
            WHERE m.session_id = ?
            ORDER BY m.time_created ASC
        """, (session_id,)).fetchall()

        msgs = [_decode(r) for r in msgs_raw]

        result = []
        for mid, data_str, ts in msgs:
            try:
                data = json.loads(data_str)
            except Exception:
                data = {}

            role = data.get("role", "unknown")
            parts_raw = conn.execute("""
                SELECT data FROM part
                WHERE message_id = ? AND session_id = ?
                ORDER BY time_created ASC
            """, (mid, session_id)).fetchall()

            parts = [_decode(r) for r in parts_raw]

            text_parts = []
            tool_parts = []
            for (pdata_str,) in parts:
                try:
                    pdata = json.loads(pdata_str)
                except Exception:
                    continue
                ptype = pdata.get("type", "")
                if ptype == "text":
                    text_parts.append(pdata.get("text", ""))
                elif ptype == "reasoning":
                    pass
                elif ptype == "tool-invocation":
                    tool_name = pdata.get("toolInvocation", {}).get("toolName", "")
                    args = pdata.get("toolInvocation", {}).get("args", {})
                    tool_parts.append({"tool": tool_name, "args": args})

            result.append({
                "id": mid, "role": role,
                "text": "\n".join(text_parts),
                "tools": tool_parts,
                "ts": ts,
            })
        return result
    finally:
        conn.close()


def _split_into_fragments(messages: List[dict]) -> List[List[dict]]:
    if not messages:
        return []

    fragments = []
    current = []

    for msg in messages:
        current.append(msg)
        if msg["role"] == "assistant" and not msg["tools"] and msg["text"]:
            fragments.append(current)
            current = []

    if current:
        fragments.append(current)

    return fragments


def scan(db_path: str = None) -> List[dict]:
    path = db_path or str(_OPENCODE_DB)
    if not Path(path).exists():
        print(f"[scanner] DB not found: {path}")
        return []

    state = _load_state()
    sessions = _get_new_sessions(path, state.get("last_session_id"))

    if not sessions:
        print("[scanner] No new sessions")
        return []

    print(f"[scanner] Found {len(sessions)} new sessions")

    all_fragments = []
    for session in sessions:
        messages = _extract_messages(path, session["id"])
        if len(messages) < 3:
            continue

        raw_fragments = _split_into_fragments(messages)

        for frag in raw_fragments:
            cleaned = clean_fragment(frag, session)
            if cleaned:
                all_fragments.append(cleaned)

        print(f"  {session['title'][:40]}: {len(messages)} msgs -> {len(raw_fragments)} fragments")

    if sessions:
        state["last_session_id"] = sessions[-1]["id"]
        state["last_scan"] = datetime.now(timezone.utc).isoformat()
        _save_state(state)

    print(f"[scanner] Total fragments: {len(all_fragments)}")
    return all_fragments

#!/usr/bin/env python3
"""scanner.py — 增量扫描 opencode 对话日志 + 片段切分

从 opencode.db 的 session/message/part 表读取对话，
按 AI Stop 事件切分为片段，输出给 filter 做去噪。
"""

import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .filter import clean_fragment


def _content_fingerprint(text: str) -> str:
    normalized = re.sub(r'\s+', ' ', text.lower().strip())
    normalized = re.sub(r'\[tool:[^\]]*\].*?(?=\[|$)', '', normalized)
    return hashlib.md5(normalized.encode("utf-8")).hexdigest()

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


def _state_time_to_ms(state: dict) -> Optional[int]:
    last_message_time = state.get("last_message_time")
    if last_message_time:
        try:
            return int(last_message_time)
        except (TypeError, ValueError):
            pass

    # Migration path for old state files that only stored last_session_id.
    # last_scan is close enough and avoids losing messages appended to the same session.
    last_scan = state.get("last_scan")
    if last_scan:
        try:
            dt = datetime.fromisoformat(last_scan)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return int(dt.timestamp() * 1000)
        except (TypeError, ValueError):
            pass

    return None


def _get_sessions_with_new_messages(db_path: str, after_ms: Optional[int] = None) -> List[dict]:
    conn = _connect_utf8(db_path)
    try:
        if after_ms is not None:
            rows_raw = conn.execute("""
                SELECT s.id, s.title, s.directory, s.time_created, MIN(m.time_created) AS first_new_message
                FROM session s
                JOIN message m ON m.session_id = s.id
                WHERE m.time_created > ?
                GROUP BY s.id, s.title, s.directory, s.time_created
                ORDER BY first_new_message ASC
            """, (after_ms,)).fetchall()
        else:
            rows_raw = conn.execute("""
                SELECT s.id, s.title, s.directory, s.time_created, MIN(m.time_created) AS first_new_message
                FROM session s
                JOIN message m ON m.session_id = s.id
                GROUP BY s.id, s.title, s.directory, s.time_created
                ORDER BY first_new_message ASC
            """).fetchall()

        rows = [_decode(r) for r in rows_raw]

        return [{"id": r[0], "title": r[1] or "", "directory": r[2] or "",
                 "created": r[3], "first_new_message": r[4]} for r in rows]
    finally:
        conn.close()


def _get_new_sessions(db_path: str, last_session_id: str = None) -> List[dict]:
    """Legacy helper kept for external callers."""
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


def _extract_messages(db_path: str, session_id: str, after_ms: Optional[int] = None) -> List[dict]:
    conn = _connect_utf8(db_path)
    try:
        if after_ms is not None:
            msgs_raw = conn.execute("""
                SELECT m.id, m.data, m.time_created
                FROM message m
                WHERE m.session_id = ? AND m.time_created > ?
                ORDER BY m.time_created ASC
            """, (session_id, after_ms)).fetchall()
        else:
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
    after_ms = _state_time_to_ms(state)
    sessions = _get_sessions_with_new_messages(path, after_ms)

    if not sessions:
        print("[scanner] No new messages")
        return []

    print(f"[scanner] Found {len(sessions)} sessions with new messages")

    all_fragments = []
    seen_fingerprints = set()
    duplicates = 0
    max_message_time = after_ms
    for session in sessions:
        messages = _extract_messages(path, session["id"], after_ms)
        for msg in messages:
            ts = msg.get("ts")
            if ts is not None and (max_message_time is None or int(ts) > max_message_time):
                max_message_time = int(ts)

        if len(messages) < 3:
            continue

        raw_fragments = _split_into_fragments(messages)

        for frag in raw_fragments:
            cleaned = clean_fragment(frag, session)
            if not cleaned:
                continue
            fp = _content_fingerprint(cleaned.get("content", ""))
            if fp in seen_fingerprints:
                duplicates += 1
                continue
            seen_fingerprints.add(fp)
            all_fragments.append(cleaned)

        print(f"  {session['title'][:40]}: {len(messages)} msgs -> {len(raw_fragments)} fragments")

    if sessions:
        state["last_session_id"] = sessions[-1]["id"]
        state["last_message_time"] = max_message_time
        state["last_scan"] = datetime.now(timezone.utc).isoformat()
        _save_state(state)

    print(f"[scanner] Total fragments: {len(all_fragments)} (deduped {duplicates} duplicates)")
    return all_fragments

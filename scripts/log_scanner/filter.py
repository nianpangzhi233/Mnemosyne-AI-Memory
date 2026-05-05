#!/usr/bin/env python3
"""filter.py — 片段级过滤 + 内容级去噪

两层过滤：
1. 片段级：丢弃纯闲聊、消息 < 3 轮、无工具调用
2. 内容级：去套话重复、去系统噪音、精简工具输出
"""

import re
from typing import Dict, List, Optional

_BOILERPLATE_PATTERNS = [
    re.compile(r"^我来帮[你你您]", re.IGNORECASE),
    re.compile(r"^让我[看看分析检查一下]", re.IGNORECASE),
    re.compile(r"^好的[，。！]?", re.IGNORECASE),
    re.compile(r"^(Sure|Of course|Let me|I'll help)", re.IGNORECASE),
    re.compile(r"^根据[您你你]的", re.IGNORECASE),
    re.compile(r"^(好的呢|很高兴为您服务)", re.IGNORECASE),
]

_NOISE_PATTERNS = [
    re.compile(r"warning:\s*LF will be replaced by CRLF", re.IGNORECASE),
    re.compile(r"deprecation\s*warning", re.IGNORECASE),
    re.compile(r"npm\s*warn\s*", re.IGNORECASE),
    re.compile(r"^\s*\.{3,}\s*$"),
    re.compile(r"pip\s*:\s*WARNING", re.IGNORECASE),
]

_TOOL_OUTPUT_SHORTEN = {
    "bash": 200,
    "read": 100,
    "glob": 50,
    "grep": 100,
}

_USER_CORRECTION_KEYWORDS = [
    "不对", "错了", "不是这样", "不要", "不能", "纠正", "你错了",
    "wrong", "incorrect", "no,", "don't", "stop",
]

_SEEN_BOILERPLATE = set()


def _is_boilerplate(text: str) -> bool:
    if not text or len(text) < 5:
        return True
    for p in _BOILERPLATE_PATTERNS:
        if p.match(text.strip()):
            return True
    return False


def _remove_noise(text: str) -> str:
    for p in _NOISE_PATTERNS:
        text = p.sub("", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _shorten_tool_output(tool_name: str, args: dict) -> str:
    max_len = _TOOL_OUTPUT_SHORTEN.get(tool_name, 200)
    args_str = str(args)
    if len(args_str) > max_len:
        return args_str[:max_len] + "..."
    return args_str


def _has_user_feedback(messages: List[dict]) -> bool:
    for msg in messages:
        if msg["role"] == "user":
            text = msg.get("text", "").lower()
            for kw in _USER_CORRECTION_KEYWORDS:
                if kw in text:
                    return True
    return False


def _has_tool_calls(messages: List[dict]) -> bool:
    for msg in messages:
        if msg.get("tools"):
            return True
    return False


def clean_fragment(messages: List[dict], session: dict) -> Optional[dict]:
    # === 片段级过滤 ===

    # 1. 消息数 < 3 轮 -> 丢弃
    if len(messages) < 3:
        return None

    # 2. 无工具调用且无用户反馈 -> 可能是闲聊，丢弃
    has_tools = _has_tool_calls(messages)
    has_feedback = _has_user_feedback(messages)
    if not has_tools and not has_feedback:
        user_texts = [m["text"] for m in messages if m["role"] == "user" and m["text"]]
        total_user_chars = sum(len(t) for t in user_texts)
        if total_user_chars < 50:
            return None

    # === 内容级去噪 ===

    clean_parts = []
    for msg in messages:
        role = msg["role"]
        text = msg.get("text", "")
        tools = msg.get("tools", [])

        if role == "user":
            cleaned = _remove_noise(text)
            if cleaned:
                clean_parts.append(f"[User] {cleaned}")

        elif role == "assistant":
            # 去套话重复
            if _is_boilerplate(text):
                normalized = text.strip()[:50]
                if normalized in _SEEN_BOILERPLATE:
                    text = ""
                else:
                    _SEEN_BOILERPLATE.add(normalized)
                    continue
            else:
                cleaned = _remove_noise(text)
                if cleaned:
                    clean_parts.append(f"[AI] {cleaned[:500]}")

            # 精简工具调用
            for tool in tools[:5]:
                tool_str = _shorten_tool_output(tool["tool"], tool.get("args", {}))
                clean_parts.append(f"[Tool:{tool['tool']}] {tool_str}")

    content = "\n".join(clean_parts)

    if len(content) < 30:
        return None

    return {
        "content": content,
        "session_title": session.get("title", ""),
        "directory": session.get("directory", ""),
        "message_count": len(messages),
        "has_tools": has_tools,
        "has_feedback": has_feedback,
    }

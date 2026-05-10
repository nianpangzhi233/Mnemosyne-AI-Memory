#!/usr/bin/env python3
"""filter.py — 片段级过滤 + 内容级去噪

核心思路：判断一个片段是否值得记住，看的是整体信息量，
不是用户写了多少字。AI 踩坑、调试、解决问题的过程本身就是高价值经验。

过滤策略：
1. 片段级：2 轮以下直接丢弃
2. 信息量评分：AI 有实质内容 +30，有工具调用 +20，有用户反馈 +15，总轮数多 +10
   总分 >= 25 才保留（有工具或 AI 有实质内容就够了）
3. 内容级：去套话、去系统噪音、精简工具输出
"""

import re
from typing import List, Optional

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

_INSIGHT_PATTERNS = [
    re.compile(r"(?:因为|由于|原因是|root.?cause|because|due to)", re.IGNORECASE),
    re.compile(r"(?:改成|换成|修改了|改成了|fixed|changed to|switched to)", re.IGNORECASE),
    re.compile(r"(?:解决了|搞定了|修好了|fixed|resolved|solved)", re.IGNORECASE),
    re.compile(r"(?:失败了|报错|崩了|error|crash|failed)", re.IGNORECASE),
    re.compile(r"(?:原来|发现|注意到|turns out|found that|noticed)", re.IGNORECASE),
    re.compile(r"(?:应该|需要|必须|should|must|need to)", re.IGNORECASE),
    re.compile(r"(?:不要|避免|别|don't|avoid|never)", re.IGNORECASE),
    re.compile(r"(?:配置|设置|参数|config|setting|parameter)", re.IGNORECASE),
    re.compile(r"(?:安装|卸载|升级|install|uninstall|upgrade|downgrade)", re.IGNORECASE),
    re.compile(r"(?:版本|version|v\d)", re.IGNORECASE),
    re.compile(r"(?:替代|方案|workaround|alternative)", re.IGNORECASE),
]

_SEEN_BOILERPLATE = set()


def _is_boilerplate(text: str) -> bool:
    if not text or len(text) < 5:
        return True
    for p in _BOILERPLATE_PATTERNS:
        if p.match(text.strip()):
            return True
    return False


def _has_insight(text: str) -> bool:
    if not text or len(text) < 15:
        return False
    return any(p.search(text) for p in _INSIGHT_PATTERNS)


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


def _ai_has_substance(messages: List[dict]) -> bool:
    for msg in messages:
        if msg["role"] != "assistant":
            continue
        text = msg.get("text", "")
        if _has_insight(text):
            return True
        if len(text) > 100:
            return True
    return False


def _fragment_score(messages: List[dict]) -> int:
    score = 0
    if _ai_has_substance(messages):
        score += 30
    if _has_tool_calls(messages):
        score += 20
    if _has_user_feedback(messages):
        score += 15
    if len(messages) >= 6:
        score += 10
    return score


def clean_fragment(messages: List[dict], session: dict) -> Optional[dict]:
    if not messages:
        return None

    score = _fragment_score(messages)
    if score < 25:
        return None

    has_tools = _has_tool_calls(messages)
    has_feedback = _has_user_feedback(messages)
    has_ai_substance = _ai_has_substance(messages)

    min_len = 20
    if not has_tools and not has_feedback and has_ai_substance:
        min_len = 40

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

            for tool in tools[:5]:
                tool_str = _shorten_tool_output(tool["tool"], tool.get("args", {}))
                clean_parts.append(f"[Tool:{tool['tool']}] {tool_str}")

    content = "\n".join(clean_parts)

    if len(content) < min_len:
        return None

    return {
        "content": content,
        "session_title": session.get("title", ""),
        "directory": session.get("directory", ""),
        "message_count": len(messages),
        "has_tools": has_tools,
        "has_feedback": has_feedback,
    }

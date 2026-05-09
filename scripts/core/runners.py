#!/usr/bin/env python3
"""Runner adapters for Skill Evolution.

The evolution engine depends on these small protocols instead of a fixed model
or provider. Concrete runners can call local gateways, external APIs, replayed
fixtures, or human/manual evaluators.
"""

import json
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Protocol


@dataclass
class AgentRunResult:
    output: str
    metadata: Dict[str, Any] = None


@dataclass
class JudgeResult:
    winner: str
    baseline_score: float
    with_skill_score: float
    delta: float
    regression: bool
    reason: str
    raw: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return {
            "winner": self.winner,
            "baseline_score": self.baseline_score,
            "with_skill_score": self.with_skill_score,
            "delta": self.delta,
            "regression": self.regression,
            "reason": self.reason,
            "raw": self.raw,
        }


class AgentRunner(Protocol):
    def run(self, prompt: str, skill_content: str = None) -> Any:
        ...


class JudgeRunner(Protocol):
    def judge(self, prompt: str, expected: str, baseline: str, with_skill: str) -> Any:
        ...


def extract_json(text: str):
    text = (text or "").strip()
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0]
    elif "```" in text:
        text = text.split("```", 1)[1].split("```", 1)[0]
    starts = [i for i in (text.find("{"), text.find("[")) if i != -1]
    if starts:
        text = text[min(starts):]
    return json.loads(text)


class OpenAICompatibleClient:
    def __init__(self, endpoint: str, model: str, api_key: str = None,
                 temperature: float = 0.1, timeout: int = 120):
        self.endpoint = endpoint
        self.model = model
        self.api_key = api_key
        self.temperature = temperature
        self.timeout = timeout

    def chat(self, system: str, user: str, max_tokens: int = 800) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": self.temperature,
            "max_tokens": max_tokens,
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        req = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        msg = body["choices"][0]["message"]
        return (msg.get("content") or msg.get("reasoning") or "").strip()


class OpenAICompatibleAgentRunner:
    def __init__(self, client: OpenAICompatibleClient, max_tokens: int = 650):
        self.client = client
        self.max_tokens = max_tokens

    def run(self, prompt: str, skill_content: str = None) -> Dict[str, str]:
        if skill_content:
            system = (
                "You are a careful senior assistant. Follow the injected skill "
                "package when relevant.\n\nSKILL PACKAGE:\n" + skill_content
            )
        else:
            system = "You are a careful senior assistant. Answer directly and concisely. Do not use any injected skill."
        return {"output": self.client.chat(system, prompt, max_tokens=self.max_tokens)}


class OpenAICompatibleJudgeRunner:
    def __init__(self, client: OpenAICompatibleClient, max_tokens: int = 650):
        self.client = client
        self.max_tokens = max_tokens

    def judge(self, prompt: str, expected: str, baseline: str, with_skill: str) -> Dict[str, Any]:
        system = (
            "You are an independent evaluator. Compare baseline and with_skill. "
            "Return JSON only with keys: winner, baseline_score, with_skill_score, "
            "delta, regression, reason. Scores are 0-10. Penalize irrelevant "
            "verbosity; reward diagnostic order and correctness."
        )
        user = (
            f"Prompt: {prompt}\n\nExpected intent: {expected}\n\n"
            f"Baseline answer:\n{baseline}\n\nWith-skill answer:\n{with_skill}\n"
        )
        raw = self.client.chat(system, user, max_tokens=self.max_tokens)
        try:
            data = extract_json(raw)
        except Exception:
            data = {"reason": raw}
        if isinstance(data, dict):
            data["raw"] = raw
            return data
        return {"reason": raw, "raw": raw}


class ReplayAgentRunner:
    def __init__(self, baseline_output: str, with_skill_output: str):
        self.baseline_output = baseline_output
        self.with_skill_output = with_skill_output

    def run(self, prompt: str, skill_content: str = None) -> Dict[str, str]:
        return {"output": self.with_skill_output if skill_content else self.baseline_output}


class ReplayJudgeRunner:
    def __init__(self, result: Dict[str, Any]):
        self.result = result

    def judge(self, prompt: str, expected: str, baseline: str, with_skill: str) -> Dict[str, Any]:
        return dict(self.result)

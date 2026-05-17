from __future__ import annotations

from .gates import WriteGate
from .models import dumps, loads, new_id, now_iso
from .store import SQLiteV8Store


class LifecycleManager:
    ALLOWED_MANUAL_STATUSES = {"demoted", "deprecated", "locked"}

    def __init__(self, store: SQLiteV8Store, write_gate: WriteGate | None = None):
        self.store = store
        self.write_gate = write_gate or WriteGate(store)

    def promote(self, candidate_id: str) -> str:
        candidate = self.store.get("candidates", candidate_id)
        if not candidate:
            raise ValueError("candidate does not exist")
        ok, reasons = self.write_gate.check_promote(candidate)
        if not ok:
            raise ValueError("promotion blocked: " + ",".join(reasons))
        memory_id = new_id("mem")
        now = now_iso()
        self.store.insert(
            "memories",
            {
                "id": memory_id,
                "created_at": now,
                "updated_at": now,
                "candidate_id": candidate_id,
                "memory_type": candidate["candidate_type"],
                "content": candidate["content"],
                "scope_json": candidate["scope_json"],
                "trigger": candidate["trigger"],
                "risk": candidate["risk"],
                "confidence": 0.7,
                "status": "validated",
                "freshness": 1.0,
                "read_policy_json": dumps({}),
                "revision": 1,
                "metadata_json": candidate["metadata_json"],
            },
        )
        self.store.update("candidates", candidate_id, {"status": "promoted"})
        return memory_id

    def set_status(self, memory_id: str, status: str) -> None:
        if status not in self.ALLOWED_MANUAL_STATUSES:
            raise ValueError(f"unsupported lifecycle status: {status}")
        memory = self.store.get("memories", memory_id)
        if not memory:
            raise ValueError("memory does not exist")
        self.store.update(
            "memories",
            memory_id,
            {"status": status, "updated_at": now_iso(), "revision": int(memory["revision"]) + 1},
        )

    def mark_stale(self, memory_id: str) -> None:
        memory = self.store.get("memories", memory_id)
        if not memory:
            raise ValueError("memory does not exist")
        self.store.update(
            "memories",
            memory_id,
            {"status": "stale", "freshness": 0.0, "updated_at": now_iso(), "revision": int(memory["revision"]) + 1},
        )

    def demote(self, memory_id: str) -> str:
        self.set_status(memory_id, "demoted")
        return memory_id

    def deprecate(self, memory_id: str) -> str:
        self.set_status(memory_id, "deprecated")
        return memory_id

    def stale(self, memory_id: str) -> str:
        self.mark_stale(memory_id)
        return memory_id

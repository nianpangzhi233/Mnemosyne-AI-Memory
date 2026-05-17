from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def dumps(value: Any) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=True, sort_keys=True)


def loads(value: str | None, default: Any = None) -> Any:
    if value in (None, ""):
        return {} if default is None else default
    return json.loads(value)


def normalize_scope(scope: dict[str, Any] | None) -> dict[str, str]:
    if not scope:
        return {}
    return {str(key): str(value) for key, value in scope.items() if value not in (None, "")}


def row_to_dict(row: Any) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)

from __future__ import annotations

from datetime import date, datetime
from typing import Any


def iso(value: datetime | date | None) -> str | None:
    return value.isoformat() if value else None


def ensure_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: ensure_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [ensure_json(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value

from __future__ import annotations

from typing import Any, TypedDict

from agent_core.schemas.common import CognitionDecision


class CognitionCareState(TypedDict, total=False):
    elder_id: str
    trigger: str
    now_ts: str
    profile: dict[str, Any]
    daily_status: dict[str, Any]
    history: list[dict[str, Any]]
    decision: CognitionDecision
    saved_result: dict[str, Any]
    skip_persist: bool

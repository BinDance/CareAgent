from __future__ import annotations

from typing import Any, TypedDict

from agent_core.schemas.common import FamilyInstructionResult


class FamilyInstructionState(TypedDict, total=False):
    elder_id: str
    input_text: str
    profile: dict[str, Any]
    daily_status: dict[str, Any]
    result: FamilyInstructionResult
    persisted_result: dict[str, Any]

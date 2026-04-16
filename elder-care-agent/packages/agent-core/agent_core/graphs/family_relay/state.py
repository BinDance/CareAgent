from __future__ import annotations

from typing import Any, TypedDict

from agent_core.schemas.common import RelayMessageResult


class FamilyRelayState(TypedDict, total=False):
    elder_id: str
    source: str
    raw_text: str
    relay: RelayMessageResult
    result: dict[str, Any]

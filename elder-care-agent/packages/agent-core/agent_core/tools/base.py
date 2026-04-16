from __future__ import annotations

from typing import Any, Protocol


class ToolExecutor(Protocol):
    async def call(self, name: str, arguments: dict[str, Any]) -> Any:
        ...

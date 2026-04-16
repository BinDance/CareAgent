
from __future__ import annotations

import inspect
from typing import Any, Callable


class LocalToolExecutor:
    def __init__(self, handlers: dict[str, Callable[..., Any]]):
        self.handlers = handlers

    async def call(self, name: str, arguments: dict[str, Any]) -> Any:
        if name not in self.handlers:
            raise KeyError(f'Unknown local tool: {name}')
        result = self.handlers[name](**arguments)
        if inspect.isawaitable(result):
            return await result
        return result

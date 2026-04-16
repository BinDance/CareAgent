from __future__ import annotations

import json
from typing import Any

from langchain_mcp_adapters.client import MultiServerMCPClient

from agent_core.config import get_settings


class RemoteMCPToolExecutor:
    def __init__(self, server_url: str | None = None):
        self.server_url = server_url or get_settings().mcp_server_url
        self._client = MultiServerMCPClient(
            {
                'eldercare': {
                    'transport': 'http',
                    'url': self.server_url,
                }
            }
        )
        self._tools: dict[str, Any] | None = None

    async def _load_tools(self) -> dict[str, Any]:
        if self._tools is None:
            tools = await self._client.get_tools()
            self._tools = {tool.name: tool for tool in tools}
        return self._tools

    async def call(self, name: str, arguments: dict[str, Any]) -> Any:
        tools = await self._load_tools()
        if name not in tools:
            raise KeyError(f'Unknown MCP tool: {name}')
        result = await tools[name].ainvoke(arguments)
        return self._normalize_result(result)

    def _normalize_result(self, result: Any) -> Any:
        if isinstance(result, (dict, list, int, float, bool)) or result is None:
            return result
        if isinstance(result, str):
            try:
                return json.loads(result)
            except json.JSONDecodeError:
                return {'text': result}
        if hasattr(result, 'content'):
            content = getattr(result, 'content')
            if isinstance(content, str):
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    return {'text': content}
            return content
        return {'value': str(result)}

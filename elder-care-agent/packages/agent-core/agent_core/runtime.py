from __future__ import annotations

from agent_core.graphs.cognition_care.graph import build_graph as build_cognition_graph
from agent_core.graphs.elder_conversation.graph import build_graph as build_elder_graph
from agent_core.graphs.family_instruction.graph import build_graph as build_family_instruction_graph
from agent_core.graphs.family_relay.graph import build_graph as build_family_relay_graph
from agent_core.graphs.prescription.graph import build_graph as build_prescription_graph
from agent_core.provider.llm import LLMProvider
from agent_core.tools.remote_mcp import RemoteMCPToolExecutor


class AgentRuntime:
    def __init__(self, llm: LLMProvider | None = None, tools: RemoteMCPToolExecutor | None = None):
        self.llm = llm or LLMProvider()
        self.tools = tools or RemoteMCPToolExecutor()
        self._elder_graph = build_elder_graph(self.llm, self.tools)
        self._family_instruction_graph = build_family_instruction_graph(self.llm, self.tools)
        self._prescription_graph = build_prescription_graph(self.llm, self.tools)
        self._family_relay_graph = build_family_relay_graph(self.llm, self.tools)
        self._cognition_graph = build_cognition_graph(self.llm, self.tools)

    async def run_elder_conversation(self, elder_id: str, input_text: str, now_ts: str | None = None) -> dict:
        return await self._elder_graph.ainvoke({'elder_id': elder_id, 'input_text': input_text, 'now_ts': now_ts})

    async def run_family_instruction(self, elder_id: str, input_text: str) -> dict:
        return await self._family_instruction_graph.ainvoke({'elder_id': elder_id, 'input_text': input_text})

    async def run_prescription(self, elder_id: str, file_path: str, file_name: str, mime_type: str) -> dict:
        return await self._prescription_graph.ainvoke({'elder_id': elder_id, 'file_path': file_path, 'file_name': file_name, 'mime_type': mime_type})

    async def run_family_relay(self, elder_id: str, source: str, raw_text: str) -> dict:
        return await self._family_relay_graph.ainvoke({'elder_id': elder_id, 'source': source, 'raw_text': raw_text})

    async def run_cognition_care(self, elder_id: str, trigger: str = 'scheduler', now_ts: str | None = None) -> dict:
        return await self._cognition_graph.ainvoke({'elder_id': elder_id, 'trigger': trigger, 'now_ts': now_ts})

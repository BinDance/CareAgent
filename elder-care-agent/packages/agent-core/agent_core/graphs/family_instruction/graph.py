from __future__ import annotations

from functools import partial

from langgraph.graph import END, START, StateGraph

from agent_core.graphs.family_instruction.nodes import analyze_instruction, load_daily_status, load_profile, persist_result
from agent_core.graphs.family_instruction.state import FamilyInstructionState
from agent_core.provider.llm import LLMProvider
from agent_core.tools.base import ToolExecutor


def build_graph(llm: LLMProvider, tools: ToolExecutor):
    graph = StateGraph(FamilyInstructionState)
    graph.add_node('load_profile', partial(load_profile, tools=tools))
    graph.add_node('load_daily_status', partial(load_daily_status, tools=tools))
    graph.add_node('analyze_instruction', partial(analyze_instruction, llm=llm))
    graph.add_node('persist_result', partial(persist_result, tools=tools))
    graph.add_edge(START, 'load_profile')
    graph.add_edge('load_profile', 'load_daily_status')
    graph.add_edge('load_daily_status', 'analyze_instruction')
    graph.add_edge('analyze_instruction', 'persist_result')
    graph.add_edge('persist_result', END)
    return graph.compile()

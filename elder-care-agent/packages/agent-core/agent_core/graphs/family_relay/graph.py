from __future__ import annotations

from functools import partial

from langgraph.graph import END, START, StateGraph

from agent_core.graphs.family_relay.nodes import persist_relay, summarize_relay
from agent_core.graphs.family_relay.state import FamilyRelayState
from agent_core.provider.llm import LLMProvider
from agent_core.tools.base import ToolExecutor


def build_graph(llm: LLMProvider, tools: ToolExecutor):
    graph = StateGraph(FamilyRelayState)
    graph.add_node('summarize_relay', partial(summarize_relay, llm=llm))
    graph.add_node('persist_relay', partial(persist_relay, tools=tools))
    graph.add_edge(START, 'summarize_relay')
    graph.add_edge('summarize_relay', 'persist_relay')
    graph.add_edge('persist_relay', END)
    return graph.compile()

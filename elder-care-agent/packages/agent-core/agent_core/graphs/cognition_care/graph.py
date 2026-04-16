from __future__ import annotations

from functools import partial

from langgraph.graph import END, START, StateGraph

from agent_core.graphs.cognition_care.nodes import decide_interaction, load_history, load_profile, load_status, persist_session
from agent_core.graphs.cognition_care.state import CognitionCareState
from agent_core.provider.llm import LLMProvider
from agent_core.tools.base import ToolExecutor


def build_graph(llm: LLMProvider, tools: ToolExecutor):
    graph = StateGraph(CognitionCareState)
    graph.add_node('load_profile', partial(load_profile, tools=tools))
    graph.add_node('load_status', partial(load_status, tools=tools))
    graph.add_node('load_history', partial(load_history, tools=tools))
    graph.add_node('decide_interaction', partial(decide_interaction, llm=llm))
    graph.add_node('persist_session', partial(persist_session, tools=tools))
    graph.add_edge(START, 'load_profile')
    graph.add_edge('load_profile', 'load_status')
    graph.add_edge('load_status', 'load_history')
    graph.add_edge('load_history', 'decide_interaction')
    graph.add_edge('decide_interaction', 'persist_session')
    graph.add_edge('persist_session', END)
    return graph.compile()

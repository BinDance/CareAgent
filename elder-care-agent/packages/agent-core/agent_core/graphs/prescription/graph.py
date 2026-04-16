from __future__ import annotations

from functools import partial

from langgraph.graph import END, START, StateGraph

from agent_core.graphs.prescription.nodes import parse_multimodal, persist_plan, prepare_payload, receive_file, risk_check
from agent_core.graphs.prescription.state import PrescriptionState
from agent_core.provider.llm import LLMProvider
from agent_core.tools.base import ToolExecutor


def build_graph(llm: LLMProvider, tools: ToolExecutor):
    graph = StateGraph(PrescriptionState)
    graph.add_node('receive_file', receive_file)
    graph.add_node('prepare_payload', prepare_payload)
    graph.add_node('parse_multimodal', partial(parse_multimodal, llm=llm))
    graph.add_node('risk_check', partial(risk_check, tools=tools))
    graph.add_node('persist_plan', partial(persist_plan, tools=tools))
    graph.add_edge(START, 'receive_file')
    graph.add_edge('receive_file', 'prepare_payload')
    graph.add_edge('prepare_payload', 'parse_multimodal')
    graph.add_edge('parse_multimodal', 'risk_check')
    graph.add_edge('risk_check', 'persist_plan')
    graph.add_edge('persist_plan', END)
    return graph.compile()

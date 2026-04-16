from __future__ import annotations

from functools import partial

from langgraph.graph import END, START, StateGraph

from agent_core.graphs.elder_conversation.nodes import (
    call_mcp_tools_if_needed,
    classify_intent,
    decide_if_cognition_interaction,
    decide_if_deliver_notice,
    decide_if_medication_reminder,
    decide_if_tool_call,
    detect_mood_signal,
    detect_risk_signal,
    generate_elder_response,
    load_context,
    load_daily_status,
    load_due_medications,
    load_pending_notices,
    load_profile,
    update_daily_status,
    write_back_conversation_summary,
    write_back_profile_candidates,
)
from agent_core.graphs.elder_conversation.state import ElderConversationState
from agent_core.provider.llm import LLMProvider
from agent_core.tools.base import ToolExecutor


def build_graph(llm: LLMProvider, tools: ToolExecutor):
    graph = StateGraph(ElderConversationState)
    graph.add_node('load_context', partial(load_context, tools=tools))
    graph.add_node('load_profile', partial(load_profile, tools=tools))
    graph.add_node('load_daily_status', partial(load_daily_status, tools=tools))
    graph.add_node('load_pending_notices', partial(load_pending_notices, tools=tools))
    graph.add_node('load_due_medications', partial(load_due_medications, tools=tools))
    graph.add_node('detect_mood_signal', partial(detect_mood_signal, llm=llm))
    graph.add_node('detect_risk_signal', partial(detect_risk_signal, llm=llm))
    graph.add_node('classify_intent', partial(classify_intent, llm=llm))
    graph.add_node('decide_if_tool_call', decide_if_tool_call)
    graph.add_node('call_mcp_tools_if_needed', partial(call_mcp_tools_if_needed, tools=tools))
    graph.add_node('decide_if_deliver_notice', decide_if_deliver_notice)
    graph.add_node('decide_if_medication_reminder', decide_if_medication_reminder)
    graph.add_node('decide_if_cognition_interaction', partial(decide_if_cognition_interaction, llm=llm))
    graph.add_node('generate_elder_response', partial(generate_elder_response, llm=llm))
    graph.add_node('write_back_conversation_summary', partial(write_back_conversation_summary, tools=tools))
    graph.add_node('write_back_profile_candidates', partial(write_back_profile_candidates, llm=llm, tools=tools))
    graph.add_node('update_daily_status', partial(update_daily_status, tools=tools))

    graph.add_edge(START, 'load_context')
    graph.add_edge('load_context', 'load_profile')
    graph.add_edge('load_profile', 'load_daily_status')
    graph.add_edge('load_daily_status', 'load_pending_notices')
    graph.add_edge('load_pending_notices', 'load_due_medications')
    graph.add_edge('load_due_medications', 'detect_mood_signal')
    graph.add_edge('detect_mood_signal', 'detect_risk_signal')
    graph.add_edge('detect_risk_signal', 'classify_intent')
    graph.add_edge('classify_intent', 'decide_if_tool_call')
    graph.add_edge('decide_if_tool_call', 'call_mcp_tools_if_needed')
    graph.add_edge('call_mcp_tools_if_needed', 'decide_if_deliver_notice')
    graph.add_edge('decide_if_deliver_notice', 'decide_if_medication_reminder')
    graph.add_edge('decide_if_medication_reminder', 'decide_if_cognition_interaction')
    graph.add_edge('decide_if_cognition_interaction', 'generate_elder_response')
    graph.add_edge('generate_elder_response', 'write_back_conversation_summary')
    graph.add_edge('write_back_conversation_summary', 'write_back_profile_candidates')
    graph.add_edge('write_back_profile_candidates', 'update_daily_status')
    graph.add_edge('update_daily_status', END)
    return graph.compile()

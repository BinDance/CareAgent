from __future__ import annotations

from typing import Any, TypedDict

from agent_core.schemas.common import ElderResponsePlan, IntentClassification, MoodSignal, ProfileCandidateSet, RiskSignal


class ElderConversationState(TypedDict, total=False):
    elder_id: str
    input_text: str
    now_ts: str
    recent_conversations: list[dict[str, Any]]
    profile: dict[str, Any]
    daily_status: dict[str, Any]
    pending_notices: list[dict[str, Any]]
    due_medications: list[dict[str, Any]]
    family_messages: list[dict[str, Any]]
    mood_signal: MoodSignal
    risk_signal: RiskSignal
    intent: IntentClassification
    tool_actions: list[str]
    tool_results: dict[str, Any]
    selected_notices: list[dict[str, Any]]
    selected_due_medications: list[dict[str, Any]]
    selected_family_messages: list[dict[str, Any]]
    cognition_decision: dict[str, Any]
    response: ElderResponsePlan
    memory_candidates: ProfileCandidateSet
    daily_patch: dict[str, Any]

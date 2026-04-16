from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from dateutil.parser import isoparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from agent_core.provider.llm import LLMProvider
from agent_core.schemas.common import ElderResponsePlan
from agent_core.tools.base import ToolExecutor


def _notice_matches_strategy(notice: dict[str, Any], daily_status: dict[str, Any]) -> bool:
    return _notice_matches_strategy_at(notice, daily_status, None, None)


def _notice_matches_strategy_at(
    notice: dict[str, Any],
    daily_status: dict[str, Any],
    now_ts: str | None,
    timezone_name: str | None,
) -> bool:
    strategy = notice.get('delivery_strategy') or 'next_free_slot'
    if now_ts:
        parsed = isoparse(str(now_ts))
        if timezone_name and parsed.tzinfo:
            try:
                hour = parsed.astimezone(ZoneInfo(timezone_name)).hour
            except ZoneInfoNotFoundError:
                hour = parsed.hour
        else:
            hour = parsed.hour
    else:
        hour = datetime.now().hour
    if strategy == 'now':
        return True
    if strategy == 'before_meal':
        return hour in {11, 12, 17, 18}
    if strategy == 'after_nap':
        return hour in {14, 15, 16}
    if strategy == 'evening':
        return hour >= 18
    if strategy == 'manual_review':
        return False
    return not daily_status.get('is_resting', False)


def _state_now_iso(state: dict[str, Any]) -> str:
    return str(state.get('now_ts') or datetime.now(timezone.utc).isoformat())


async def load_context(state: dict[str, Any], tools: ToolExecutor) -> dict[str, Any]:
    recent = await tools.call('get_recent_conversations', {'elder_id': state['elder_id'], 'limit': 8})
    family_messages = await tools.call('list_family_messages', {'elder_id': state['elder_id']})
    return {
        'recent_conversations': recent,
        'family_messages': family_messages,
    }


async def load_profile(state: dict[str, Any], tools: ToolExecutor) -> dict[str, Any]:
    return {'profile': await tools.call('get_elder_profile', {'elder_id': state['elder_id']})}


async def load_daily_status(state: dict[str, Any], tools: ToolExecutor) -> dict[str, Any]:
    return {'daily_status': await tools.call('get_today_status', {'elder_id': state['elder_id']})}


async def load_pending_notices(state: dict[str, Any], tools: ToolExecutor) -> dict[str, Any]:
    notices = await tools.call('list_pending_notices', {'elder_id': state['elder_id']})
    return {'pending_notices': notices}


async def load_due_medications(state: dict[str, Any], tools: ToolExecutor) -> dict[str, Any]:
    due = await tools.call('get_due_medications', {'elder_id': state['elder_id'], 'now_ts': _state_now_iso(state)})
    return {'due_medications': due}


async def detect_mood_signal(state: dict[str, Any], llm: LLMProvider) -> dict[str, Any]:
    mood = await llm.analyze_mood(state['input_text'], {'recent_conversations': state.get('recent_conversations', [])})
    return {'mood_signal': mood}


async def detect_risk_signal(state: dict[str, Any], llm: LLMProvider) -> dict[str, Any]:
    risk = await llm.analyze_risk(state['input_text'], {'recent_conversations': state.get('recent_conversations', [])})
    return {'risk_signal': risk}


async def classify_intent(state: dict[str, Any], llm: LLMProvider) -> dict[str, Any]:
    intent = await llm.classify_elder_intent(
        state['input_text'],
        {
            'daily_status': state.get('daily_status', {}),
            'profile': state.get('profile', {}),
            'recent_conversations': state.get('recent_conversations', [])[-6:],
        },
    )
    return {'intent': intent}


async def decide_if_tool_call(state: dict[str, Any]) -> dict[str, Any]:
    actions: list[str] = []
    intent = state['intent']
    risk = state['risk_signal']
    if getattr(risk, 'requires_alert', False):
        actions.append('raise_alert')
    if intent.primary_intent == 'family_relay':
        actions.append('send_message_to_family')
    if intent.primary_intent == 'medication_confirmation' and state.get('due_medications'):
        actions.append('confirm_medication_taken')
    return {'tool_actions': actions}


async def call_mcp_tools_if_needed(state: dict[str, Any], tools: ToolExecutor) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for action in state.get('tool_actions', []):
        if action == 'raise_alert':
            results[action] = await tools.call(
                'raise_alert',
                {
                    'elder_id': state['elder_id'],
                    'reason': ', '.join(state['risk_signal'].indicators) or state['input_text'],
                    'level': state['risk_signal'].level,
                },
            )
        elif action == 'send_message_to_family':
            results[action] = await tools.call('send_message_to_family', {'elder_id': state['elder_id'], 'summary_text': state['intent'].family_message or state['input_text']})
        elif action == 'confirm_medication_taken' and state.get('due_medications'):
            confirmations: list[dict[str, Any]] = []
            seen_plan_ids: set[str] = set()
            for item in state['due_medications']:
                plan_id = item.get('id')
                if not plan_id or plan_id in seen_plan_ids:
                    continue
                seen_plan_ids.add(plan_id)
                confirmations.append(
                    await tools.call(
                        'confirm_medication_taken',
                        {'plan_id': plan_id, 'taken_at': _state_now_iso(state), 'source': 'elder_voice'},
                    )
                )
            results[action] = confirmations
    return {'tool_results': results}


async def decide_if_deliver_notice(state: dict[str, Any]) -> dict[str, Any]:
    if state['intent'].primary_intent != 'ask_notice':
        return {'selected_notices': [], 'selected_family_messages': []}
    timezone_name = None
    if isinstance(state.get('profile'), dict):
        timezone_name = state['profile'].get('timezone')
    selected_notices = [
        notice
        for notice in state.get('pending_notices', [])
        if _notice_matches_strategy_at(notice, state.get('daily_status', {}), state.get('now_ts'), str(timezone_name) if timezone_name else None)
    ][:1]
    selected_messages = [message for message in state.get('family_messages', []) if message.get('direction') == 'family_to_elder' and message.get('status') == 'pending'][:1]
    return {'selected_notices': selected_notices, 'selected_family_messages': selected_messages}


async def decide_if_medication_reminder(state: dict[str, Any]) -> dict[str, Any]:
    if state['intent'].primary_intent == 'medication_confirmation':
        return {'selected_due_medications': []}
    if not any(token in state.get('input_text', '') for token in ['药', '吃药', '服药', '药片', '胶囊', '药丸']):
        return {'selected_due_medications': []}
    selected = [item for item in state.get('due_medications', []) if item.get('status') == 'active'][:1]
    return {'selected_due_medications': selected}


async def decide_if_cognition_interaction(state: dict[str, Any], llm: LLMProvider) -> dict[str, Any]:
    decision = await llm.decide_cognition(
        {
            'profile': state.get('profile', {}),
            'daily_status': state.get('daily_status', {}),
            'recent_conversations': state.get('recent_conversations', []),
            'mood_signal': state['mood_signal'].model_dump(),
        }
    )
    return {'cognition_decision': decision.model_dump()}


async def generate_elder_response(state: dict[str, Any], llm: LLMProvider) -> dict[str, Any]:
    response = await llm.generate_elder_response(
        state['input_text'],
        {
            'recent_conversations': state.get('recent_conversations', []),
            'profile': state.get('profile', {}),
            'daily_status': state.get('daily_status', {}),
            'selected_notices': state.get('selected_notices', []),
            'selected_due_medications': state.get('selected_due_medications', []),
            'selected_family_messages': state.get('selected_family_messages', []),
            'risk_signal': state['risk_signal'].model_dump(),
            'mood_signal': state['mood_signal'].model_dump(),
            'intent': state['intent'].model_dump(),
            'cognition_decision': state.get('cognition_decision', {}),
        },
    )
    return {'response': response}


async def write_back_conversation_summary(state: dict[str, Any], tools: ToolExecutor) -> dict[str, Any]:
    response: ElderResponsePlan = state['response']
    await tools.call(
        'save_conversation',
        {
            'elder_id': state['elder_id'],
            'speaker': 'elder',
            'content': state['input_text'],
            'summary_json': {
                'mood': state['mood_signal'].model_dump(),
                'intent': state['intent'].model_dump(),
                'risk': state['risk_signal'].model_dump(),
            },
        },
    )
    await tools.call(
        'save_conversation',
        {
            'elder_id': state['elder_id'],
            'speaker': 'agent',
            'content': response.reply_text,
            'summary_json': {
                'delivered_notice_ids': response.deliver_notice_ids,
                'delivered_message_ids': response.deliver_message_ids,
                'reminder_plan_ids': response.reminder_plan_ids,
            },
        },
    )
    for notice_id in response.deliver_notice_ids:
        await tools.call('mark_notice_delivered', {'notice_id': notice_id, 'delivered_at': _state_now_iso(state)})
    for message_id in response.deliver_message_ids:
        await tools.call('mark_family_message_delivered', {'message_id': message_id, 'delivered_at': _state_now_iso(state)})
    for plan_id in response.reminder_plan_ids:
        await tools.call('log_medication_reminder', {'plan_id': plan_id, 'scheduled_at': _state_now_iso(state)})
    return {}


async def write_back_profile_candidates(state: dict[str, Any], llm: LLMProvider, tools: ToolExecutor) -> dict[str, Any]:
    memory = await llm.extract_memory_candidates(
        state['input_text'],
        {
            'profile': state.get('profile', {}),
            'daily_status': state.get('daily_status', {}),
            'mood_signal': state['mood_signal'].model_dump(),
            'risk_signal': state['risk_signal'].model_dump(),
            'cognition_follow_up': state.get('cognition_follow_up', False),
        },
    )
    await tools.call('propose_profile_update', {'elder_id': state['elder_id'], 'candidate_json': memory.model_dump()})
    return {'memory_candidates': memory}


async def update_daily_status(state: dict[str, Any], tools: ToolExecutor) -> dict[str, Any]:
    patch = {
        'last_interaction_at': _state_now_iso(state),
        'mood': state['mood_signal'].label,
        'mood_summary': state['mood_signal'].summary,
        'contacted_family_today': bool(state['response'].family_message_sent),
    }
    if state['intent'].medication_taken:
        patch['medication_taken'] = True
    await tools.call('update_today_status', {'elder_id': state['elder_id'], 'patch_json': patch})
    return {'daily_patch': patch}

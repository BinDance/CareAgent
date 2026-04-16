from __future__ import annotations

from datetime import datetime
from typing import Any

from agent_core.provider.llm import LLMProvider
from agent_core.tools.base import ToolExecutor


async def load_profile(state: dict[str, Any], tools: ToolExecutor) -> dict[str, Any]:
    return {'profile': await tools.call('get_elder_profile', {'elder_id': state['elder_id']})}


async def load_daily_status(state: dict[str, Any], tools: ToolExecutor) -> dict[str, Any]:
    return {'daily_status': await tools.call('get_today_status', {'elder_id': state['elder_id']})}


async def analyze_instruction(state: dict[str, Any], llm: LLMProvider) -> dict[str, Any]:
    result = await llm.analyze_family_instruction(state['input_text'], {'profile': state.get('profile', {}), 'daily_status': state.get('daily_status', {})})
    return {'result': result}


async def persist_result(state: dict[str, Any], tools: ToolExecutor) -> dict[str, Any]:
    result = state['result']
    payload: dict[str, Any] = {'kind': result.kind, 'summary': result.summarized_notice}
    if result.kind == 'notice':
        payload['notice'] = await tools.call(
            'create_family_notice',
            {
                'elder_id': state['elder_id'],
                'raw_text': state['input_text'],
                'urgency': result.urgency,
                'strategy': result.delivery_strategy or 'next_free_slot',
                'summarized_notice': result.summarized_notice,
                'rationale': result.rationale,
            },
        )
    elif result.kind == 'message':
        payload['message'] = await tools.call('send_message_to_elder', {'elder_id': state['elder_id'], 'text': result.relay_message or result.summarized_notice})
    elif result.kind == 'query':
        payload['query'] = await tools.call('generate_daily_report', {'elder_id': state['elder_id'], 'date': datetime.utcnow().date().isoformat()})
    if result.urgency == 'critical':
        payload['review'] = await tools.call('request_human_review', {'task_type': 'critical_family_instruction', 'payload': {'elder_id': state['elder_id'], 'text': state['input_text']}})
    return {'persisted_result': payload}

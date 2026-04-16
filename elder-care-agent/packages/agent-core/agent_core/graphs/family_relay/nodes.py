from __future__ import annotations

from agent_core.provider.llm import LLMProvider
from agent_core.tools.base import ToolExecutor


async def summarize_relay(state: dict[str, str], llm: LLMProvider) -> dict[str, object]:
    direction = 'elder_to_family' if state['source'] == 'elder' else 'family_to_elder'
    relay = await llm.summarize_relay(state['raw_text'], direction)
    return {'relay': relay}


async def persist_relay(state: dict[str, object], tools: ToolExecutor) -> dict[str, object]:
    relay = state['relay']
    if relay.direction == 'elder_to_family':
        result = await tools.call('send_message_to_family', {'elder_id': state['elder_id'], 'summary_text': relay.summary_text})
    else:
        result = await tools.call('send_message_to_elder', {'elder_id': state['elder_id'], 'text': relay.summary_text})
    return {'result': result}

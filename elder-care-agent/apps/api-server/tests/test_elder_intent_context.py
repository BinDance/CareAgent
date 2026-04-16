import asyncio

from agent_core.graphs.elder_conversation.nodes import classify_intent
from agent_core.schemas.common import IntentClassification


class CaptureIntentLLM:
    def __init__(self):
        self.last_context = None

    async def classify_elder_intent(self, text, context):
        self.last_context = context
        return IntentClassification(primary_intent='cognition_response', needs_tool_call=False, confidence=0.9, rationale='test')


def test_classify_intent_includes_recent_conversations_context():
    llm = CaptureIntentLLM()
    state = {
        'input_text': '我忘记了',
        'daily_status': {'mood': 'calm'},
        'profile': {'stable_profile': {'liked_topics': ['以前的工作']}},
        'recent_conversations': [
            {'speaker': 'agent', 'content': '您以前工作时最有成就感的一件事是什么？'},
            {'speaker': 'elder', 'content': '我想想。'},
        ],
    }

    result = asyncio.run(classify_intent(state, llm))

    assert result['intent'].primary_intent == 'cognition_response'
    assert llm.last_context is not None
    assert 'recent_conversations' in llm.last_context
    assert llm.last_context['recent_conversations'][-1]['content'] == '我想想。'

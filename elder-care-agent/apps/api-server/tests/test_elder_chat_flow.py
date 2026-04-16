from langchain_core.messages import AIMessage

from eldercare_api.deps import get_agent_runtime


class FakeFreeformChat:
    async def ainvoke(self, _messages):
        return AIMessage(content='当然可以，我给您讲个小故事。从前有位奶奶，每天早上都在阳台晒太阳，心里就暖暖的。')


def test_elder_plain_chat_uses_freeform_model_reply(app_client):
    runtime = app_client.app.dependency_overrides[get_agent_runtime]()
    runtime.llm._chat = FakeFreeformChat()

    response = app_client.post('/api/elder/voice-input', json={'elder_id': 'elder-demo-1', 'transcript': '给我讲个故事'})
    assert response.status_code == 200

    payload = response.json()
    assert payload['reply_text'].startswith('当然可以，我给您讲个小故事')
    assert payload['delivered_notice_ids'] == []
    assert payload['reminder_plan_ids'] == []

def test_elder_relay_message_flow(app_client):
    response = app_client.post('/api/elder/voice-input', json={'elder_id': 'elder-demo-1', 'transcript': '帮我跟我儿子说一下，今天买青菜回家。'})
    assert response.status_code == 200
    messages = app_client.get('/api/family/messages/elder-demo-1')
    assert messages.status_code == 200
    items = messages.json()['items']
    assert any(item['direction'] == 'elder_to_family' and '买青菜' in item['summary_text'] for item in items)

def test_family_notice_flow(app_client):
    response = app_client.post('/api/family/notice', json={'elder_id': 'elder-demo-1', 'text': '今晚我要加班，你跟妈妈说先吃饭，不用等我电话。'})
    assert response.status_code == 200
    data = response.json()
    assert data['kind'] == 'notice'
    assert data['stored_notice'] is not None
    dashboard = app_client.get('/api/family/dashboard/elder-demo-1')
    assert dashboard.status_code == 200
    assert any('先吃晚饭' in item['summarized_notice'] or '先吃饭' in item['summarized_notice'] for item in dashboard.json()['notices'])

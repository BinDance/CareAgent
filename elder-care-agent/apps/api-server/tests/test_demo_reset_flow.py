def test_family_demo_reset_restores_seed_data(app_client):
    create_response = app_client.post(
        '/api/family/medication-plans',
        json={
            'elder_id': 'elder-demo-1',
            'medication_name': '临时测试药',
            'dose': '1片',
            'frequency': '每日1次',
            'meal_timing': '饭后',
            'time_slots': ['09:00'],
        },
    )
    assert create_response.status_code == 200

    message_response = app_client.post(
        '/api/family/message-to-elder',
        json={'elder_id': 'elder-demo-1', 'text': '这是一条临时 demo 留言。'},
    )
    assert message_response.status_code == 200

    reset_response = app_client.post('/api/family/demo-reset')
    assert reset_response.status_code == 200
    assert reset_response.json()['elder_id'] == 'elder-demo-1'

    dashboard_response = app_client.get('/api/family/dashboard/elder-demo-1')
    assert dashboard_response.status_code == 200
    dashboard = dashboard_response.json()
    effective_routine = dashboard['profile_summary']['today_profile']['effective_routine']
    assert [item['source'] for item in effective_routine[:3]] == ['long_term', 'long_term', 'long_term']
    assert dashboard['cognition_summary']['items'] == []
    assert dashboard['notices'] == []

    plans_response = app_client.get('/api/family/medication-plans/elder-demo-1')
    assert plans_response.status_code == 200
    assert plans_response.json()['items'] == []

    messages_response = app_client.get('/api/family/messages/elder-demo-1')
    assert messages_response.status_code == 200
    messages = messages_response.json()['items']
    assert not any('临时 demo 留言' in item['summary_text'] for item in messages)
    assert messages == []

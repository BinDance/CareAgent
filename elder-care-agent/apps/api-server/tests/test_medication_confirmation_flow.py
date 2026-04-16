from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from eldercare_api.deps import get_agent_runtime


def test_elder_medication_confirmation_acknowledges_and_marks_due_plans(app_client):
    runtime = app_client.app.dependency_overrides[get_agent_runtime]()
    runtime.llm._chat = None

    current_slot = datetime.now(timezone.utc).astimezone(ZoneInfo('Asia/Shanghai')).strftime('%H:%M')
    created_plan_ids: list[str] = []

    for medication_name in ['奥氮平片', '地西泮片']:
        response = app_client.post(
            '/api/family/medication-plans',
            json={
                'elder_id': 'elder-demo-1',
                'medication_name': medication_name,
                'dose': '5mg',
                'frequency': '晚一次',
                'meal_timing': '饭后',
                'time_slots': [current_slot],
            },
        )
        assert response.status_code == 200
        created_plan_ids.append(response.json()['id'])

    elder_response = app_client.post(
        '/api/elder/voice-input',
        json={'elder_id': 'elder-demo-1', 'transcript': '我两个药都吃好了'},
    )
    assert elder_response.status_code == 200

    elder_payload = elder_response.json()
    assert '药已经吃好了' in elder_payload['reply_text']
    assert elder_payload['delivered_notice_ids'] == []

    dashboard = app_client.get('/api/family/dashboard/elder-demo-1')
    assert dashboard.status_code == 200
    dashboard_payload = dashboard.json()

    taken_plan_ids = {
        item['plan_id']
        for item in dashboard_payload['medication_summary']['logs']
        if item['log_type'] == 'taken'
    }
    assert set(created_plan_ids).issubset(taken_plan_ids)
    assert any(card['title'] == '服药状态' and card['value'] == '已确认' for card in dashboard_payload['cards'])

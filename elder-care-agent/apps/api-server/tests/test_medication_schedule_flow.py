def test_after_meal_plan_uses_profile_lunch_time(app_client):
    response = app_client.post(
        '/api/family/medication-plans',
        json={
            'elder_id': 'elder-demo-1',
            'medication_name': '盐酸曲林片',
            'dose': '100mg',
            'frequency': '每日1次',
            'meal_timing': '饭后',
            'time_slots': [],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data['time_slots'] == ['12:20']


def test_evening_plan_uses_profile_sleep_time(app_client):
    response = app_client.post(
        '/api/family/medication-plans',
        json={
            'elder_id': 'elder-demo-1',
            'medication_name': '奥氮平片',
            'dose': '5mg',
            'frequency': '晚一次',
            'meal_timing': '',
            'time_slots': [],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data['time_slots'] == ['20:50']

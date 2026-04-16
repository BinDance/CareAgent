def test_prescription_multimodal_flow(app_client):
    raw_pdf_like = '阿司匹林 100mg 每日1次 饭后\n维生素D 1片 每日1次 早上'.encode('utf-8')
    response = app_client.post(
        '/api/family/upload-prescription',
        files={'file': ('rx.pdf', raw_pdf_like, 'application/pdf')},
        data={'elder_id': 'elder-demo-1'},
    )
    assert response.status_code == 200
    data = response.json()
    assert data['prescription_id']
    assert len(data['created_plans']) >= 1
    assert 'medications' in data['extraction']

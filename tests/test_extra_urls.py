def test_extra_url_on_draft(app, db, client, prepare_es, test_users, draft_record):
    resp = client.get('/draft/records/1/files/_test')

    assert resp.status_code == 200
    assert resp.json == {'status': 'ok'}

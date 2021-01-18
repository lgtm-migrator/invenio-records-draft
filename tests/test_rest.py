import json

from tests.helpers import remove_ts


def test_draft_create(app, db, client, prepare_es, test_users):
    resp = client.post('/draft/records/', data=json.dumps({'title': 'test'}), content_type='application/json')

    assert resp.status_code == 201
    resp = resp.json
    assert remove_ts(resp) == {
        "id": "1",
        "links": {
            "self": "http://localhost:5000/draft/records/1",
            'files': 'http://localhost:5000/draft/records/1/files/'
        },
        "metadata": {
            "$schema": "https://localhost:5000/schemas/sample/sample-v1.0.0.json",
            "control_number": "1",
            "oarepo:validity": {
                "errors": {
                    "marshmallow": [{
                        "field": "title",
                        "message": "Shorter than minimum length 5."
                    }]
                },
                "valid": False
            },
            'oarepo:draft': True,
            "title": "test"
        },
        "revision": 0
    }

    resp = client.get('/draft/records/')

    assert resp.status_code == 200
    resp = resp.json
    assert remove_ts(resp) == {
        'aggregations': {},
        'hits': {
            'hits': [
                {
                    'id': '1',
                    'links': {
                        'self': 'http://localhost:5000/draft/records/1',
                        'files': 'http://localhost:5000/draft/records/1/files/'
                    },
                    'metadata': {
                        '$schema': 'https://localhost:5000/schemas/sample/sample-v1.0.0.json',
                        'control_number': '1',
                        'oarepo:validity': {
                            'errors': {
                                'marshmallow': [
                                    {
                                        'field': 'title',
                                        'message': 'Shorter than minimum length 5.'
                                    }]},
                            'valid': False
                        },
                        'oarepo:draft': True,
                        'title': 'test'},
                    'revision': 0,
                }],
            'total': 1},
        'links': {'self': 'http://localhost:5000/draft/records/?size=10&page=1'}}

    print('before patch')
    resp = client.patch('/draft/records/1',
                        data=json.dumps([{'op': 'replace', 'path': '/title', 'value': 'longer test'}]),
                        content_type='application/json-patch+json')
    assert resp.status_code == 200

    resp = client.get('/draft/records/')

    assert resp.status_code == 200
    resp = resp.json
    assert remove_ts(resp) == {
        'aggregations': {},
        'hits': {
            'hits': [
                {
                    'id': '1',
                    'links': {
                        'self': 'http://localhost:5000/draft/records/1',
                        'files': 'http://localhost:5000/draft/records/1/files/'
                    },
                    'metadata': {
                        '$schema': 'https://localhost:5000/schemas/sample/sample-v1.0.0.json',
                        'control_number': '1',
                        'oarepo:validity': {
                            'valid': True
                        },
                        'oarepo:draft': True,
                        'title': 'longer test'
                    },
                    'revision': 1,
                }],
            'total': 1},
        'links': {'self': 'http://localhost:5000/draft/records/?size=10&page=1'}}

    resp = client.post('/draft/records/1/publish')
    assert resp.status_code == 401

    # login first user
    resp = client.post('/test/login/1')
    assert resp.status_code == 200

    # this user can publish the record ...
    resp = client.get('/draft/records/1')
    assert resp.status_code == 200
    resp = resp.json

    assert remove_ts(resp) == {
        'id': '1',
        'links': {
            'self': 'http://localhost:5000/draft/records/1',
            'publish': 'http://localhost:5000/draft/records/1/publish',
            'files': 'http://localhost:5000/draft/records/1/files/'
        },
        'metadata': {
            '$schema': 'https://localhost:5000/schemas/sample/sample-v1.0.0.json',
            'control_number': '1',
            'oarepo:validity': {
                'valid': True
            },
            'oarepo:draft': True,
            'title': 'longer test'
        },
        'revision': 1,
    }

    resp = client.post('/draft/records/1/publish')
    assert resp.status_code == 302
    print(resp.data)
    print(resp.headers)
    assert resp.headers['Location'] == 'http://localhost:5000/records/1'

    resp = resp.json
    assert resp == {
        "links": {
            "published": "http://localhost:5000/records/1"
        },
        "status": "ok"
    }

    resp = client.get('/draft/records/1')
    assert resp.status_code == 410

    resp = client.get('/records/1')
    assert resp.status_code == 200

    # edit the record - at first, no permissions
    resp = client.post('/test/logout')
    assert resp.status_code == 200

    resp = client.post('/records/1/edit')
    assert resp.status_code == 401

    # login first user
    resp = client.post('/test/login/1')
    assert resp.status_code == 200

    resp = client.post('/records/1/edit')
    assert resp.status_code == 302
    assert resp.headers['Location'] == 'http://localhost:5000/draft/records/1'

    resp = resp.json
    assert resp == {
        "links": {
            "draft": "http://localhost:5000/draft/records/1"
        }
    }

    # record still exists during edit
    resp = client.get('/records/1')
    assert resp.status_code == 200

    # patch it
    resp = client.patch('/draft/records/1',
                        data=json.dumps([{'op': 'replace', 'path': '/title', 'value': 'longer test edit'}]),
                        content_type='application/json-patch+json')
    assert resp.status_code == 200

    # and publish again
    resp = client.post('/draft/records/1/publish')
    assert resp.status_code == 302
    print(resp.data)
    print(resp.headers)
    assert resp.headers['Location'] == 'http://localhost:5000/records/1'

    resp = resp.json
    assert resp == {
        "links": {
            "published": "http://localhost:5000/records/1"
        },
        "status": "ok"
    }

    # unpublish the record - at first, no permissions
    resp = client.post('/test/logout')
    assert resp.status_code == 200

    resp = client.post('/records/1/unpublish')
    assert resp.status_code == 401

    # login first user
    resp = client.post('/test/login/1')
    assert resp.status_code == 200

    resp = client.post('/records/1/unpublish')
    assert resp.status_code == 302
    assert resp.headers['Location'] == 'http://localhost:5000/draft/records/1'

    resp = resp.json
    assert resp == {
        "links": {
            "draft": "http://localhost:5000/draft/records/1"
        },
        "status": "ok"
    }

    # record does not exist during edit
    resp = client.get('/records/1')
    assert resp.status_code == 410

    # patch it
    resp = client.patch('/draft/records/1',
                        data=json.dumps([{'op': 'replace', 'path': '/title', 'value': 'longer test edit'}]),
                        content_type='application/json-patch+json')
    assert resp.status_code == 200

    # and publish again
    resp = client.post('/draft/records/1/publish')
    assert resp.status_code == 302
    print(resp.data)
    print(resp.headers)
    assert resp.headers['Location'] == 'http://localhost:5000/records/1'

    resp = resp.json
    assert resp == {
        "links": {
            "published": "http://localhost:5000/records/1"
        },
        "status": "ok"
    }

import json


def test_draft_create(app, db, client, prepare_es):
    resp = client.post('/drafts/records/', data=json.dumps({'title': 'test'}), content_type='application/json')

    assert resp.status_code == 201
    resp = resp.json
    resp.pop('created')
    resp.pop('updated')
    assert resp == {
        "id": "1",
        "links": {
            "self": "http://localhost:5000/drafts/records/1"
        },
        "metadata": {
            "$schema": "https://localhost:5000/schemas/sample/sample-v1.0.0.json",
            "control_number": "1",
            "invenio_draft_validation": {
                "errors": {
                    "marshmallow": [{
                        "field": "title",
                        "message": "Shorter than minimum length 5."
                    }]
                },
                "valid": False
            },
            "title": "test"
        },
        "revision": 0
    }

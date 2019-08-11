from invenio_jsonschemas import current_jsonschemas
from invenio_search import current_search_client


def test_draft_validations_title_missing(app, db, schemas, mappings, prepare_es,
                                         client, draft_records_url):
    resp = client.post(
        draft_records_url,
        json={
            '$schema': current_jsonschemas.path_to_url('draft/records/record-v1.0.0.json')
        })
    assert resp.status_code == 201
    current_search_client.indices.flush()

    resp = client.get(draft_records_url)
    assert resp.status_code == 200
    record = resp.json['hits']['hits'][0]
    print(record)
    assert record['metadata']['invenio_draft_validation'] == {
        'valid': False,
        'errors': {
            'marshmallow': [
                {
                    'field': 'title',
                    'message': 'Missing data for required field.'
                }
            ]
        }
    }


def test_draft_validations_title_long(app, db, schemas, mappings, prepare_es,
                                      client, draft_records_url):
    resp = client.post(
        draft_records_url,
        json={
            '$schema': current_jsonschemas.path_to_url('draft/records/record-v1.0.0.json'),
            'title': 'too long title' * 100
        })
    assert resp.status_code == 201
    current_search_client.indices.flush()

    resp = client.get(draft_records_url)
    assert resp.status_code == 200
    record = resp.json['hits']['hits'][0]
    print(record)
    assert record['metadata']['invenio_draft_validation'] == {
        'valid': False,
        'errors': {
            'marshmallow': [
                {
                    'field': 'title',
                    'message': 'Length must be between 1 and 10.'
                }
            ]
        }
    }


def test_draft_validations_title_short(app, db, schemas, mappings, prepare_es,
                                       client, draft_records_url):
    resp = client.post(
        draft_records_url,
        json={
            '$schema': current_jsonschemas.path_to_url('draft/records/record-v1.0.0.json'),
            'title': '1'
        })
    assert resp.status_code == 201
    current_search_client.indices.flush()

    resp = client.get(draft_records_url)
    assert resp.status_code == 200
    record = resp.json['hits']['hits'][0]
    print(record)
    assert record['metadata']['invenio_draft_validation'] == {
        'valid': False,
        'errors': {
            'jsonschema': [
                {
                    'field': 'title',
                    'message': "'1' is too short"
                }
            ]
        }
    }

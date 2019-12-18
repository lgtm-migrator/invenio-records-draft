import re
import uuid

from invenio_indexer.api import RecordIndexer
from invenio_jsonschemas import current_jsonschemas
from invenio_pidstore.minters import recid_minter
from invenio_pidstore.models import PersistentIdentifier, PIDStatus
from invenio_records import Record
from invenio_search import current_search_client

from invenio_records_draft.proxies import current_drafts
from tests.helpers import header_links, login


def stringify_functions(x):
    if isinstance(x, list):
        for yy in x:
            stringify_functions(yy)
        return x
    if not isinstance(x, dict):
        return x
    for k, v in list(x.items()):
        if callable(v):
            x[k] = re.sub(r' at 0x[0-9a-fA-F]*>', r'>', str(v))
        else:
            stringify_functions(v)
    return x


def test_endpoint_config(app, schemas):
    draft_endpoint = current_drafts.draft_endpoints['records']
    published_endpoint = current_drafts.published_endpoints['records']

    assert stringify_functions(draft_endpoint) == {
        'create_permission_factory_imp': '<function allow_all>',
        'default_endpoint_prefix': True,
        'delete_permission_factory_imp': '<function allow_all>',
        'item_route': 'drafts/records/<pid(drecid,'
                      'record_class="sample.records.config:DraftRecord"):pid_value>',
        'list_permission_factory_imp': '<function allow_all>',
        'list_route': 'drafts/records/',
        'pid_type': 'drecid',
        'pid_fetcher': 'drecid',
        'pid_minter': 'drecid',
        'read_permission_factory_imp': '<function allow_all>',
        'record_class': "<class 'sample.records.config.DraftRecord'>",
        'record_loaders': {
            'application/json': '<function marshmallow_loader.<locals>.json_loader>',
            'application/json-patch+json': '<function json_patch_loader>'
        },
        'record_serializers': {
            'application/json': '<function record_responsify.<locals>.view>'
        },
        'search_index': 'draft-records-record-v1.0.0',
        'search_serializers': {
            'application/json': '<function search_responsify.<locals>.view>'
        },
        'default_media_type': 'application/json',
        'update_permission_factory_imp': '<function allow_all>',
        'links_factory_imp':
            '<invenio_records_draft.endpoints.DraftLinksFactory object>',
        'endpoint': 'draft_records',
        'publish_permission_factory': '<function allow_authenticated>',
        'unpublish_permission_factory': '<function allow_authenticated>',
        'edit_permission_factory': '<function allow_authenticated>',
    }

    assert stringify_functions(published_endpoint) == {
        'create_permission_factory_imp': '<function deny_all>',
        'default_endpoint_prefix': True,
        'delete_permission_factory_imp': '<function allow_all>',
        'item_route': '/records/<pid(recid,'
                      'record_class="sample.records.config:PublishedRecord"):pid_value>',
        'list_permission_factory_imp': '<function allow_all>',
        'list_route': '/records/',
        'pid_type': 'recid',
        'pid_fetcher': 'recid',
        'pid_minter': 'recid',
        'read_permission_factory_imp': '<function allow_all>',
        'record_class': "<class 'sample.records.config.PublishedRecord'>",
        'record_serializers': {
            'application/json': '<function record_responsify.<locals>.view>'
        },
        'search_index': 'records-record-v1.0.0',
        'search_serializers': {
            'application/json': '<function search_responsify.<locals>.view>'
        },
        'default_media_type': 'application/json',
        'links_factory_imp':
            '<invenio_records_draft.endpoints.PublishedLinksFactory object>',
        'update_permission_factory_imp': '<function deny_all>',
        'endpoint': 'published_records',
        'publish_permission_factory': '<function allow_authenticated>',
        'unpublish_permission_factory': '<function allow_authenticated>',
        'edit_permission_factory': '<function allow_authenticated>',
    }


def test_production_endpoint(app, db, schemas, mappings, prepare_es,
                             client, published_records_url, test_users):
    resp = client.get(published_records_url)
    assert resp.status_code == 200
    assert (app.config['SERVER_NAME'] + published_records_url) in header_links(resp)['self']

    login(client, test_users.u1)

    resp = client.post(published_records_url, json={'title': 'abc'})
    assert resp.status_code == 403
    assert resp.json == {
        'message': "You don't have the permission to access the requested resource. "
                   'It is either read-protected or not readable by the server.',
        'status': 403
    }

    # let's create a record
    record_uuid = uuid.uuid4()
    data = {
        'title': 'blah',
        '$schema': current_jsonschemas.path_to_url('records/record-v1.0.0.json')
    }
    recid_minter(record_uuid, data)
    rec = Record.create(data, id_=record_uuid)
    RecordIndexer().index(rec)
    current_search_client.indices.flush()

    resp = client.get(published_records_url)
    assert resp.status_code == 200
    assert len(resp.json['hits']['hits']) == 1
    record_url = resp.json['hits']['hits'][0]['links']['self']
    assert record_url == 'http://localhost:5000/records/1'

    # try to update the record
    resp = client.put(record_url, json={'title': 'abc'})
    assert resp.status_code == 403
    assert resp.json == {
        'message': "You don't have the permission to access the requested resource. "
                   'It is either read-protected or not readable by the server.',
        'status': 403
    }

    # try to patch the record
    patch_ops = [{'op': 'replace', 'path': '/title', 'value': 'abc'}]
    resp = client.patch(record_url, json=patch_ops, headers={
        'Content-Type': 'application/json-patch+json'
    })
    assert resp.status_code == 403
    assert resp.json == {
        'message': "You don't have the permission to access the requested resource. "
                   'It is either read-protected or not readable by the server.',
        'status': 403
    }

    # deleting the record should pass as the default permission is allow_all
    resp = client.delete(record_url)
    assert resp.status_code == 204

    resp = client.get(record_url)
    assert resp.status_code == 410  # gone


def test_draft_endpoint_list(app, db, schemas, mappings, prepare_es,
                             client, draft_records_url):
    resp = client.get(draft_records_url)
    assert resp.status_code == 200
    server_name = app.config['SERVER_NAME']
    assert (server_name + draft_records_url) in header_links(resp)['self']

    # let's create a record
    record_uuid = uuid.uuid4()
    data = {
        # no title for draft record'title': 'blah',
        '$schema': current_jsonschemas.path_to_url('draft/records/record-v1.0.0.json')
    }
    recid_minter(record_uuid, data)
    rec = Record.create(data, id_=record_uuid)
    RecordIndexer().index(rec)
    current_search_client.indices.flush()

    resp = client.get(draft_records_url)
    assert resp.status_code == 200
    assert len(resp.json['hits']['hits']) == 1
    first_hit = resp.json['hits']['hits'][0]
    assert first_hit['links']['self'] == f'http://{server_name}{draft_records_url}1'


def test_draft_endpoint_ops(app, db, schemas, mappings, prepare_es,
                            client, draft_records_url):
    resp = client.post(
        draft_records_url,
        json={
            '$schema': current_jsonschemas.path_to_url('draft/records/record-v1.0.0.json')
        })
    assert resp.status_code == 201
    record_link = resp.json['links']['self']
    current_search_client.indices.flush()

    resp = client.get(draft_records_url)
    assert resp.status_code == 200
    assert len(resp.json['hits']['hits']) == 1
    first_hit = resp.json['hits']['hits'][0]
    record_url = first_hit['links']['self']
    assert record_url == record_link

    resp = client.get(record_link)
    assert resp.status_code == 200
    assert resp.json['metadata'] in (
        {
            "$schema": "https://localhost:5000/schemas/draft/records/record-v1.0.0.json",
            "id": "1",
            'invenio_draft_validation': {
                'errors': {
                    'marshmallow': [
                        {'field': 'title',
                         'message': 'Missing data for required field.'
                         }
                    ]
                },
                'valid': False
            }
        },
        {
            "$schema": "https://localhost:5000/schemas/draft/records/record-v1.0.0.json",
            "id": "1",
            'invenio_draft_validation': {
                'errors': {
                    'marshmallow': {
                        'title': ['Missing data for required field.']
                    }
                },
                'valid': False
            }
        },
    )

    # try to update the record
    resp = client.put(record_url, json={
        "$schema": "https://localhost:5000/schemas/draft/records/record-v1.0.0.json",
        'title': 'def'})
    assert resp.status_code == 200
    current_search_client.indices.flush()

    resp = client.get(record_url)
    assert resp.status_code == 200
    assert resp.json['metadata']['title'] == 'def'

    # try to update the record with invalid data that should not pass even draft
    resp = client.put(record_url, json={
        "$schema": "https://localhost:5000/schemas/draft/records/record-v1.0.0.json",
        'title': 'def', 'invalid': 'blah'})
    assert resp.status_code == 400
    assert resp.json in (
        {
            'errors': [{'field': 'invalid', 'message': 'Unknown field name invalid'}],
            'message': 'Validation error.',
            'status': 400
        },
        {
            'errors': [{'field': 'invalid', 'message': 'Unknown field.', 'parents': []}],
            'message': 'Validation error.',
            'status': 400
        },
    )

    # try to patch the record
    patch_ops = [{'op': 'replace', 'path': '/title', 'value': 'abc'}]
    resp = client.patch(record_url, json=patch_ops, headers={
        'Content-Type': 'application/json-patch+json'
    })
    assert resp.status_code == 200
    current_search_client.indices.flush()

    resp = client.get(record_url)
    assert resp.status_code == 200
    assert resp.json['metadata']['title'] == 'abc'

    # try to patch the record with invalid data
    patch_ops = [{'op': 'add', 'path': '/invalid', 'value': 'abc'}]
    resp = client.patch(record_url, json=patch_ops, headers={
        'Content-Type': 'application/json-patch+json'
    })
    assert resp.status_code == 400
    assert resp.json == {
        'message': "Validation error: Additional properties "
                   "are not allowed ('invalid' was unexpected).",
        'status': 400
    }

    # deleting the record should pass as the default permission is allow_all
    resp = client.delete(record_url)
    assert resp.status_code == 204
    current_search_client.indices.flush()

    resp = client.get(record_url)
    assert resp.status_code == 410  # gone


def test_published_record_extra_urls(app, db, schemas, mappings, prepare_es,
                                     client, published_records_url, test_users,
                                     published_record):
    resp = client.get('http://localhost:5000/records/1')
    assert resp.status_code == 200

    links_section = resp.json['links']
    # not logged user should not see neither publish nor edit
    assert links_section == {
        'self': 'http://localhost:5000/records/1',
    }

    login(client, test_users.u1)

    resp = client.get('http://localhost:5000/records/1')
    assert resp.status_code == 200

    links_section = resp.json['links']
    assert links_section == {
        'edit': 'http://localhost:5000/records/1/edit',
        'self': 'http://localhost:5000/records/1',
        'unpublish': 'http://localhost:5000/records/1/unpublish'
    }


def test_unpublish(app, db, schemas, mappings, prepare_es,
                   client, published_records_url, test_users,
                   published_record):
    login(client, test_users.u1)

    resp = client.get('http://localhost:5000/records/1')
    assert resp.status_code == 200

    unpublish_link = resp.json['links']['unpublish']

    resp = client.post(unpublish_link)
    assert resp.status_code == 302
    assert resp.headers['Location'] == 'http://localhost:5000/drafts/records/1'

    resp = client.get('http://localhost:5000/drafts/records/1')
    assert resp.status_code == 200

    resp = client.get('http://localhost:5000/records/1')
    assert resp.status_code == 410  # gone

    published_pid = PersistentIdentifier.get(pid_type='recid', pid_value='1')
    draft_pid = PersistentIdentifier.get(pid_type='drecid', pid_value='1')
    assert published_pid.object_uuid != draft_pid.object_uuid

    assert published_pid.status == PIDStatus.DELETED

    # elasticsearch
    resp = client.get('http://localhost:5000/records/')
    assert resp.status_code == 200
    assert len(resp.json['hits']['hits']) == 0

    resp = client.get('http://localhost:5000/drafts/records/')
    assert resp.status_code == 200

    assert len(resp.json['hits']['hits']) == 1
    record_url = resp.json['hits']['hits'][0]['links']['self']
    assert record_url == 'http://localhost:5000/drafts/records/1'


def test_edit(app, db, schemas, mappings, prepare_es,
              client, published_records_url, test_users,
              published_record):
    login(client, test_users.u1)

    resp = client.get('http://localhost:5000/records/1')
    assert resp.status_code == 200

    edit_link = resp.json['links']['edit']

    resp = client.post(edit_link)
    assert resp.status_code == 302
    assert resp.headers['Location'] == 'http://localhost:5000/drafts/records/1'

    resp = client.get('http://localhost:5000/drafts/records/1')
    assert resp.status_code == 200

    resp = client.get('http://localhost:5000/records/1')
    assert resp.status_code == 200  # record stays

    published_pid = PersistentIdentifier.get(pid_type='recid', pid_value='1')
    draft_pid = PersistentIdentifier.get(pid_type='drecid', pid_value='1')
    assert published_pid.object_uuid != draft_pid.object_uuid

    # elasticsearch
    resp = client.get('http://localhost:5000/records/')
    assert resp.status_code == 200
    assert len(resp.json['hits']['hits']) == 1
    record_url = resp.json['hits']['hits'][0]['links']['self']
    assert record_url == 'http://localhost:5000/records/1'

    resp = client.get('http://localhost:5000/drafts/records/')
    assert resp.status_code == 200

    assert len(resp.json['hits']['hits']) == 1
    record_url = resp.json['hits']['hits'][0]['links']['self']
    assert record_url == 'http://localhost:5000/drafts/records/1'


def test_publish(app, db, schemas, mappings, prepare_es,
                 client, published_records_url, test_users,
                 draft_record):
    login(client, test_users.u1)

    resp = client.get('http://localhost:5000/drafts/records/1')
    assert resp.status_code == 200

    publish_link = resp.json['links']['publish']

    resp = client.post(publish_link)
    assert resp.status_code == 302
    assert resp.headers['Location'] == 'http://localhost:5000/records/1'

    resp = client.get('http://localhost:5000/records/1')
    assert resp.status_code == 200

    resp = client.get('http://localhost:5000/drafts/records/1')
    assert resp.status_code == 410  # gone

    published_pid = PersistentIdentifier.get(pid_type='recid', pid_value='1')
    draft_pid = PersistentIdentifier.get(pid_type='drecid', pid_value='1')
    assert published_pid.object_uuid != draft_pid.object_uuid

    assert draft_pid.status == PIDStatus.DELETED

    # elasticsearch
    resp = client.get('http://localhost:5000/drafts/records/')
    assert resp.status_code == 200
    assert len(resp.json['hits']['hits']) == 0

    resp = client.get('http://localhost:5000/records/')
    assert resp.status_code == 200

    assert len(resp.json['hits']['hits']) == 1
    record_url = resp.json['hits']['hits'][0]['links']['self']
    assert record_url == 'http://localhost:5000/records/1'

import re
import uuid

import pytest
import requests
from invenio_indexer.api import RecordIndexer
from invenio_jsonschemas import current_jsonschemas
from invenio_pidstore.minters import recid_minter
from invenio_records import Record
from invenio_search import current_search_client

from invenio_records_draft.endpoints import draft_enabled_endpoint
from sample.records.marshmallow import RecordSchemaV1, MetadataSchemaV1
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


def test_endpoint_config(app):
    assert stringify_functions(draft_enabled_endpoint(
        url_prefix='records',
        record_marshmallow=RecordSchemaV1,
        metadata_marshmallow=MetadataSchemaV1,
        search_index='records')) == \
           {
               'draft_records': {
                   'create_permission_factory_imp': '<function allow_all>',
                   'default_endpoint_prefix': True,
                   'delete_permission_factory_imp': '<function allow_all>',
                   'item_route': 'drafts/records/<pid(draft_recid,'
                                 'record_class="invenio_records.api:Record"):pid_value>',
                   'list_permission_factory_imp': '<function allow_all>',
                   'list_route': 'drafts/records/',
                   'pid_type': 'draft_recid',
                   'pid_fetcher': 'recid',
                   'pid_minter': 'recid',
                   'read_permission_factory_imp': '<function allow_all>',
                   'record_class': "<class 'invenio_records.api.Record'>",
                   'record_loaders': {
                       'application/json': '<function marshmallow_loader.<locals>.json_loader>'
                   },
                   'record_serializers': {
                       'application/json': '<function record_responsify.<locals>.view>'
                   },
                   'search_index': 'draft-records',
                   'search_serializers': {
                       'application/json': '<function search_responsify.<locals>.view>'
                   },
                   'default_media_type': 'application/json',
                   'update_permission_factory_imp': '<function allow_all>',
                   'links_factory_imp': '<function make_links_factory.'
                                        '<locals>.default_links_factory>',
               },
               'published_records': {
                   'create_permission_factory_imp': '<function deny_all>',
                   'default_endpoint_prefix': True,
                   'delete_permission_factory_imp': '<function deny_all>',
                   'item_route': '/records/<pid(recid,'
                                 'record_class="invenio_records.api:Record"):pid_value>',
                   'list_permission_factory_imp': '<function allow_all>',
                   'list_route': '/records/',
                   'pid_type': 'recid',
                   'pid_fetcher': 'recid',
                   'pid_minter': 'recid',
                   'read_permission_factory_imp': '<function allow_all>',
                   'record_class': "<class 'invenio_records.api.Record'>",
                   'record_loaders': {
                       'application/json': '<function marshmallow_loader.<locals>.json_loader>'
                   },
                   'record_serializers': {
                       'application/json': '<function record_responsify.<locals>.view>'
                   },
                   'search_index': 'records',
                   'search_serializers': {
                       'application/json': '<function search_responsify.<locals>.view>'
                   },
                   'default_media_type': 'application/json',
                   'update_permission_factory_imp': '<function deny_all>'
               }
           }


def test_production_endpoint_list(app, db, schemas, mappings, prepare_es,
                                  client, published_records_url, test_users):
    resp = client.get(published_records_url)
    assert resp.status_code == 200
    assert (app.config['SERVER_NAME'] + published_records_url) in header_links(resp)['self']

    login(client, test_users.u1)

    resp = client.post(published_records_url, data={'title': 'abc'})
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
    assert resp.json['hits']['hits'][0]['links']['self'] == 'http://localhost:5000/records/1'


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

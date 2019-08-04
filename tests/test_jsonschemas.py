import os

from invenio_jsonschemas import InvenioJSONSchemas, current_jsonschemas

from invenio_records_draft.cli import make_schemas


def test_instance_path(app):
    assert app.instance_path.endswith('/test-instance')
    assert os.path.exists(app.instance_path)


def test_schemas_in_config(app):
    assert app.config['INVENIO_RECORD_DRAFT_SCHEMAS']
    assert len(set(x['published_schema'] for x in app.config['INVENIO_RECORD_DRAFT_SCHEMAS'])) == 1


def test_make_schemas(app):
    runner = app.test_cli_runner()
    result = runner.invoke(make_schemas)
    print(result.output)
    assert result.exit_code == 0
    for schema in app.config['INVENIO_RECORD_DRAFT_SCHEMAS']:
        draft_path = os.path.join(app.instance_path, 'draft_schemas', schema['draft_schema'])
        assert f'Created schema {draft_path}' in result.output


def test_schemas_deployed(app, schemas):
    for schema in app.config['INVENIO_RECORD_DRAFT_SCHEMAS']:
        assert schema['draft_schema'] in current_jsonschemas.list_schemas()


def test_schemas_available(app, schemas, client):
    for schema in app.config['INVENIO_RECORD_DRAFT_SCHEMAS']:
        draft = schema['draft_schema']
        result = client.get(f'/schemas/{draft}')
        assert result.status_code == 200
        assert result.json['$schema'] == 'http://json-schema.org/draft-04/schema#'
        assert result.json['title'] == 'My site v1.0.0'
        assert b'required' not in result.data

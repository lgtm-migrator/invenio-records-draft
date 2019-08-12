import os

from invenio_jsonschemas import current_jsonschemas

from invenio_records_draft.proxies import current_drafts


def test_referenced_schema(app):
    schema_dir = os.path.join(os.path.dirname(__file__), 'schemas')
    current_jsonschemas.register_schema(
        schema_dir, 'test/v.json'
    )
    current_jsonschemas.register_schema(
        schema_dir, 'a.json'
    )
    current_jsonschemas.register_schema(
        schema_dir, 'b.json'
    )
    schema_data = current_drafts.get_schema('test/v.json')

    assert schema_data == {
        'type': 'object',
        'properties': {
            'aa': {
                'type': 'object',
                'required': ['b'],
                'properties': {
                    'b': {
                        'type': 'object',
                        'required': ['c'],
                        'properties': {
                            'c': {
                                'type': 'string'
                            }
                        }
                    }
                }
            }
        },
        'required': ['a']
    }

import json

from invenio_search import current_search


def test_draft_mapping(app):
    assert list(sorted(current_search.mappings.keys())) == [
        'draft-sample-sample-v1.0.0', 'sample-sample-v1.0.0'
    ]

    assert json.loads(open(current_search.mappings['draft-sample-sample-v1.0.0']).read()) == {
        'mappings': {
            'dynamic': False,
            "dynamic_templates": [
                {
                    "validation_jsonschema": {
                        "path_match": "invenio_draft_validation.errors.jsonschema.*",
                        "mapping": {
                            "type": "keyword",
                        }
                    },
                },
                {
                    "validation_marshmallow": {
                        "path_match": "invenio_draft_validation.errors.marshmallow.*",
                        "mapping": {
                            "type": "keyword",
                        }
                    }
                }
            ],
            'properties': {
                'invenio_draft_validation': {
                    'properties': {
                        'errors': {
                            'properties': {
                                'jsonschema': {
                                    'type': 'object',
                                    'dynamic': True
                                },
                                'marshmallow': {
                                    'type': 'object',
                                    'dynamic': True
                                },
                                'other': {
                                    'type': 'text'
                                }
                            },
                            'type': 'object'
                        },
                        'valid': {
                            'type': 'boolean'
                        }
                    },
                    'type': 'object'
                },
                'title': {
                    'type': 'text'
                }
            }
        },
        'settings': {
            'index.mapping.ignore_malformed': True
        }
    }

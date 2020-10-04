import json

from invenio_search import current_search


def test_draft_mapping(app):
    assert list(sorted(current_search.mappings.keys())) == [
        'draft-sample-sample-v1.0.0', 'sample-sample-v1.0.0'
    ]

    assert json.loads(open(current_search.mappings['draft-sample-sample-v1.0.0']).read()) == {
        'mappings': {
            'dynamic': False,
            'properties': {
                'oarepo:validity': {
                    'properties': {
                        "errors": {
                            "type": "object",
                            "properties": {
                                "marshmallow": {
                                    "type": "object",
                                    "properties": {
                                        "field": {
                                            "type": "keyword",
                                            "copy_to": "oarepo:validity.errors.all.field"
                                        },
                                        "message": {
                                            "type": "text",
                                            "copy_to": "oarepo:validity.errors.all.message",
                                            "fields": {
                                                "raw": {
                                                    "type": "keyword"
                                                }
                                            }
                                        }
                                    }
                                },
                                "jsonschema": {
                                    "type": "object",
                                    "properties": {
                                        "field": {
                                            "type": "keyword",
                                            "copy_to": "oarepo:validity.errors.all.field"
                                        },
                                        "message": {
                                            "type": "text",
                                            "copy_to": "oarepo:validity.errors.all.message",
                                            "fields": {
                                                "raw": {
                                                    "type": "keyword"
                                                }
                                            }
                                        }
                                    }
                                },
                                "other": {
                                    "type": "text",
                                    "copy_to": "oarepo:validity.errors.all.message",
                                },
                                'all': {
                                    'properties': {
                                        'field': {
                                            'type': 'keyword'
                                        },
                                        'message': {
                                            'fields': {
                                                'raw': {
                                                    'type': 'keyword'
                                                }
                                            },
                                            'type': 'text'
                                        }
                                    },
                                    'type': 'object'
                                },
                            }
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

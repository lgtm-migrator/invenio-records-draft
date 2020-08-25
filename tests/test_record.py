from tests.conftest import SampleDraftRecord


def test_valid_record(app):
    rec = SampleDraftRecord({'title': 'longer'})
    rec.validate()
    assert dict(rec) == {
        '$schema': 'https://localhost:5000/schemas/sample/sample-v1.0.0.json',
        'title': 'longer',
        'invenio_draft_validation': {
            'valid': True
        }
    }


def test_invalid_schema(app):
    rec = SampleDraftRecord({'title': 'longer', 'extra': False})
    rec.validate()
    assert dict(rec) == {
        '$schema': 'https://localhost:5000/schemas/sample/sample-v1.0.0.json',
        'title': 'longer',
        'extra': False,
        'invenio_draft_validation': {
            'valid': False,
            'errors': {
                'jsonschema':
                    {
                        '': [
                            'Additional properties are not allowed (\'extra\' was unexpected)'
                        ]
                    }
            }
        }
    }


def test_invalid_marshmallow(app):
    rec = SampleDraftRecord({'title': 'abc'})
    rec.validate()
    assert dict(rec) == {
        '$schema': 'https://localhost:5000/schemas/sample/sample-v1.0.0.json',
        'title': 'abc',
        'invenio_draft_validation': {
            'valid': False,
            'errors': {
                'marshmallow': {
                    'title': [
                        'Shorter than minimum length 5.'
                    ]
                }
            }
        }
    }

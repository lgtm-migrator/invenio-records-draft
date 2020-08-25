from flask import current_app
from invenio_indexer.utils import schema_to_index
from invenio_records_rest.loaders.marshmallow import MarshmallowErrors
from invenio_search import current_search
from jsonschema import ValidationError as SchemaValidationError
from marshmallow.exceptions import ValidationError as MarshmallowValidationError

from oarepo_records_draft.proxies import current_drafts


class DraftRecordMixin:

    def validate(self, **kwargs):
        try:
            ret = super().validate(**kwargs)
            self['invenio_draft_validation'] = {
                'valid': True
            }
            return ret
        except MarshmallowErrors as e:
            self.save_marshmallow_error(e)
        except SchemaValidationError as e:
            self.save_schema_error(e)
        except Exception as e:
            self.save_generic_error(e)

    def save_marshmallow_error(self, err: MarshmallowErrors):
        errors = {}
        for e in err.errors:
            if e['parents']:
                errors.setdefault('.'.join(e['parents']) + '.' + e['field'], []).append(e['message'])
            else:
                errors.setdefault(e['field'], []).append(e['message'])

        self['invenio_draft_validation'] = {
            'valid': False,
            'errors': {
                'marshmallow': errors
            }
        }

    def save_schema_error(self, err: SchemaValidationError):
        self['invenio_draft_validation'] = {
            'valid': False,
            'errors': {
                'jsonschema': {
                    '.'.join(err.path): [
                        err.message
                    ]
                }
            }
        }

    def save_generic_error(self, err):
        self['invenio_draft_validation'] = {
            'valid': False,
            'errors': {
                'other': str(err)
            }
        }


def record_to_index(record):
    """Get index/doc_type given a record.

    It tries to extract from `record['$schema']` the index and doc_type.
    If it fails, return the default values.

    :param record: The record object.
    :returns: Tuple (index, doc_type).
    """
    index_names = current_search.mappings.keys()
    schema = record.get('$schema', '')
    if isinstance(schema, dict):
        schema = schema.get('$ref', '')

    index = schema_to_index(schema, index_names=index_names)[0]
    if 'invenio_draft_validation' in record:
        index = current_drafts.draft_for_index(index)

    return index, '_doc'

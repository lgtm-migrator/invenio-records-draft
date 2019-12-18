import logging

from invenio_jsonschemas import current_jsonschemas
from invenio_pidstore.fetchers import FetchedPID
from invenio_pidstore.models import PersistentIdentifier
from invenio_records import Record
from invenio_records_rest.loaders.marshmallow import MarshmallowErrors
from marshmallow.exceptions import ValidationError as MarshmallowValidationError
from invenio_records_rest.utils import obj_or_import_string
from jsonschema import ValidationError
from marshmallow import __version_info__ as marshmallow_version

logger = logging.getLogger('invenio-records-draft')


class InvalidRecordException(Exception):
    def __init__(self, message, errors):
        super().__init__(message)
        self.errors = errors

    def __str__(self):
        return '{0}: {1}'.format(super().__str__(), str(self.errors))


class MarshmallowValidator:

    def __init__(self,
                 marshmallow_schema_class,
                 published_record_schema,
                 published_record_class=Record):

        self.marshmallow_schema_class = marshmallow_schema_class
        self.published_record_schema = published_record_schema
        self.published_record_class = published_record_class

    def validate(self, data, pid):
        if isinstance(self.marshmallow_schema_class, str):
            self.marshmallow_schema_class = obj_or_import_string(self.marshmallow_schema_class)
        if isinstance(self.published_record_class, str):
            self.published_record_class = obj_or_import_string(self.published_record_class)

        context = {
            'pid': pid
        }

        marshmallow_instance = self.marshmallow_schema_class(context=context)
        result = marshmallow_instance.load(data)

        if marshmallow_version[0] < 3:
            if result.errors:
                raise MarshmallowErrors(result.errors)

            data = result.data
        else:
            data = result

        data['$schema'] = (
                current_jsonschemas.path_to_url(self.published_record_schema) or
                self.published_record_schema
        )
        data = self.published_record_class(data)
        data.validate()


class DraftEnabledRecordMixin:

    def validate(self, *args, **kwargs):
        if hasattr(self, 'draft_validator'):
            try:
                if self.model:
                    pid = PersistentIdentifier.query.filter_by(
                        object_type='rec', object_uuid=self.model.id).one_or_none()
                else:
                    pid = FetchedPID(pid_value='', provider=None, pid_type=None)
                data = dict(self)
                data.pop('invenio_draft_validation', None)
                self.draft_validator.validate(data, pid)
            except MarshmallowErrors as e:
                self['invenio_draft_validation'] = {
                    'valid': False,
                    'errors': {
                        'marshmallow': e.errors
                    }
                }
            except MarshmallowValidationError as e:
                self['invenio_draft_validation'] = {
                    'valid': False,
                    'errors': {
                        'marshmallow': e.messages
                    }
                }
            except ValidationError as e:
                self['invenio_draft_validation'] = {
                    'valid': False,
                    'errors': {
                        'jsonschema': [
                            {
                                'field': '.'.join(e.path),
                                'message': e.message
                            }
                        ]
                    }
                }
            except Exception as e:
                import traceback
                traceback.print_exc()
                self['invenio_draft_validation'] = {
                    'valid': False,
                    'errors': {
                        'other': str(e)
                    }
                }
            else:
                self['invenio_draft_validation'] = {
                    'valid': True
                }
        return super().validate(*args, **kwargs)

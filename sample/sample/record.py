from oarepo_validate import SchemaKeepingRecordMixin, MarshmallowValidatedRecordMixin
from sample.marshmallow import SampleSchemaV1

from oarepo_records_draft.record import DraftRecordMixin
from .constants import SAMPLE_ALLOWED_SCHEMAS, SAMPLE_PREFERRED_SCHEMA

try:
    # try to use files enabled record
    from invenio_records_files.api import Record
except ImportError:
    # and fall back to normal record
    from invenio_records.api import Record


class SampleRecord(SchemaKeepingRecordMixin,
                   MarshmallowValidatedRecordMixin,
                   Record):
    ALLOWED_SCHEMAS = SAMPLE_ALLOWED_SCHEMAS
    PREFERRED_SCHEMA = SAMPLE_PREFERRED_SCHEMA
    MARSHMALLOW_SCHEMA = SampleSchemaV1



class SampleDraftRecord(DraftRecordMixin, SampleRecord):
    pass

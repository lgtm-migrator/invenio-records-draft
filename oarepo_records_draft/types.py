from collections import namedtuple
from functools import lru_cache
from typing import List, Dict, Iterator

from invenio_base.utils import obj_or_import_string


class RecordEndpointConfiguration:
    """
    Extra information about record rest endpoint
    """

    def __init__(self,
                 published: bool, rest_name: str,
                 rest: Dict, extra: Dict,
                 paired_endpoint: 'RecordEndpointConfiguration' = None):
        """
        A record endpoint

        :param published:   true if the endpoint belongs to a published record, false if it is a draft
        :param rest_name:   key in the RECORD_REST_ENDPOINTS
        :param pid_type:    pid type
        :param rest:        configuration in RECORD_REST_ENDPOINTS
        :param extra:       any extra configuration
        :param paired_endpoint:  reference to the paired endpoint - draft if this one is published and vice versa
        """
        self.published = published
        self.rest_name = rest_name
        self.pid_type = rest['pid_type']
        self.rest = rest
        self.extra = extra
        self.paired_endpoint = paired_endpoint
        self.schema_indices = {}

    @property
    def record_class(self):
        return self.resolve('record_class')

    @lru_cache(maxsize=32)
    def resolve(self, name):
        clz = self.extra.get(name) or self.rest.get(name)
        if not clz:
            return None
        return obj_or_import_string(clz)

    def get_index(self, schema):
        if schema in self.schema_indices:
            return self.schema_indices[schema]

    def set_index(self, schema, index):
        self.schema_indices[schema] = index


class PublishedRecordEndpointConfiguration(RecordEndpointConfiguration):
    def __init__(self,
                 rest_name: str,
                 rest: Dict, extra: Dict,
                 paired_endpoint: 'RecordEndpointConfiguration' = None):
        super().__init__(published=True, rest_name=rest_name, rest=rest, extra=extra, paired_endpoint=paired_endpoint)


class DraftRecordEndpointConfiguration(RecordEndpointConfiguration):
    def __init__(self,
                 rest_name: str,
                 rest: Dict, extra: Dict,
                 paired_endpoint: 'RecordEndpointConfiguration' = None):
        super().__init__(published=False, rest_name=rest_name, rest=rest, extra=extra, paired_endpoint=paired_endpoint)

    def set_index(self, schema, index):
        self.schema_indices[schema] = 'draft-' + index


class DraftPublishedRecordConfiguration:
    """
    Binds together draft and published rest endpoint configurations
    """

    def __init__(self, draft: DraftRecordEndpointConfiguration, published: PublishedRecordEndpointConfiguration):
        self.draft = draft
        self.published = published
        draft.paired_endpoint = published
        published.paired_endpoint = draft

    def set_index(self, schema, index):
        self.published.set_index(schema, index)
        self.draft.set_index(schema, 'draft-' + index)


class DraftManagedRecords:
    """
    A collection of records managed by this library
    """

    def __init__(self):
        self.records: List[DraftPublishedRecordConfiguration] = []
        self.by_pid_type: Dict[str, RecordEndpointConfiguration] = {}

    def add_record(
            self,
            draft: DraftRecordEndpointConfiguration,
            published: PublishedRecordEndpointConfiguration
    ):
        self.records.append(DraftPublishedRecordConfiguration(draft, published))
        self.by_pid_type[draft.rest['pid_type']] = draft
        self.by_pid_type[published.rest['pid_type']] = published

    def __iter__(self) -> Iterator[DraftPublishedRecordConfiguration]:
        return iter(self.records)

    def __len__(self):
        return len(self.records)

    def __getitem__(self, item):
        return self.records[item]

    def by_record_class(self, clz):
        potentials = []
        for rec in self.records:
            if rec.published.record_class == clz:
                return rec.published
            if issubclass(clz, rec.published.record_class):
                potentials.append((rec.published, rec.published.record_class))

            if rec.draft.record_class == clz:
                return rec.draft
            if issubclass(clz, rec.draft.record_class):
                potentials.append((rec.draft, rec.draft.record_class))

        if not potentials:
            return None

        # select best potential
        potentials.sort(key=lambda x: len(x[1].mro()))

        # the best one is the most specific one, that is with longest mro
        return potentials[-1][0]


class RecordContext:
    def __init__(self, record_pid, record, **kwargs):
        self.record_pid = record_pid
        self.record = record
        # these two are filled during the record collection phase
        self.draft_record_url = None
        self.published_record_url = None
        for k, v in kwargs.items():
            setattr(self, k, v)

    @property
    def record_uuid(self):
        return self.record.id


class Endpoints:
    """
    A replacement for RECORD_REST_ENDPOINTS until app_extensions_loaded signal is available
    """

    def __init__(self, app, endpoints):
        self.app = app
        self.endpoints = endpoints
        self.ready = False
        self.managed_records = None

    def update(self, other):
        self.endpoints.update(other)

    def __setitem__(self, key, value):
        self.endpoints[key] = value

    def __getitem__(self, item):
        return self.endpoints[item]

    def setup_endpoints(self):
        if not self.ready:
            from oarepo_records_draft.endpoints import setup_draft_endpoints
            with self.app.app_context():
                self.managed_records = setup_draft_endpoints(self.app, self.endpoints)
            self.ready = True
        self.app.extensions['oarepo-draft'].managed_records = self.managed_records

    def items(self):
        self.setup_endpoints()
        return self.endpoints.items()

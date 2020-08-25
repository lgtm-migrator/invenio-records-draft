import invenio_indexer.config
from celery.app.base import App
from invenio_base.signals import app_loaded
from invenio_base.utils import obj_or_import_string
from invenio_indexer.utils import schema_to_index
from invenio_search import current_search

from oarepo_records_draft.mappings import setup_draft_mappings
from .types import RecordSchema, RecordEndpoint


def setup_indexer(app):
    if app.config['INDEXER_RECORD_TO_INDEX'] == invenio_indexer.config.INDEXER_RECORD_TO_INDEX:
        app.config['INDEXER_RECORD_TO_INDEX'] = 'oarepo_records_draft.record.record_to_index'


class Endpoints:
    def __init__(self, app, endpoints):
        self.app = app
        self.endpoints = endpoints
        self.ready = False

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
                self.app.extensions['oarepo-draft'].endpoints = setup_draft_endpoints(self.app, self.endpoints)
            self.ready = True

    def items(self):
        self.setup_endpoints()
        return self.endpoints.items()


class RecordsDraftState:
    def __init__(self, app):
        self.app = app
        self.endpoints = None

    def app_loaded(self, _sender, app=None, **kwargs):
        with app.app_context():
            setup_indexer(app)
            setup_draft_mappings(self, app)

    @property
    def index_mappings(self):
        endpoints = self.endpoints
        ret = {}
        index_names = current_search.mappings.keys()
        for published_code, draft_code, published_options, draft_options in endpoints.values():
            published_record = obj_or_import_string(published_options['record_class'])
            for json_schema in published_record.ALLOWED_SCHEMAS:
                index_name = schema_to_index(json_schema, index_names=index_names)[0]
                draft_index_name = self.draft_for_index(index_name)
                ret[index_name] = RecordSchema(published_record, json_schema, index_name, draft_index_name)
        return ret

    def draft_for_index(self, index_name):
        return 'draft-' + index_name

    @property
    def mappings(self):
        mappings = self.app.extensions['invenio-search'].mappings
        index_mappings = self.index_mappings
        for index_name in mappings:
            if index_name in index_mappings:
                yield index_mappings[index_name]


class RecordsDraft(object):
    def __init__(self, app=None):
        if app:
            self.init_app(app)

    def init_app(self, app):
        self.init_config(app)
        _state = RecordsDraftState(app)
        app.extensions['oarepo-draft'] = _state
        app_loaded.connect(_state.app_loaded)

    def init_config(self, app):
        app.config.setdefault('RECORDS_DRAFT_ENDPOINTS', {})
        app.config['RECORDS_REST_ENDPOINTS'] = Endpoints(app, app.config.get('RECORDS_REST_ENDPOINTS', {}))

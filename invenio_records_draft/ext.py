import json
import os

from invenio_base.signals import app_loaded
from invenio_jsonschemas import current_jsonschemas
from invenio_search import current_search
from invenio_search.utils import schema_to_index

from invenio_records_draft.proxies import current_drafts


class InvenioRecordsDraftState(object):

    def __init__(self, app):
        self.app = app

    def make_draft_schema(self, cfg):
        cfg = self.preprocess_config(cfg)
        schema_data = current_jsonschemas.get_schema(
            cfg['published_schema'], with_refs=False, resolved=True)
        self.remove_required(schema_data)

        target_schema = os.path.join(
            self.app.config['INVENIO_RECORD_DRAFT_SCHEMAS_DIR'],
            cfg['draft_schema'])
        target_dir = os.path.dirname(target_schema)

        if not os.path.exists(target_dir):
            os.makedirs(target_dir)

        with open(target_schema, 'w') as f:
            f.write(json.dumps(schema_data, indent=4, ensure_ascii=False))

        return target_schema

    def make_draft_mapping(self, cfg):
        published_index = schema_to_index(cfg['published_schema'])[0]
        draft_index = schema_to_index(cfg['draft_schema'])[0]

        published_mapping_file = current_search.mappings[published_index]

        with open(published_mapping_file, 'r') as f:
            mapping_data = json.load(f)

        target_mapping = os.path.join(
            self.app.config['INVENIO_RECORD_DRAFT_MAPPINGS_DIR'],
            f'{draft_index}.json')
        target_dir = os.path.dirname(target_mapping)

        if not os.path.exists(target_dir):
            os.makedirs(target_dir)

        with open(target_mapping, 'w') as f:
            f.write(json.dumps(mapping_data, indent=4, ensure_ascii=False))

        return target_mapping

    def remove_required(self, el):
        if isinstance(el, list):
            for c in el:
                self.remove_required(c)
        elif isinstance(el, dict):
            if 'required' in el:
                del el['required']
            for c in el.values():
                self.remove_required(c)

    def draft_schema(self, published_schema):
        if not published_schema.startswith('/'):
            published_schema = '/' + published_schema
        return 'drafts' + published_schema

    def preprocess_config(self, config):
        if isinstance(config, str):
            config = {
                'published_schema': config
            }
        else:
            config = {**config}

        if 'draft_schema' not in config:
            config['draft_schema'] = self.draft_schema(config['published_schema'])

        return config


class InvenioRecordsDraft(object):

    def __init__(self, app=None, db=None):
        if app:
            self.init_app(app, db)

    def init_app(self, app, db=None):
        self.init_config(app)
        app.extensions['invenio-records-draft'] = InvenioRecordsDraftState(app)

    def init_config(self, app):
        app.config['INVENIO_RECORD_DRAFT_SCHEMAS_DIR'] = os.path.join(
            app.instance_path, 'draft_schemas')

        app.config['INVENIO_RECORD_DRAFT_MAPPINGS_DIR'] = os.path.join(
            app.instance_path, 'draft_mappings')


@app_loaded.connect
def register_schemas_and_mappings(sender, app=None, **kwargs):
    with app.app_context():
        for cfg in app.config['INVENIO_RECORD_DRAFT_SCHEMAS']:
            cfg = current_drafts.preprocess_config(cfg)

            draft_schema = cfg['draft_schema']
            if draft_schema in current_jsonschemas.schemas:
                continue  # pragma: no cover

            full_path = os.path.join(app.config['INVENIO_RECORD_DRAFT_SCHEMAS_DIR'], draft_schema)
            if not os.path.exists(full_path):  # pragma: no cover
                print('Draft schema %s not found. '
                      'Please call invenio draft make-schemas' % draft_schema)
                continue

            current_jsonschemas.register_schema(app.config['INVENIO_RECORD_DRAFT_SCHEMAS_DIR'],
                                                draft_schema)

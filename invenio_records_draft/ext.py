import json
import os

from invenio_base.signals import app_loaded
from invenio_jsonschemas import current_jsonschemas


class InvenioRecordsDraftState(object):

    def __init__(self, app):
        self.app = app

    def make_draft_schema(self, published_schema, draft_schema):
        schema_data = current_jsonschemas.get_schema(published_schema, with_refs=False, resolved=True)
        self.remove_required(schema_data)

        target_schema = os.path.join(self.app.config['INVENIO_RECORD_DRAFT_SCHEMAS_DIR'], draft_schema)
        target_dir = os.path.dirname(target_schema)

        if not os.path.exists(target_dir):
            os.makedirs(target_dir)

        with open(target_schema, 'w') as f:
            f.write(json.dumps(schema_data, indent=4, ensure_ascii=False))

        return target_schema

    def remove_required(self, el):
        if isinstance(el, list):
            for c in el:
                self.remove_required(c)
        elif isinstance(el, dict):
            if 'required' in el:
                del el['required']
            for c in el.values():
                self.remove_required(c)


class InvenioRecordsDraft(object):

    def __init__(self, app=None, db=None):
        if app:
            self.init_app(app, db)

    def init_app(self, app, db=None):
        self.init_config(app)
        app.extensions['invenio-records-draft'] = InvenioRecordsDraftState(app)

    def init_config(self, app):
        app.config['INVENIO_RECORD_DRAFT_SCHEMAS_DIR'] = os.path.join(app.instance_path, 'draft_schemas')


@app_loaded.connect
def register_schemas(sender, app=None, **kwargs):
    with app.app_context():
        for cfg in app.config['INVENIO_RECORD_DRAFT_SCHEMAS']:
            draft_schema = cfg['draft_schema']
            if draft_schema in current_jsonschemas.schemas:
                continue

            full_path = os.path.join(app.config['INVENIO_RECORD_DRAFT_SCHEMAS_DIR'], draft_schema)
            if not os.path.exists(full_path):
                print('Draft schema %s not found. Please call invenio draft make-schemas' % draft_schema)
                continue

            current_jsonschemas.register_schema(app.config['INVENIO_RECORD_DRAFT_SCHEMAS_DIR'], draft_schema)

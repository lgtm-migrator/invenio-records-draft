import json
import os
import pkgutil

from elasticsearch import VERSION as ES_VERSION
from invenio_base.signals import app_loaded
from invenio_jsonschemas import current_jsonschemas
from invenio_search import current_search
from invenio_search.utils import schema_to_index

from invenio_records_draft.proxies import current_drafts


class InvenioRecordsDraftState(object):

    def __init__(self, app):
        self.app = app

    def make_draft_schema(self, config):
        config = self.preprocess_config(config)
        schema_data = current_jsonschemas.get_schema(
            config['published_schema'], with_refs=False, resolved=True)
        self.remove_required(schema_data)
        target_schema = config['draft_schema_file']
        target_dir = os.path.dirname(target_schema)

        if not os.path.exists(target_dir):
            os.makedirs(target_dir)

        with open(target_schema, 'w') as f:
            f.write(json.dumps(schema_data, indent=4, ensure_ascii=False))

        return target_schema

    def make_draft_mapping(self, config):
        config = self.preprocess_config(config)
        published_index = config['published_index']

        published_mapping_file = current_search.mappings[published_index]

        with open(published_mapping_file, 'r') as f:
            mapping_data = json.load(f)

        target_mapping = config['draft_mapping_file']
        target_dir = os.path.dirname(target_mapping)

        if not os.path.exists(target_dir):
            os.makedirs(target_dir)

        # add _draft_validation mapping
        draft_mapping = json.loads(pkgutil.get_data('invenio_records_draft', f'/mappings/v{ES_VERSION[0]}/draft.json'))

        first_mapping = list(mapping_data['mappings'].values())[0]
        first_mapping['properties'].update(draft_mapping)

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

    @staticmethod
    def draft_schema(published_schema):
        if not published_schema.startswith('/'):
            published_schema = '/' + published_schema
        return 'draft' + published_schema

    def preprocess_config(self, config):
        if isinstance(config, str):
            config = {
                'published_schema': config
            }
        else:
            config = {**config}

        if 'draft_schema' not in config:
            config['draft_schema'] = self.draft_schema(config['published_schema'])

        config['draft_schema_file'] = os.path.join(
            self.app.config['INVENIO_RECORD_DRAFT_SCHEMAS_DIR'],
            config['draft_schema'])

        config['published_index'] = schema_to_index(config['published_schema'])[0]
        draft_index = schema_to_index(config['draft_schema'])[0]
        config['draft_index'] = draft_index

        config['published_mapping_file'] = current_search.mappings[config['published_index']]

        config['draft_mapping_file'] = os.path.join(
            self.app.config['INVENIO_RECORD_DRAFT_MAPPINGS_DIR'],
            f'{draft_index}.json')

        return config


class InvenioRecordsDraft(object):

    def __init__(self, app=None, db=None):
        if app:
            self.init_app(app, db)

    # noinspection PyUnusedLocal
    def init_app(self, app, db=None):
        self.init_config(app)
        app.extensions['invenio-records-draft'] = InvenioRecordsDraftState(app)

    # noinspection PyMethodMayBeStatic
    def init_config(self, app):
        app.config['INVENIO_RECORD_DRAFT_SCHEMAS_DIR'] = os.path.join(
            app.instance_path, 'draft_schemas')

        app.config['INVENIO_RECORD_DRAFT_MAPPINGS_DIR'] = os.path.join(
            app.instance_path, 'draft_mappings')


# noinspection PyUnusedLocal
@app_loaded.connect
def register_schemas_and_mappings(sender, app=None, **kwargs):
    with app.app_context():
        for config in app.config['INVENIO_RECORD_DRAFT_SCHEMAS']:
            config = current_drafts.preprocess_config(config)

            draft_schema = config['draft_schema']
            if draft_schema in current_jsonschemas.schemas:
                continue  # pragma: no cover

            full_path = os.path.join(app.config['INVENIO_RECORD_DRAFT_SCHEMAS_DIR'], draft_schema)
            if not os.path.exists(full_path):  # pragma: no cover
                print('Draft schema %s not found. '
                      'Please call invenio draft make-schemas' % draft_schema)
                continue

            current_jsonschemas.register_schema(app.config['INVENIO_RECORD_DRAFT_SCHEMAS_DIR'],
                                                draft_schema)

        mapping_prefix = app.config.get('SEARCH_INDEX_PREFIX', None)
        for config in app.config['INVENIO_RECORD_DRAFT_SCHEMAS']:
            config = current_drafts.preprocess_config(config)

            published_index = config['published_index']
            draft_schema = config['draft_schema']
            draft_index = config['draft_index']
            draft_mapping_file = config['draft_mapping_file']

            if draft_index not in current_search.mappings:
                current_search.number_of_indexes += 1
                current_search.mappings[draft_index] = draft_mapping_file

            # create aliases
            for alias_name, alias_mappings in list(current_search.aliases.items()):
                if published_index in alias_mappings:
                    if mapping_prefix and alias_name.startswith(mapping_prefix):
                        draft_alias_name = mapping_prefix + 'draft-' + alias_name[len(mapping_prefix):]
                    else:
                        draft_alias_name = 'draft-' + alias_name

                    if draft_alias_name not in current_search.aliases:
                        current_search.aliases[draft_alias_name] = {}
                    current_search.aliases[draft_alias_name][draft_index] = draft_mapping_file

import copy
import json
import os
import pkgutil
from urllib.parse import urlsplit, urlunparse

from elasticsearch import VERSION as ES_VERSION
from flask import Blueprint, current_app, url_for
from invenio_base.signals import app_loaded
from invenio_jsonschemas import current_jsonschemas
from invenio_records_rest import current_records_rest
from invenio_records_rest.utils import build_default_endpoint_prefixes, obj_or_import_string
from invenio_records_rest.views import create_url_rules
from invenio_search import current_search
from invenio_search.utils import schema_to_index
from jsonref import JsonRef

from invenio_records_draft.endpoints import (
    create_draft_endpoint,
    create_published_endpoint,
    pid_getter,
)
from invenio_records_draft.views import (
    EditRecordAction,
    PublishRecordAction,
    UnpublishRecordAction,
)


def internal_invenio_loader(relative_schema, *args, **kwargs):
    parts = urlsplit(relative_schema)
    if not parts.netloc:
        relative_schema = urlunparse((current_app.config['JSONSCHEMAS_URL_SCHEME'],
                                      current_app.config['JSONSCHEMAS_HOST'],
                                      relative_schema, None, None, None))
    path = current_jsonschemas.url_to_path(relative_schema)
    return current_jsonschemas.get_schema(path)


class InvenioRecordsDraftState(object):

    def __init__(self, app):
        self.app = app
        self.published_schemas = {}
        self.draft_schemas = {}
        self.draft_endpoints = {}
        self.published_endpoints = {}

    def get_schema(self, schema_path):
        schema_data = current_jsonschemas.get_schema(
            schema_path, with_refs=False, resolved=False)
        schema_data = JsonRef.replace_refs(
            schema_data,
            base_uri=current_jsonschemas.path_to_url(schema_path),
            loader=internal_invenio_loader
        )
        return current_jsonschemas.resolver_cls(schema_data)

    def make_draft_schema(self, config):
        config = self.preprocess_config(config)
        schema_data = self.get_schema(config['published_schema'])

        removed_properties = config.get('removed_properties', {
            'type': ['required'],
            'string': ['minLength', 'maxLength', 'pattern', 'format'],
            'integer': [
                'multipleOf',
                'minimum', 'exclusiveMinimum', 'maximum', 'exclusiveMaximum'
            ],
            'number': [
                'multipleOf',
                'minimum', 'exclusiveMinimum', 'maximum', 'exclusiveMaximum'
            ],
            'object': [
                'required', 'minProperties', 'maxProperties', 'dependencies'
            ],
            'array': [
                'minItems', 'maxItems', 'uniqueItems'
            ]
        })

        self.remove_properties(schema_data, removed_properties)
        schema_data['properties']['invenio_draft_validation'] = {
            'type': 'object',
            'additionalProperties': True,
            'properties': {}
        }

        if 'draft_schema_transformer' in config:
            schema_data = config['draft_schema_transformer'](schema_data)
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
        draft_mapping = json.loads(
            pkgutil.get_data('invenio_records_draft',
                             f'/mappings/v{ES_VERSION[0]}/draft.json'))

        first_mapping = list(mapping_data['mappings'].values())[0]
        first_mapping['properties'].update(draft_mapping)

        with open(target_mapping, 'w') as f:
            f.write(json.dumps(mapping_data, indent=4, ensure_ascii=False))

        return target_mapping

    def remove_properties(self, el, props):
        if isinstance(el, list):
            for c in el:
                self.remove_properties(c, props)

        if isinstance(el, dict):
            _type = el.get('type', None)
            removed_props = props.get(str(_type), [])
            for k, c in list(el.items()):
                if k in removed_props:
                    del el[k]
                else:
                    self.remove_properties(c, props)

    def get_draft_schema(self, published_schema):
        if published_schema in self.published_schemas:
            return self.published_schemas[published_schema]['draft_schema']
        local_published_schema = current_jsonschemas.url_to_path(published_schema)
        if local_published_schema in self.published_schemas:
            return self.published_schemas[local_published_schema]['draft_schema']
        raise ValueError('Schema %s not found' % published_schema)

    def preprocess_config(self, config):
        if isinstance(config, str):
            config = {
                'published_schema': config
            }
        else:
            config = {**config}

        if 'draft_schema' not in config:
            if not config['published_schema'].startswith('/'):
                config['draft_schema'] = 'draft' + '/' + config['published_schema']

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

    def app_loaded(self, app):
        with app.app_context():
            self._register_draft_schemas(app)
            self._register_draft_mappings(app)
            self._register_blueprints(app)

    def _register_draft_mappings(self, app):
        mapping_prefix = app.config.get('SEARCH_INDEX_PREFIX', None)
        for config in self.published_schemas.values():
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
                        draft_alias_name = mapping_prefix + 'draft-' + \
                                           alias_name[len(mapping_prefix):]
                    else:
                        draft_alias_name = 'draft-' + alias_name

                    if draft_alias_name not in current_search.aliases:
                        current_search.aliases[draft_alias_name] = {}
                    current_search.aliases[draft_alias_name][draft_index] = \
                        draft_mapping_file

    def _register_draft_schemas(self, app):
        for config in app.config.get('INVENIO_RECORD_DRAFT_SCHEMAS', []):
            config = self.preprocess_config(config)

            published_schema = config['published_schema']
            draft_schema = config['draft_schema']

            if draft_schema in current_jsonschemas.list_schemas():
                continue

            self.published_schemas[published_schema] = config
            self.draft_schemas[draft_schema] = config

            full_path = os.path.join(
                app.config['INVENIO_RECORD_DRAFT_SCHEMAS_DIR'], draft_schema)

            if not os.path.exists(full_path):  # pragma: no cover
                print('Draft schema %s not found. '
                      'Please call invenio draft make-schemas' % draft_schema)
                continue

            current_jsonschemas.register_schema(
                app.config['INVENIO_RECORD_DRAFT_SCHEMAS_DIR'], draft_schema)

    def _register_blueprints(self, app):
        if 'invenio_records_rest' not in app.blueprints:
            return

        rest_blueprint = app.blueprints['invenio_records_rest']
        mapping_prefix = app.config.get('SEARCH_INDEX_PREFIX', None)

        endpoint_configs = app.config.get('DRAFT_ENABLED_RECORDS_REST_ENDPOINTS', {})
        last_deferred_function_index = len(rest_blueprint.deferred_functions)

        permission_factories = {}

        extra_published_record_endpoints = {}
        extra_draft_record_endpoints = {}

        for url_prefix, config in endpoint_configs.items():
            config = copy.copy(config)

            if 'draft_pid_type' not in config:
                raise Exception('Add "draft_pid_type" to '
                                'DRAFT_ENABLED_RECORDS_REST_ENDPOINTS[%s]' % url_prefix)

            json_schemas = config.pop('json_schemas', [])
            if not isinstance(json_schemas, (list, tuple)):
                json_schemas = [json_schemas]

            published_index = (
                    config.pop('published_search_index', None) or
                    config.pop('search_index', None)
            )

            if not published_index:
                published_index = get_search_index(json_schemas, url_prefix)
                if mapping_prefix and published_index.startswith(mapping_prefix):
                    published_index = published_index[len(mapping_prefix):]

            published_endpoint = f'published_{url_prefix}'
            draft_endpoint = f'draft_{url_prefix}'

            record_marshmallow = config.pop('record_marshmallow')
            metadata_marshmallow = config.pop('metadata_marshmallow')

            publish_permission_factory = config.pop('publish_permission_factory')
            unpublish_permission_factory = config.pop('unpublish_permission_factory')
            edit_permission_factory = config.pop('edit_permission_factory')

            permission_factories[url_prefix] = {
                'publish_permission_factory': publish_permission_factory,
                'unpublish_permission_factory': unpublish_permission_factory,
                'edit_permission_factory': edit_permission_factory
            }

            extra_published_record_endpoints[url_prefix] = {
                e: obj_or_import_string(a)
                for e, a in config.pop('extra_published_record_endpoints', {}).items()
            }
            extra_draft_record_endpoints[url_prefix] = {
                e: obj_or_import_string(a)
                for e, a in config.pop('extra_draft_record_endpoints', {}).items()
            }

            published_endpoint_config = create_published_endpoint(
                url_prefix=url_prefix,
                published_endpoint=published_endpoint,
                draft_endpoint=draft_endpoint,
                record_marshmallow=record_marshmallow,
                search_index=published_index,
                publish_permission_factory=publish_permission_factory,
                unpublish_permission_factory=unpublish_permission_factory,
                edit_permission_factory=edit_permission_factory,
                extra_urls=extra_published_record_endpoints[url_prefix],
                **config)

            draft_index = (
                    config.pop('draft_search_index', None) or
                    config.pop('search_index', None)
            )

            if not draft_index:
                draft_schemas = [self.get_draft_schema(x) for x in json_schemas]
                draft_index = get_search_index(draft_schemas, url_prefix)
                if mapping_prefix and draft_index.startswith(mapping_prefix):
                    draft_index = draft_index[len(mapping_prefix):]

            draft_endpoint_config = create_draft_endpoint(
                url_prefix=url_prefix,

                published_endpoint=published_endpoint,
                draft_endpoint=draft_endpoint,
                record_marshmallow=record_marshmallow,
                metadata_marshmallow=metadata_marshmallow,
                search_index=draft_index,
                publish_permission_factory=publish_permission_factory,
                unpublish_permission_factory=unpublish_permission_factory,
                edit_permission_factory=edit_permission_factory,
                extra_urls=extra_draft_record_endpoints[url_prefix],
                **config
            )

            for rule in create_url_rules(published_endpoint, **published_endpoint_config):
                rest_blueprint.add_url_rule(**rule)

            for rule in create_url_rules(draft_endpoint, **draft_endpoint_config):
                rest_blueprint.add_url_rule(**rule)

            default_prefixes = build_default_endpoint_prefixes({
                published_endpoint: published_endpoint_config,
                draft_endpoint: draft_endpoint_config
            })

            current_records_rest.default_endpoint_prefixes.update(default_prefixes)
            draft_endpoint_config['endpoint'] = draft_endpoint
            published_endpoint_config['endpoint'] = published_endpoint
            self.draft_endpoints[url_prefix] = draft_endpoint_config
            self.published_endpoints[url_prefix] = published_endpoint_config

        state = rest_blueprint.make_setup_state(app, {}, False)
        for deferred in rest_blueprint.deferred_functions[last_deferred_function_index:]:
            deferred(state)

        blueprint = Blueprint("invenio_records_draft", __name__, url_prefix="/")

        for prefix in self.draft_endpoints.keys():
            draft_config = self.draft_endpoints[prefix]
            draft_endpoint_name = draft_config['endpoint']

            published_config = self.published_endpoints[prefix]
            published_endpoint_name = published_config['endpoint']

            permissions = permission_factories[prefix]

            draft_url = url_for(
                'invenio_records_rest.{0}_list'.format(draft_endpoint_name),
                _external=False)

            published_url = url_for(
                'invenio_records_rest.{0}_list'.format(published_endpoint_name),
                _external=False)

            published_record_validator = \
                endpoint_configs[prefix].get('published_record_validator', None)

            metadata_marshmallow = \
                endpoint_configs[prefix].get('metadata_marshmallow', None)

            blueprint.add_url_rule(
                rule=f'{draft_url}{pid_getter(draft_config)}/publish',
                view_func=PublishRecordAction.as_view(
                    PublishRecordAction.view_name.format(draft_endpoint_name),
                    publish_permission_factory=permissions['publish_permission_factory'],
                    published_record_class=published_config['record_class'],
                    published_pid_type=published_config['pid_type'],
                    published_endpoint_name=published_endpoint_name
                ))

            blueprint.add_url_rule(
                rule=f'{published_url}{pid_getter(published_config)}/unpublish',
                view_func=UnpublishRecordAction.as_view(
                    UnpublishRecordAction.view_name.format(published_endpoint_name),
                    unpublish_permission_factory=permissions['unpublish_permission_factory'],
                    draft_pid_type=draft_config['pid_type'],
                    draft_record_class=draft_config['record_class'],
                    draft_endpoint_name=draft_endpoint_name
                ))

            blueprint.add_url_rule(
                rule=f'{published_url}{pid_getter(published_config)}/edit',
                view_func=EditRecordAction.as_view(
                    EditRecordAction.view_name.format(published_endpoint_name),
                    edit_permission_factory=permissions['edit_permission_factory'],
                    draft_pid_type=draft_config['pid_type'],
                    draft_record_class=draft_config['record_class'],
                    draft_endpoint_name=draft_endpoint_name
                ))

            for rule, action in extra_published_record_endpoints[prefix].items():
                blueprint.add_url_rule(
                    rule=f'{published_url}{pid_getter(published_config)}/{rule}',
                    view_func=action.as_view(
                        action.view_name.format(published_endpoint_name),
                        draft_config=draft_config,
                        **published_config
                    ))

            for rule, action in extra_draft_record_endpoints[prefix].items():
                blueprint.add_url_rule(
                    rule=f'{draft_url}{pid_getter(draft_config)}/{rule}',
                    view_func=action.as_view(
                        action.view_name.format(draft_endpoint_name),
                        published_config=published_config,
                        **draft_config
                    ))

        app.register_blueprint(blueprint)


def get_search_index(json_schemas, url_prefix):
    indices = [schema_to_index(x)[0] for x in json_schemas]
    indices = [x for x in indices if x]
    if len(indices) == 1:
        return indices[0]
    else:
        raise Exception(
            'Add "published_search_index" or "json_schemas" to '
            'DRAFT_ENABLED_RECORDS_REST_ENDPOINTS["%s"]' % url_prefix)


class InvenioRecordsDraft(object):

    def __init__(self, app=None, db=None):
        if app:
            self.init_app(app, db)

    # noinspection PyUnusedLocal
    def init_app(self, _app, db=None):
        self.init_config(_app)
        _state = InvenioRecordsDraftState(_app)
        _app.extensions['invenio-records-draft'] = _state

        def app_loaded_callback(sender, app, **kwargs):
            if _app == app:
                _state.app_loaded(app)

        app_loaded.connect(app_loaded_callback, weak=False)

    # noinspection PyMethodMayBeStatic
    def init_config(self, app):
        app.config['INVENIO_RECORD_DRAFT_SCHEMAS_DIR'] = os.path.join(
            app.instance_path, 'draft_schemas')

        app.config['INVENIO_RECORD_DRAFT_MAPPINGS_DIR'] = os.path.join(
            app.instance_path, 'draft_mappings')

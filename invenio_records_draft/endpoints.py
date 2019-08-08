from flask import url_for
from flask.helpers import locked_cached_property
from invenio_base.signals import app_loaded
from invenio_db import db
from invenio_pidstore import current_pidstore
from invenio_pidstore.errors import PIDDoesNotExistError
from invenio_pidstore.fetchers import FetchedPID
from invenio_pidstore.models import PersistentIdentifier, PIDStatus
from invenio_records import Record
from invenio_records_rest.loaders import json_patch_loader, marshmallow_loader
from invenio_records_rest.serializers import (
    JSONSerializer,
    record_responsify,
    search_responsify,
)
from invenio_records_rest.utils import allow_all, deny_all, obj_or_import_string

from invenio_records_draft.marshmallow import DraftSchemaWrapper
from invenio_records_draft.record import DraftEnabledRecordMixin
from invenio_records_draft.views import (
    EditRecordAction,
    PublishRecordAction,
    UnpublishRecordAction,
)

DEFAULT_LINKS_FACTORY = 'invenio_records_rest.links.default_links_factory'


def draft_enabled_endpoint(
        url_prefix='records',
        record_marshmallow=None,
        metadata_marshmallow=None,
        search_index='records',
        draft_pid_type=None,
        draft_allow_patch=False,
        publish_permission_factory=allow_all,
        unpublish_permission_factory=allow_all,
        edit_permission_factory=allow_all,
        published_record_validator=None,
        **kwargs
):
    published_endpoint = f'published_{url_prefix}'
    draft_endpoint = f'draft_{url_prefix}'

    common_kwargs = {
        k: v for k, v in kwargs.items()
        if not k.startswith('draft_') and not k.startswith('published_')
    }

    pid_type = common_kwargs.pop('pid_type', 'recid')
    pid_minter = common_kwargs.pop('pid_minter', 'recid')
    pid_fetcher = common_kwargs.pop('pid_fetcher', 'recid')

    draft_kwargs = {
        k[6:]: v for k, v in kwargs.items() if k.startswith('draft_')
    }
    draft_kwargs.update(common_kwargs)

    published_kwargs = {
        k[10:]: v for k, v in kwargs.items() if k.startswith('published_')
    }
    published_kwargs.update(common_kwargs)

    draft_kwargs['default_endpoint_prefix'] = True
    published_kwargs['default_endpoint_prefix'] = True

    check_and_set(draft_kwargs, 'list_route',
                  lambda: f'drafts/{url_prefix}/')
    check_and_set(published_kwargs, 'list_route',
                  lambda: f'/{url_prefix}/')

    check_and_set(draft_kwargs, 'pid_type', lambda: draft_pid_type)
    check_and_set(published_kwargs, 'pid_type', lambda: pid_type)

    draft_pid_minter = make_draft_minter(draft_pid_type, pid_minter)
    check_and_set(draft_kwargs, 'pid_minter', lambda: draft_pid_type)
    check_and_set(published_kwargs, 'pid_minter', lambda: pid_minter)

    draft_pid_fetcher = make_draft_fetcher(draft_pid_type, pid_fetcher)
    check_and_set(draft_kwargs, 'pid_fetcher', lambda: draft_pid_type)
    check_and_set(published_kwargs, 'pid_fetcher', lambda: pid_fetcher)

    check_and_set(draft_kwargs, 'record_class', lambda: Record)
    check_and_set(published_kwargs, 'record_class', lambda: Record)

    check_and_set(draft_kwargs, 'default_media_type', lambda: 'application/json')
    check_and_set(published_kwargs, 'default_media_type', lambda: 'application/json')

    def pid_getter(kw):
        if 'pid_getter' in kw:
            return kw.pop('pid_getter')
        record_class = obj_or_import_string(kw['record_class'])
        record_module_name = record_class.__module__
        record_class_name = record_class.__name__
        pid_type = kw.get('pid_type', 'recid')
        pid = f'pid({pid_type},record_class="{record_module_name}:{record_class_name}")'
        return f'<{pid}:pid_value>'

    check_and_set(draft_kwargs, 'item_route',
                  lambda: f'drafts/{url_prefix}/{pid_getter(draft_kwargs)}')
    check_and_set(published_kwargs, 'item_route',
                  lambda: f'/{url_prefix}/{pid_getter(published_kwargs)}')

    check_and_set(draft_kwargs, 'search_index',
                  lambda: f'draft-{search_index}')
    check_and_set(published_kwargs, 'search_index',
                  lambda: search_index)

    draft_read_permission_factory = \
        draft_kwargs.pop('read_permission_factory', None)
    draft_modify_permission_factory = \
        draft_kwargs.pop('modify_permission_factory', None)

    check_and_set(draft_kwargs, 'read_permission_factory_imp',
                  lambda: draft_read_permission_factory or allow_all)
    check_and_set(draft_kwargs, 'create_permission_factory_imp',
                  lambda: draft_modify_permission_factory or allow_all)
    check_and_set(draft_kwargs, 'update_permission_factory_imp',
                  lambda: draft_modify_permission_factory or allow_all)
    check_and_set(draft_kwargs, 'delete_permission_factory_imp',
                  lambda: draft_modify_permission_factory or allow_all)
    check_and_set(draft_kwargs, 'list_permission_factory_imp',
                  lambda: allow_all)

    published_read_permission_factory = \
        published_kwargs.pop('read_permission_factory', None)
    published_modify_permission_factory = \
        published_kwargs.pop('modify_permission_factory', None)

    check_and_set(published_kwargs, 'read_permission_factory_imp',
                  lambda: published_read_permission_factory or allow_all)
    check_and_set(published_kwargs, 'create_permission_factory_imp',
                  lambda: published_modify_permission_factory or deny_all)
    check_and_set(published_kwargs, 'update_permission_factory_imp',
                  lambda: published_modify_permission_factory or deny_all)
    check_and_set(published_kwargs, 'delete_permission_factory_imp',
                  lambda: published_modify_permission_factory or allow_all)
    check_and_set(published_kwargs, 'list_permission_factory_imp',
                  lambda: allow_all)

    # record and search serializers

    def set_record_serializers(kw, wrapper):
        if 'record_serializers' not in kw:
            kw['record_serializers'] = {}
        rs = kw['record_serializers']
        for mime, sc in kw.pop('serializer_classes', {
            'application/json': JSONSerializer
        }).items():
            if mime not in rs:
                serializer_class = obj_or_import_string(sc)
                serialized = serializer_class(wrapper(
                    obj_or_import_string(record_marshmallow)), replace_refs=True)
                rs[mime] = record_responsify(serialized, mime)

    set_record_serializers(draft_kwargs, DraftSchemaWrapper)
    set_record_serializers(published_kwargs, lambda x: x)

    def set_search_serializers(kw, wrapper):
        if 'search_serializers' not in kw:
            kw['search_serializers'] = {}
        rs = kw['search_serializers']
        for mime, sc in kw.pop('search_serializer_classes', {
            'application/json': JSONSerializer
        }).items():
            if mime not in rs:
                serializer_class = obj_or_import_string(sc)
                serialized = serializer_class(wrapper(
                    obj_or_import_string(record_marshmallow)), replace_refs=True)
                rs[mime] = search_responsify(serialized, mime)

    set_search_serializers(draft_kwargs, DraftSchemaWrapper)
    set_search_serializers(published_kwargs, lambda x: x)

    # loaders
    def set_loaders(kw, wrapper):
        if 'record_loaders' not in kw:
            kw['record_loaders'] = {}

        kl = kw['record_loaders']
        for mime, loader in kw.pop('loader_classes', {
            'application/json': metadata_marshmallow,
        }).items():
            if mime not in kl:
                kl[mime] = marshmallow_loader(wrapper(loader))

        if draft_allow_patch:
            if 'application/json-patch+json' not in kl:
                kl['application/json-patch+json'] = json_patch_loader

    set_loaders(draft_kwargs, DraftSchemaWrapper)

    def register_minters_fetchers(sender, app):
        with app.app_context():
            current_pidstore.minters[draft_pid_type] = draft_pid_minter
            current_pidstore.fetchers[draft_pid_type] = draft_pid_fetcher

    app_loaded.connect(register_minters_fetchers, weak=False)

    draft_kwargs['links_factory_imp'] = \
        DraftLinksFactory(draft_endpoint,
                          pid_type, published_endpoint,
                          draft_kwargs.get('links_factory_impl',
                                           DEFAULT_LINKS_FACTORY),
                          publish_permission_factory,
                          unpublish_permission_factory,
                          edit_permission_factory)

    published_kwargs['links_factory_imp'] = \
        PublishedLinksFactory(published_endpoint,
                              draft_pid_type, draft_endpoint,
                              published_kwargs.get('links_factory_impl',
                                                   DEFAULT_LINKS_FACTORY),
                              publish_permission_factory,
                              unpublish_permission_factory,
                              edit_permission_factory)

    if not published_record_validator:
        published_record_validator = \
            DraftEnabledRecordMixin.marshmallow_validator(metadata_marshmallow)

    _registrar.register_blueprint_views(
        endpoint_name=published_endpoint,
        draft_endpoint_name=draft_endpoint,
        draft_url=draft_kwargs['item_route'],
        published_pid_type=pid_type,
        published_record_class=obj_or_import_string(published_kwargs['record_class']),
        draft_pid_type=draft_pid_type,
        draft_record_class=obj_or_import_string(draft_kwargs['record_class']),
        published_url=published_kwargs['item_route'],
        publish_permission_factory=publish_permission_factory,
        unpublish_permission_factory=unpublish_permission_factory,
        edit_permission_factory=edit_permission_factory,
        published_record_validator=published_record_validator
    )

    return {
        published_endpoint: published_kwargs,
        draft_endpoint: draft_kwargs
    }


def check_and_set(data, key, value):
    if key in data:
        return
    data[key] = value()


def make_draft_minter(draft_pid_type, original_minter):
    def draft_minter(record_uuid, data):
        with db.session.begin_nested():
            pid = PersistentIdentifier.query.filter_by(
                pid_type=original_minter, object_type='rec',
                object_uuid=record_uuid).one_or_none()
            if pid:
                # published version already exists with the same record_uuid => raise an exception,
                # draft and published version can never point to the same invenio record
                raise ValueError('Draft and published version '
                                 'can never point to the same invenio record')
            else:
                # create a new pid as if the record were published
                pid = current_pidstore.minters[original_minter](record_uuid, data)
                # but change the pid type to draft
                pid.pid_type = draft_pid_type
                db.session.add(pid)
                return pid

    return draft_minter


def make_draft_fetcher(draft_pid_type, original_fetcher):
    def draft_fetcher(record_uuid, data):
        fetched_pid = current_pidstore.fetchers[original_fetcher](record_uuid, data)
        return FetchedPID(
            provider=fetched_pid.provider,
            pid_type=draft_pid_type,
            pid_value=fetched_pid.pid_value,
        )

    return draft_fetcher


class LinksFactory:
    def __init__(self, endpoint_name, other_end_pid_type,
                 other_end_endpoint_name, links_factory,
                 publish_permission_factory,
                 unpublish_permission_factory,
                 edit_permission_factory):
        self.endpoint_name = endpoint_name
        self._links_factory = links_factory
        self.other_end_pid_type = other_end_pid_type
        self.other_end_endpoint_name = other_end_endpoint_name
        self.publish_permission_factory = publish_permission_factory
        self.unpublish_permission_factory = unpublish_permission_factory
        self.edit_permission_factory = edit_permission_factory

    @locked_cached_property
    def links_factory(self):
        return obj_or_import_string(self._links_factory)

    def get_other_end_link(self, pid):
        try:
            # check if other side pid exists
            other_side_pid = PersistentIdentifier.get(self.other_end_pid_type, pid.pid_value)
            if other_side_pid.status != PIDStatus.DELETED:
                endpoint = 'invenio_records_rest.{0}_item'.format(self.other_end_endpoint_name)
                return url_for(endpoint, pid_value=pid.pid_value, _external=True)
        except PIDDoesNotExistError:
            pass
        return None


class DraftLinksFactory(LinksFactory):
    def __call__(self, pid, record=None, **kwargs):
        resp = self.links_factory(pid, record=record, **kwargs)
        other_end = self.get_other_end_link(pid)
        if other_end:
            resp['published'] = other_end

        if record and self.publish_permission_factory(record=record).can():
            resp['publish'] = url_for(
                'invenio_records_draft.publish_{0}'.format(self.endpoint_name),
                pid_value=pid.pid_value
            )
        return resp


class PublishedLinksFactory(LinksFactory):
    def __call__(self, pid, record=None, **kwargs):
        resp = self.links_factory(pid, record=record, **kwargs)
        other_end = self.get_other_end_link(pid)
        if other_end:
            resp['draft'] = other_end

        if record and self.unpublish_permission_factory(record=record).can():
            resp['unpublish'] = url_for(
                'invenio_records_draft.unpublish_{0}'.format(self.endpoint_name),
                pid_value=pid.pid_value,
                _external=True
            )

        if record and self.edit_permission_factory(record=record).can():
            resp['edit'] = url_for(
                'invenio_records_draft.edit_{0}'.format(self.endpoint_name),
                pid_value=pid.pid_value,
                _external=True
            )

        return resp


class BlueprintRegistrar:
    def __init__(self):
        self.endpoints = {}

    def add_to_blueprint(self, blueprint):
        for views in self.endpoints.values():
            for rule in views:
                blueprint.add_url_rule(**rule)

    def register_blueprint_views(
            self,
            published_url,
            draft_url,
            published_pid_type,
            published_record_class,
            draft_pid_type,
            draft_record_class,
            endpoint_name,
            draft_endpoint_name,
            publish_permission_factory,
            unpublish_permission_factory,
            edit_permission_factory,
            published_record_validator
    ):
        if endpoint_name in self.endpoints:
            return

        views = [
            dict(rule=f'{draft_url}/publish', view_func=PublishRecordAction.as_view(
                PublishRecordAction.view_name.format(draft_endpoint_name),
                publish_permission_factory=publish_permission_factory,
                published_record_class=published_record_class,
                published_pid_type=published_pid_type,
                published_record_validator=published_record_validator,
                published_endpoint_name=endpoint_name
            )),
            dict(rule=f'{published_url}/unpublish', view_func=UnpublishRecordAction.as_view(
                UnpublishRecordAction.view_name.format(endpoint_name),
                unpublish_permission_factory=unpublish_permission_factory,
                draft_pid_type=draft_pid_type,
                draft_record_class=draft_record_class,
                draft_endpoint_name=draft_endpoint_name
            )),
            dict(rule=f'{published_url}/edit', view_func=EditRecordAction.as_view(
                EditRecordAction.view_name.format(endpoint_name),
                edit_permission_factory=edit_permission_factory,
                draft_pid_type=draft_pid_type,
                draft_record_class=draft_record_class,
                draft_endpoint_name=draft_endpoint_name
            )),
        ]

        self.endpoints[endpoint_name] = views


_registrar = BlueprintRegistrar()

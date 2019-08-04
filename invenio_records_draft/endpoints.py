from flask import current_app, url_for
from invenio_base.signals import app_created, app_loaded
from invenio_db import db
from invenio_pidstore import current_pidstore
from invenio_pidstore.fetchers import FetchedPID
from invenio_pidstore.models import PersistentIdentifier, PIDStatus
from invenio_records import Record
from invenio_records_rest.loaders import marshmallow_loader
from invenio_records_rest.serializers import (
    JSONSerializer,
    record_responsify,
    search_responsify,
)
from invenio_records_rest.utils import allow_all, deny_all, obj_or_import_string

from invenio_records_draft.marshmallow import DraftSchemaWrapper


def draft_enabled_endpoint(
        url_prefix='records',
        record_marshmallow=None,
        metadata_marshmallow=None,
        search_index='records',
        draft_pid_type=None,
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
        k[9:]: v for k, v in kwargs.items() if k.startswith('published_')
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
        draft_kwargs.pop('read_permission_factory', allow_all)
    draft_modify_permission_factory = \
        draft_kwargs.pop('modify_permission_factory', allow_all)

    check_and_set(draft_kwargs, 'read_permission_factory_imp',
                  lambda: draft_read_permission_factory)
    check_and_set(draft_kwargs, 'create_permission_factory_imp',
                  lambda: draft_modify_permission_factory)
    check_and_set(draft_kwargs, 'update_permission_factory_imp',
                  lambda: draft_modify_permission_factory)
    check_and_set(draft_kwargs, 'delete_permission_factory_imp',
                  lambda: draft_modify_permission_factory)
    check_and_set(draft_kwargs, 'list_permission_factory_imp',
                  lambda: allow_all)

    published_read_permission_factory = \
        published_kwargs.pop('read_permission_factory', allow_all)
    published_modify_permission_factory = \
        published_kwargs.pop('modify_permission_factory', deny_all)

    check_and_set(published_kwargs, 'read_permission_factory_imp',
                  lambda: published_read_permission_factory)
    check_and_set(published_kwargs, 'create_permission_factory_imp',
                  lambda: published_modify_permission_factory)
    check_and_set(published_kwargs, 'update_permission_factory_imp',
                  lambda: published_modify_permission_factory)
    check_and_set(published_kwargs, 'delete_permission_factory_imp',
                  lambda: published_modify_permission_factory)
    check_and_set(published_kwargs, 'list_permission_factory_imp',
                  lambda: allow_all)

    check_and_set(draft_kwargs, 'links_factory_imp', lambda: make_links_factory(draft_endpoint))

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
            'application/json': metadata_marshmallow
        }).items():
            if mime not in kl:
                kl[mime] = marshmallow_loader(wrapper(loader))

    set_loaders(draft_kwargs, DraftSchemaWrapper)
    set_loaders(published_kwargs, lambda x: x)

    def register_minters_fetchers(sender, app):
        with app.app_context():
            current_pidstore.minters[draft_pid_type] = draft_pid_minter
            current_pidstore.fetchers[draft_pid_type] = draft_pid_fetcher

    app_loaded.connect(register_minters_fetchers, weak=False)

    return {
        published_endpoint: published_kwargs,
        draft_endpoint: draft_kwargs
    }


def check_and_set(data, key, value):
    if key in data:
        return
    data[key] = value()


def make_links_factory(endpoint_name):
    def default_links_factory(pid, record=None, **kwargs):
        """Factory for record links generation.

        :param pid: A Persistent Identifier instance.
        :returns: Dictionary containing a list of useful links for the record.
        """
        endpoint = 'invenio_records_rest.{0}_item'.format(endpoint_name)
        links = dict(self=url_for(endpoint, pid_value=pid.pid_value, _external=True))
        return links

    return default_links_factory


def make_draft_minter(draft_pid_type, original_minter):
    def draft_minter(record_uuid, data):
        with db.session.begin_nested():
            pid = PersistentIdentifier.query.filter_by(
                pid_type=original_minter, object_type='rec',
                object_uuid=record_uuid).one_or_none()
            if pid:
                # published version already exists with the same record_uuid => raise an exception,
                # draft and published version can never point to the same invenio record
                raise ValueError('Draft and published version can never point to the same invenio record')
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

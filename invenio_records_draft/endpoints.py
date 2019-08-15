import re

from flask import url_for
from flask.helpers import locked_cached_property
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

DEFAULT_LINKS_FACTORY = 'invenio_records_rest.links.default_links_factory'


def create_published_endpoint(url_prefix,
                              published_endpoint, draft_endpoint,
                              record_marshmallow, search_index, draft_pid_type,
                              publish_permission_factory, unpublish_permission_factory,
                              edit_permission_factory,
                              extra_urls,
                              **kwargs):
    published_kwargs = {
        re.sub('^published_', '', k): v for k, v in kwargs.items() if not k.startswith('draft_')
    }

    published_kwargs.setdefault('pid_type', 'recid')
    published_kwargs.setdefault('pid_minter', 'recid')
    published_kwargs.setdefault('pid_fetcher', 'recid')

    published_kwargs.setdefault('default_endpoint_prefix', True)
    published_kwargs.setdefault('list_route', f'/{url_prefix}/')
    published_kwargs.setdefault('record_class', Record)
    published_kwargs.setdefault('default_media_type', 'application/json')

    if not published_kwargs.get('item_route'):
        published_kwargs['item_route'] = f'/{url_prefix}/{pid_getter(published_kwargs)}'

    published_kwargs.setdefault('search_index', search_index)
    published_read_permission_factory = \
        published_kwargs.pop('read_permission_factory', None)
    published_modify_permission_factory = \
        published_kwargs.pop('modify_permission_factory', None)

    published_kwargs.setdefault('read_permission_factory_imp',
                                published_read_permission_factory or allow_all)
    published_kwargs.setdefault('create_permission_factory_imp',
                                published_modify_permission_factory or deny_all)
    published_kwargs.setdefault('update_permission_factory_imp',
                                published_modify_permission_factory or deny_all)
    published_kwargs.setdefault('delete_permission_factory_imp',
                                published_modify_permission_factory or allow_all)
    published_kwargs.setdefault('list_permission_factory_imp',
                                allow_all)

    _set_record_serializers(published_kwargs, record_marshmallow, lambda x: x)
    _set_search_serializers(published_kwargs, record_marshmallow, lambda x: x)
    published_kwargs['links_factory_imp'] = \
        PublishedLinksFactory(published_endpoint,
                              draft_pid_type, draft_endpoint,
                              published_kwargs.get('links_factory_imp',
                                                   DEFAULT_LINKS_FACTORY),
                              publish_permission_factory,
                              unpublish_permission_factory,
                              edit_permission_factory,
                              extra_urls)

    return published_kwargs


def create_draft_endpoint(
        url_prefix,

        published_endpoint,
        draft_endpoint,

        record_marshmallow,
        metadata_marshmallow,
        search_index,
        draft_pid_type,
        publish_permission_factory,
        unpublish_permission_factory,
        edit_permission_factory,
        extra_urls,
        **kwargs
):
    published_pid_type = kwargs.get('published_pid_type', kwargs.get('pid_type', 'recid'))

    draft_kwargs = {
        re.sub('^draft_', '', k): v for k, v in kwargs.items() if not k.startswith('published_')
    }

    draft_kwargs.setdefault('default_endpoint_prefix', True)

    draft_kwargs.setdefault('list_route', f'drafts/{url_prefix}/')

    draft_kwargs['pid_type'] = draft_pid_type

    pid_minter = draft_kwargs.pop('pid_minter', published_pid_type)
    pid_fetcher = draft_kwargs.pop('pid_fetcher', published_pid_type)

    draft_pid_minter = _make_draft_minter(draft_pid_type, pid_minter)
    draft_pid_fetcher = _make_draft_fetcher(draft_pid_type, pid_fetcher)

    draft_kwargs['pid_minter'] = draft_pid_type
    draft_kwargs['pid_fetcher'] = draft_pid_type

    draft_kwargs.setdefault('record_class', Record)

    draft_kwargs.setdefault('default_media_type', 'application/json')

    getter = pid_getter(draft_kwargs)
    draft_kwargs.setdefault('item_route', f'drafts/{url_prefix}/{getter}')

    draft_kwargs.setdefault('search_index', search_index)

    draft_read_permission_factory = \
        draft_kwargs.pop('read_permission_factory', None)
    draft_modify_permission_factory = \
        draft_kwargs.pop('modify_permission_factory', None)

    draft_kwargs.setdefault('read_permission_factory_imp',
                            draft_read_permission_factory or allow_all)
    draft_kwargs.setdefault('create_permission_factory_imp',
                            draft_modify_permission_factory or allow_all)
    draft_kwargs.setdefault('update_permission_factory_imp',
                            draft_modify_permission_factory or allow_all)
    draft_kwargs.setdefault('delete_permission_factory_imp',
                            draft_modify_permission_factory or allow_all)
    draft_kwargs.setdefault('list_permission_factory_imp',
                            allow_all)

    _set_record_serializers(draft_kwargs, record_marshmallow, DraftSchemaWrapper)
    _set_search_serializers(draft_kwargs, record_marshmallow, DraftSchemaWrapper)

    draft_allow_patch = draft_kwargs.pop('allow_patch', False)

    # loaders
    _set_loaders(draft_kwargs, metadata_marshmallow, draft_allow_patch, DraftSchemaWrapper)

    current_pidstore.minters[draft_pid_type] = draft_pid_minter
    current_pidstore.fetchers[draft_pid_type] = draft_pid_fetcher

    draft_kwargs['links_factory_imp'] = \
        DraftLinksFactory(draft_endpoint,
                          published_pid_type, published_endpoint,
                          draft_kwargs.get('links_factory_imp',
                                           DEFAULT_LINKS_FACTORY),
                          publish_permission_factory,
                          unpublish_permission_factory,
                          edit_permission_factory,
                          extra_urls)

    return draft_kwargs


def pid_getter(kw):
    if 'pid_getter' in kw:
        return kw.pop('pid_getter')
    record_class = obj_or_import_string(kw['record_class'])
    record_module_name = record_class.__module__
    record_class_name = record_class.__name__
    pid_type = kw.get('pid_type', 'recid')
    pid = f'pid({pid_type},record_class="{record_module_name}:{record_class_name}")'
    return f'<{pid}:pid_value>'


def _set_record_serializers(kw, record_marshmallow, wrapper):
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


def _set_search_serializers(kw, record_marshmallow, wrapper):
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


def _set_loaders(kw, metadata_marshmallow, draft_allow_patch, wrapper):
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


def check_and_set(data, key, value):
    if key in data:
        return
    data[key] = value()


def _make_draft_minter(draft_pid_type, original_minter):
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


def _make_draft_fetcher(draft_pid_type, original_fetcher):
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
                 edit_permission_factory,
                 extra_urls):
        self.endpoint_name = endpoint_name
        self._links_factory = links_factory
        self.other_end_pid_type = other_end_pid_type
        self.other_end_endpoint_name = other_end_endpoint_name
        self.publish_permission_factory = publish_permission_factory
        self.unpublish_permission_factory = unpublish_permission_factory
        self.edit_permission_factory = edit_permission_factory
        self.extra_urls = extra_urls

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

    def get_extra_url_rules(self, pid):
        resp = {}
        for rule, action in self.extra_urls.items():
            resp[rule] = url_for(
                'invenio_records_draft.{0}'.format(
                    action.view_name.format(self.endpoint_name)
                ), pid_value=pid.pid_value, _external=True)
        return resp


class DraftLinksFactory(LinksFactory):
    def __call__(self, pid, record=None, **kwargs):
        resp = self.links_factory(pid, record=record, **kwargs)
        other_end = self.get_other_end_link(pid)
        if other_end:
            resp['published'] = other_end

        if record and self.publish_permission_factory(record=record).can():
            resp['publish'] = url_for(
                'invenio_records_draft.publish_{0}'.format(self.endpoint_name),
                pid_value=pid.pid_value, _external=True
            )
        resp.update(self.get_extra_url_rules(pid))
        return resp


class PublishedLinksFactory(LinksFactory):
    def __call__(self, pid, record=None, **kwargs):
        resp = self.links_factory(pid, record=record, **kwargs)
        other_end = self.get_other_end_link(pid)
        if other_end and self.edit_permission_factory(record=record).can():
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

        resp.update(self.get_extra_url_rules(pid))

        return resp

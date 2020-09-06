import json
import re

from invenio_app.helpers import obj_or_import_string
from invenio_db import db
from invenio_indexer.utils import schema_to_index
from invenio_pidstore import current_pidstore
from invenio_pidstore.fetchers import FetchedPID
from invenio_pidstore.models import PersistentIdentifier
from invenio_records_rest.utils import deny_all, check_elasticsearch, allow_all
from invenio_search import current_search

from oarepo_records_draft.links import PublishedLinksFactory, DraftLinksFactory
from oarepo_records_draft.record import DraftRecordMixin
from oarepo_records_draft.types import RecordEndpointConfiguration, DraftManagedRecords, \
    PublishedRecordEndpointConfiguration, DraftRecordEndpointConfiguration


def setup_draft_endpoints(app, invenio_endpoints):
    draft_endpoints = {
        k: {**v} for k, v in app.config.get('RECORDS_DRAFT_ENDPOINTS', {}).items()
    }

    drafts = set()
    endpoints = DraftManagedRecords()

    for published, options in draft_endpoints.items():
        if 'draft' in options:
            drafts.add(options['draft'])

    for published, options in draft_endpoints.items():
        if published in drafts:
            continue
        if 'draft' not in options:
            raise ValueError('`draft` not found in RECORDS_DRAFT_ENDPOINTS[%s]' % published)
        draft = options.pop('draft')
        if draft not in draft_endpoints:
            draft_endpoints[draft] = {}
        published_endpoint, draft_endpoint = setup_draft_endpoint(app, published, draft, draft_endpoints[published],
                                                                  draft_endpoints[draft])

        endpoints.add_record(
            draft=draft_endpoint,
            published=published_endpoint
        )

        invenio_endpoints[published_endpoint.rest_name] = published_endpoint.rest
        invenio_endpoints[draft_endpoint.rest_name] = draft_endpoint.rest

    return endpoints


def copy(source, target, prop, default=None):
    if default is not None and prop not in source:
        source[prop] = default

    if prop in source and prop not in target:
        target[prop] = source[prop]


def setup_draft_endpoint(app, published_code, draft_code, published, draft):
    extra_draft = {}
    extra_published = {}

    if 'pid_type' not in published:
        published['pid_type'] = published_code

    if 'pid_type' not in draft:
        draft['pid_type'] = draft_code

    draft_endpoint = DraftRecordEndpointConfiguration(
        rest_name=draft_code,
        rest=draft,
        extra=extra_draft
    )
    published_endpoint = PublishedRecordEndpointConfiguration(
        rest_name=published_code,
        rest=published,
        extra=extra_published
    )

    copy(published, draft, 'default_endpoint_prefix', True)
    copy(published, draft, 'default_media_type', 'application/json')
    copy(published, draft, 'max_result_window')
    copy(published, draft, 'record_loaders')
    copy(published, draft, 'record_serializers', {
        'application/json': 'oarepo_validate:json_response',
    })
    copy(published, draft, 'record_serializers_aliases')
    copy(published, draft, 'search_serializers', {
        'application/json': 'oarepo_validate:json_search',
    })
    copy(published, draft, 'search_serializers_aliases')
    copy(published, draft, 'search_class')
    copy(published, draft, 'indexer_class')
    copy(published, draft, 'search_factory_impl')
    copy(published, draft, 'suggesters')
    copy(published, draft, 'use_options_view')
    copy(published, draft, 'error_handlers')

    if 'create_permission_factory_imp' not in published:
        published['create_permission_factory_imp'] = deny_all

    if 'delete_permission_factory_imp' not in published:
        published['delete_permission_factory_imp'] = deny_all

    if 'update_permission_factory_imp' not in published:
        published['update_permission_factory_imp'] = deny_all

    if 'list_permission_factory_imp' not in published:
        published['list_permission_factory_imp'] = allow_all

    if 'read_permission_factory_imp' not in published:
        published['read_permission_factory_imp'] = check_elasticsearch

    if 'create_permission_factory_imp' not in draft:
        draft['create_permission_factory_imp'] = deny_all

    if 'delete_permission_factory_imp' not in draft:
        draft['delete_permission_factory_imp'] = deny_all

    if 'update_permission_factory_imp' not in draft:
        draft['update_permission_factory_imp'] = deny_all

    if 'list_permission_factory_imp' not in draft:
        draft['list_permission_factory_imp'] = allow_all

    if 'read_permission_factory_imp' not in draft:
        draft['read_permission_factory_imp'] = check_elasticsearch

    if 'record_class' not in published:
        raise ValueError('Record class not in %s' % published_code)

    if 'record_class' not in draft:
        draft['record_class'] = generate_draft_record_class(published['record_class'])

    if 'list_route' not in published:
        published['list_route'] = '/' + published_code

    if 'list_route' not in draft:
        draft['list_route'] = '/draft' + published['list_route']

    if 'item_route' not in published:
        record_pid = 'pid(%s,record_class="%s")' % (published['pid_type'], published['record_class'])
        route = published['list_route']
        if not route.endswith('/'):
            route += '/'
        published['item_route'] = route + '<{0}:pid_value>'.format(record_pid)

    if 'item_route' not in draft:
        if not isinstance(draft['record_class'], str):
            raise ValueError('item_route is not specified in %s and %s["record_class"] '
                             'is not string, so can not generate item_route for you' % (draft_code, draft_code))
        replaced_pid = re.sub(r'<pid\(.*?,', f'<pid({draft["pid_type"]},', published['item_route'])
        replaced_record_class = re.sub(r'record_class\s*=\s*".*?"', f'record_class="{draft["record_class"]}"',
                                       replaced_pid)
        draft['item_route'] = '/draft' + replaced_record_class

    if 'pid_fetcher' not in published:
        raise ValueError('pid_fetcher not in %s' % published_code)

    if 'pid_fetcher' not in draft:
        draft['pid_fetcher'] = make_draft_fetcher(draft['pid_type'], published['pid_fetcher'])

    if 'pid_minter' not in published:
        raise ValueError('pid_minter not in %s' % published_code)

    if 'pid_minter' not in draft:
        draft['pid_minter'] = make_draft_minter(draft['pid_type'], published['pid_minter'])

    if 'search_index' not in published:
        record_class = obj_or_import_string(published['record_class'])
        if not hasattr(record_class, 'PREFERRED_SCHEMA'):
            raise ValueError('search_index not in %s' % published_code)
        preferred_schema = record_class.PREFERRED_SCHEMA
        index, doc_type = schema_to_index(preferred_schema, index_names=current_search.mappings.keys())
        if index:
            published['search_index'] = index
        else:
            raise ValueError('search_index not in %s and can not be determined from PREFERRED_SCHEMA' % published_code)

    if 'search_index' not in draft:
        if published['search_index']:
            draft['search_index'] = 'draft-' + published['search_index']
        else:
            draft['search_index'] = None

    publish_permission_factory = published.pop('publish_permission_factory_imp', deny_all)
    unpublish_permission_factory = published.pop('unpublish_permission_factory_imp', deny_all)
    edit_permission_factory = published.pop('edit_permission_factory_imp', deny_all)

    publish_permission_factory = draft.pop('publish_permission_factory_imp', publish_permission_factory)
    unpublish_permission_factory = draft.pop('unpublish_permission_factory_imp', unpublish_permission_factory)
    edit_permission_factory = draft.pop('edit_permission_factory_imp', edit_permission_factory)

    extra_draft['publish_permission_factory'] = publish_permission_factory
    extra_published['unpublish_permission_factory'] = unpublish_permission_factory
    extra_published['edit_permission_factory'] = edit_permission_factory

    extra_draft['actions'] = draft.pop('actions', {})
    extra_published['actions'] = published.pop('actions', {})

    published['links_factory_imp'] = \
        PublishedLinksFactory(
            published_endpoint,
            links_factory=published.get('links_factory_imp'),
            actions=extra_published['actions'])

    draft['links_factory_imp'] = \
        DraftLinksFactory(draft_endpoint,
                          links_factory=draft.get('links_factory_imp'),
                          actions=extra_draft['actions'])

    return published_endpoint, draft_endpoint


def make_draft_fetcher(draft_pid_type, original_fetcher):
    def draft_fetcher(record_uuid, data):
        fetched_pid = current_pidstore.fetchers[original_fetcher](record_uuid, data)
        return FetchedPID(
            provider=fetched_pid.provider,
            pid_type=draft_pid_type,
            pid_value=fetched_pid.pid_value,
        )

    current_pidstore.fetchers[draft_pid_type + '_fetcher'] = draft_fetcher
    return draft_pid_type + '_fetcher'


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

                try:
                    # if the draft version already exists, return it
                    return PersistentIdentifier.get(draft_pid_type, pid.pid_value)
                except:
                    # otherwise change the pid type to draft and return it
                    pid.pid_type = draft_pid_type
                    db.session.add(pid)
                return pid

    current_pidstore.minters[draft_pid_type + '_minter'] = draft_minter
    return draft_pid_type + '_minter'


def generate_draft_record_class(record_class):
    rc_package = obj_or_import_string(record_class.split(':')[0])
    rc = obj_or_import_string(record_class)
    draft_name = rc.__name__ + 'Draft'
    if not hasattr(rc_package, draft_name):
        setattr(rc_package, draft_name, type(draft_name, (
            DraftRecordMixin,
            rc
        ), {}))
    return record_class.split(':')[0] + ':' + draft_name

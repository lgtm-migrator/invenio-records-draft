from invenio_pidstore.models import PersistentIdentifier
from invenio_records_rest.links import default_links_factory
from invenio_records_rest.utils import allow_all, deny_all

from invenio_records_draft.endpoints import DraftLinksFactory, PublishedLinksFactory


def test_draft_link_factory_not_published_no_rights(app, db, schemas, mappings, draft_record,
                                                    prepare_es,
                                                    client, published_records_url):
    factory = DraftLinksFactory(
        endpoint_name='draft_records',
        other_end_pid_type='recid',
        other_end_endpoint_name='published_records',
        links_factory=default_links_factory,
        publish_permission_factory=deny_all,
        unpublish_permission_factory=deny_all,
        edit_permission_factory=deny_all,
        extra_urls={}
    )
    # create a request context to invenio-records-rest so that invenio knows it is handling
    # the request and can create link urls properly
    with app.test_request_context(published_records_url):
        links = factory(PersistentIdentifier.query.filter_by(object_uuid=draft_record.id).one(),
                        draft_record)
    assert 'publish' not in links
    assert 'published' not in links


def test_draft_link_factory_not_published_rights(app, db, schemas, mappings, draft_record,
                                                 prepare_es,
                                                 client, published_records_url):
    factory = DraftLinksFactory(
        endpoint_name='draft_records',
        other_end_pid_type='recid',
        other_end_endpoint_name='published_records',
        links_factory=default_links_factory,
        publish_permission_factory=allow_all,
        unpublish_permission_factory=allow_all,
        edit_permission_factory=allow_all,
        extra_urls={}
    )
    # create a request context to invenio-records-rest so that invenio knows it is handling
    # the request and can create link urls properly
    with app.test_request_context(published_records_url):
        links = factory(PersistentIdentifier.query.filter_by(object_uuid=draft_record.id).one(),
                        draft_record)
    assert links['publish'] == 'http://localhost:5000/drafts/records/1/publish'
    assert 'published' not in links


def test_draft_link_factory_published_no_rights(app, db, schemas, mappings, draft_record,
                                                prepare_es, published_record,
                                                client, published_records_url):
    factory = DraftLinksFactory(
        endpoint_name='draft_records',
        other_end_pid_type='recid',
        other_end_endpoint_name='published_records',
        links_factory=default_links_factory,
        publish_permission_factory=deny_all,
        unpublish_permission_factory=deny_all,
        edit_permission_factory=deny_all,
        extra_urls={}
    )
    # create a request context to invenio-records-rest so that invenio knows it is handling
    # the request and can create link urls properly
    with app.test_request_context(published_records_url):
        links = factory(PersistentIdentifier.query.filter_by(object_uuid=draft_record.id).one(),
                        draft_record)
    assert 'publish' not in links
    assert links['published'] == 'http://localhost:5000/records/1'


def test_draft_link_factory_published_rights(app, db, schemas, mappings, draft_record,
                                             prepare_es, published_record,
                                             client, published_records_url):
    factory = DraftLinksFactory(
        endpoint_name='draft_records',
        other_end_pid_type='recid',
        other_end_endpoint_name='published_records',
        links_factory=default_links_factory,
        publish_permission_factory=allow_all,
        unpublish_permission_factory=allow_all,
        edit_permission_factory=allow_all,
        extra_urls={}
    )
    # create a request context to invenio-records-rest so that invenio knows it is handling
    # the request and can create link urls properly
    with app.test_request_context(published_records_url):
        links = factory(PersistentIdentifier.query.filter_by(object_uuid=draft_record.id).one(),
                        draft_record)
    assert links['publish'] == 'http://localhost:5000/drafts/records/1/publish'
    assert links['published'] == 'http://localhost:5000/records/1'


def test_published_link_factory_no_draft_no_rights(app, db, schemas, mappings, published_record,
                                                   prepare_es,
                                                   client, published_records_url):
    factory = PublishedLinksFactory(
        endpoint_name='published_records',
        other_end_pid_type='drecid',
        other_end_endpoint_name='draft_records',
        links_factory=default_links_factory,
        publish_permission_factory=deny_all,
        unpublish_permission_factory=deny_all,
        edit_permission_factory=deny_all,
        extra_urls={}
    )
    # create a request context to invenio-records-rest so that invenio knows it is handling
    # the request and can create link urls properly
    with app.test_request_context(published_records_url):
        links = factory(
            PersistentIdentifier.query.filter_by(object_uuid=published_record.id).one(),
            published_record
        )
    assert 'unpublish' not in links
    assert 'edit' not in links
    assert 'draft' not in links


def test_published_link_factory_no_draft_rights(app, db, schemas, mappings, published_record,
                                                prepare_es,
                                                client, published_records_url):
    factory = PublishedLinksFactory(
        endpoint_name='published_records',
        other_end_pid_type='drecid',
        other_end_endpoint_name='draft_records',
        links_factory=default_links_factory,
        publish_permission_factory=allow_all,
        unpublish_permission_factory=allow_all,
        edit_permission_factory=allow_all,
        extra_urls={}
    )
    # create a request context to invenio-records-rest so that invenio knows it is handling
    # the request and can create link urls properly
    with app.test_request_context(published_records_url):
        links = factory(
            PersistentIdentifier.query.filter_by(object_uuid=published_record.id).one(),
            published_record
        )
    assert 'unpublish' in links
    assert 'edit' in links
    assert 'draft' not in links


def test_published_link_factory_draft_no_rights(app, db, schemas, mappings, published_record,
                                                prepare_es, draft_record,
                                                client, published_records_url):
    factory = PublishedLinksFactory(
        endpoint_name='published_records',
        other_end_pid_type='drecid',
        other_end_endpoint_name='draft_records',
        links_factory=default_links_factory,
        publish_permission_factory=deny_all,
        unpublish_permission_factory=deny_all,
        edit_permission_factory=deny_all,
        extra_urls={}
    )
    # create a request context to invenio-records-rest so that invenio knows it is handling
    # the request and can create link urls properly
    with app.test_request_context(published_records_url):
        links = factory(
            PersistentIdentifier.query.filter_by(object_uuid=published_record.id).one(),
            published_record
        )
    assert 'unpublish' not in links
    assert 'edit' not in links
    assert 'draft' not in links


def test_published_link_factory_draft_rights(app, db, schemas, mappings, published_record,
                                             prepare_es, draft_record,
                                             client, published_records_url):
    factory = PublishedLinksFactory(
        endpoint_name='published_records',
        other_end_pid_type='drecid',
        other_end_endpoint_name='draft_records',
        links_factory=default_links_factory,
        publish_permission_factory=allow_all,
        unpublish_permission_factory=allow_all,
        edit_permission_factory=allow_all,
        extra_urls={}
    )
    # create a request context to invenio-records-rest so that invenio knows it is handling
    # the request and can create link urls properly
    with app.test_request_context(published_records_url):
        links = factory(
            PersistentIdentifier.query.filter_by(object_uuid=published_record.id).one(),
            published_record
        )
    assert 'unpublish' in links
    assert 'edit' in links
    assert links['draft'] == 'http://localhost:5000/drafts/records/1'

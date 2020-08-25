# -*- coding: utf-8 -*-
"""Defines fixtures available to all tests."""
import os
import shutil
import sys
import uuid
from collections import namedtuple

import pytest
from flask import Flask, make_response, url_for
from flask.testing import FlaskClient
from flask_login import LoginManager, login_user
from flask_principal import Principal
from invenio_accounts.models import Role, User
from invenio_base.signals import app_loaded
from invenio_db import InvenioDB
from invenio_db import db as _db
from invenio_indexer import InvenioIndexer
from invenio_indexer.api import RecordIndexer
from invenio_jsonschemas import InvenioJSONSchemas
from invenio_pidstore import InvenioPIDStore
from invenio_pidstore.minters import recid_minter
from invenio_pidstore.models import PersistentIdentifier, PIDStatus
from invenio_records import InvenioRecords
from invenio_records_rest import InvenioRecordsREST
from invenio_records_rest.utils import PIDConverter
import invenio_records_rest.views
from invenio_rest import InvenioREST
from invenio_search import InvenioSearch, current_search_client
from invenio_search.cli import destroy, init
from oarepo_records_draft.ext import RecordsDraft
from oarepo_records_draft.record import DraftRecordMixin
from sample.ext import SampleExt
from sample.record import SampleRecord
from sqlalchemy_utils import create_database, database_exists
from tests.helpers import set_identity


class JsonClient(FlaskClient):
    def open(self, *args, **kwargs):
        kwargs.setdefault('content_type', 'application/json')
        kwargs.setdefault('Accept', 'application/json')
        return super().open(*args, **kwargs)


@pytest.fixture()
def base_app():
    """Flask applicat-ion fixture."""
    instance_path = os.path.join(sys.prefix, 'var', 'test-instance')

    # empty the instance path
    if os.path.exists(instance_path):
        shutil.rmtree(instance_path)
    os.makedirs(instance_path)

    os.environ['INVENIO_INSTANCE_PATH'] = instance_path

    app_ = Flask('invenio-records-draft-testapp', instance_path=instance_path)
    app_.config.update(
        TESTING=True,
        JSON_AS_ASCII=True,
        SQLALCHEMY_TRACK_MODIFICATIONS=True,
        SQLALCHEMY_DATABASE_URI=os.environ.get(
            'SQLALCHEMY_DATABASE_URI',
            'sqlite:///:memory:'),
        SERVER_NAME='localhost:5000',
        SECURITY_PASSWORD_SALT='TEST_SECURITY_PASSWORD_SALT',
        SECRET_KEY='TEST_SECRET_KEY',
        INVENIO_INSTANCE_PATH=instance_path,
        SEARCH_INDEX_PREFIX='test-',
        RECORDS_REST_ENDPOINTS={},
        JSONSCHEMAS_HOST='localhost:5000',
        SEARCH_ELASTIC_HOSTS=os.environ.get('SEARCH_ELASTIC_HOSTS', None)
    )
    app.test_client_class = JsonClient

    from oarepo_records_draft import config  # noqa

    InvenioDB(app_)
    InvenioIndexer(app_)
    InvenioSearch(app_)
    RecordsDraft(app_)

    return app_


@pytest.yield_fixture()
def app(base_app):
    """Flask application fixture."""

    base_app._internal_jsonschemas = InvenioJSONSchemas(base_app)
    InvenioREST(base_app)
    InvenioRecordsREST(base_app)
    InvenioRecords(base_app)
    InvenioPIDStore(base_app)
    base_app.url_map.converters['pid'] = PIDConverter
    SampleExt(base_app)

    base_app.register_blueprint(invenio_records_rest.views.create_blueprint_from_app(base_app))

    principal = Principal(base_app)

    login_manager = LoginManager()
    login_manager.init_app(base_app)
    login_manager.login_view = 'login'

    @login_manager.user_loader
    def basic_user_loader(user_id):
        user_obj = User.query.get(int(user_id))
        return user_obj

    @base_app.route('/test/login/<int:id>', methods=['GET', 'POST'])
    def test_login(id):
        print("test: logging user with id", id)
        response = make_response()
        user = User.query.get(id)
        login_user(user)
        set_identity(user)
        return response

    app_loaded.send(None, app=base_app)

    with base_app.app_context():
        yield base_app


@pytest.yield_fixture()
def client(app):
    """Get test client."""
    with app.test_client() as client:
        print(app.url_map)
        yield client


@pytest.fixture
def db(app):
    """Create database for the tests."""
    with app.app_context():
        if not database_exists(str(_db.engine.url)) and \
                app.config['SQLALCHEMY_DATABASE_URI'] != 'sqlite://':
            create_database(_db.engine.url)
        _db.create_all()

    yield _db

    # Explicitly close DB connection
    _db.session.close()
    _db.drop_all()


@pytest.fixture
def published_records_url(app):
    return url_for('oarepo_records_rest.published_records_list')


@pytest.fixture
def draft_records_url(app):
    return url_for('oarepo_records_rest.draft_records_list')


TestUsers = namedtuple('TestUsers', ['u1', 'u2', 'u3', 'r1', 'r2'])


@pytest.fixture()
def test_users(app, db):
    """Returns named tuple (u1, u2, u3, r1, r2)."""
    with db.session.begin_nested():
        r1 = Role(name='role1')
        r2 = Role(name='role2')

        u1 = User(id=1, email='1@test.com', active=True, roles=[r1])
        u2 = User(id=2, email='2@test.com', active=True, roles=[r1, r2])
        u3 = User(id=3, email='3@test.com', active=True, roles=[r2])

        db.session.add(u1)
        db.session.add(u2)
        db.session.add(u3)

        db.session.add(r1)
        db.session.add(r2)

    return TestUsers(u1, u2, u3, r1, r2)


@pytest.fixture()
def prepare_es(app, db):
    runner = app.test_cli_runner()
    result = runner.invoke(destroy, ['--yes-i-know', '--force'])
    if result.exit_code:
        print(result.output, file=sys.stderr)
    assert result.exit_code == 0
    result = runner.invoke(init)
    if result.exit_code:
        print(result.output, file=sys.stderr)
    assert result.exit_code == 0


@pytest.fixture()
def published_record(app, db, schemas, mappings, prepare_es):
    # let's create a record
    record_uuid = uuid.uuid4()
    data = {
        'title': 'blah',
        '$schema': schemas['published']
    }
    recid_minter(record_uuid, data)
    rec = SampleRecord.create(data, id_=record_uuid)
    RecordIndexer().index(rec)
    current_search_client.indices.refresh()
    current_search_client.indices.flush()

    return rec


class SampleDraftRecord(DraftRecordMixin, SampleRecord):
    pass


@pytest.fixture()
def draft_record(app, db, schemas, mappings, prepare_es):
    # let's create a record
    draft_uuid = uuid.uuid4()
    data = {
        'title': 'blah',
        '$schema': schemas['draft'],
        'id': '1'
    }
    PersistentIdentifier.create(
        pid_type='drecid', pid_value='1', status=PIDStatus.REGISTERED,
        object_type='rec', object_uuid=draft_uuid
    )
    rec = SampleDraftRecord.create(data, id_=draft_uuid)

    RecordIndexer().index(rec)
    current_search_client.indices.refresh()
    current_search_client.indices.flush()

    return rec

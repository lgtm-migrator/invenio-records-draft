# -*- coding: utf-8 -*-
"""Defines fixtures available to all tests."""
import os
import shutil
import subprocess
import sys

import pip
import pytest
from flask import Flask
from flask.testing import FlaskClient
from invenio_base.signals import app_loaded
from invenio_db import InvenioDB
from invenio_db import db as _db
from invenio_jsonschemas import InvenioJSONSchemas
from sqlalchemy_utils import create_database, database_exists

from invenio_records_draft.cli import make_schemas
from invenio_records_draft.ext import InvenioRecordsDraft, register_schemas
from sample.records import Records


class JsonClient(FlaskClient):
    def open(self, *args, **kwargs):
        kwargs.setdefault('content_type', 'application/json')
        kwargs.setdefault('Accept', 'application/json')
        return super().open(*args, **kwargs)


def install(package):
    assert subprocess.call([sys.executable, "-m", "pip", "install", '-e', package]) == 0


@pytest.fixture()
def base_app():
    """Flask application fixture."""
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
        SERVER_NAME='localhost',
        SECURITY_PASSWORD_SALT='TEST_SECURITY_PASSWORD_SALT',
        SECRET_KEY='TEST_SECRET_KEY',
        INVENIO_INSTANCE_PATH=instance_path
    )
    app.test_client_class = JsonClient

    InvenioDB(app_)

    return app_


@pytest.yield_fixture()
def app(base_app):
    """Flask application fixture."""
    InvenioRecordsDraft(base_app)
    # base_app.register_blueprint(blueprint)

    base_app._internal_jsonschemas = InvenioJSONSchemas(base_app)

    # install sample application to the testing virtualenv
    install(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'sample'))
    Records(base_app)

    with base_app.app_context():
        yield base_app


@pytest.yield_fixture()
def client(app):
    """Get test client."""
    with app.test_client() as client:
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
def schemas(app):
    runner = app.test_cli_runner()
    result = runner.invoke(make_schemas)
    assert result.exit_code == 0

    # trigger registration of new schemas, normally performed
    # via app_loaded signal that is not emitted in tests
    register_schemas(app, app=app)

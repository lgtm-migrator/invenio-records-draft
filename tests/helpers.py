import flask
import requests
from flask import current_app
from flask_principal import Identity, identity_changed
from invenio_access import authenticated_user


def header_links(resp):
    links = requests.utils.parse_header_links(resp.headers['link'])
    return {
        link['rel']: link['url'] for link in links
    }


def set_identity(u):
    """Sets identity in flask.g to the user."""
    identity = Identity(u.id)
    identity.provides.add(authenticated_user)
    identity_changed.send(current_app._get_current_object(), identity=identity)
    assert flask.g.identity.id == u.id


def login(http_client, user):
    """Calls test login endpoint to log user."""
    resp = http_client.get(f'/test/login/{user.id}')
    assert resp.status_code == 200

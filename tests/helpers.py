from contextlib import contextmanager

import flask
import requests
from flask import current_app
from flask_principal import Identity, identity_changed
from invenio_access import authenticated_user
from invenio_records_rest.utils import allow_all
from marshmallow import ValidationError
from marshmallow import __version_info__ as marshmallow_version

from invenio_records_draft.proxies import current_drafts


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


@contextmanager
def disable_test_authenticated():
    stored_drafts = {}
    stored_published = {}
    for prefix, endpoint in current_drafts.draft_endpoints.items():
        stored_drafts[prefix] = {**endpoint}
        endpoint['publish_permission_factory'] = allow_all
        endpoint['unpublish_permission_factory'] = allow_all
        endpoint['edit_permission_factory'] = allow_all
    for prefix, endpoint in current_drafts.published_endpoints.items():
        stored_published[prefix] = {**endpoint}
        endpoint['publish_permission_factory'] = allow_all
        endpoint['unpublish_permission_factory'] = allow_all
        endpoint['edit_permission_factory'] = allow_all
    try:
        yield
    finally:
        for prefix in current_drafts.draft_endpoints:
            current_drafts.draft_endpoints[prefix] = stored_drafts[prefix]
        for prefix in current_drafts.published_endpoints:
            current_drafts.published_endpoints[prefix] = stored_published[prefix]


def marshmallow_load(schema, data):
    ret = schema.load(data)
    if marshmallow_version[0] >= 3:
        return ret
    if ret[1] != {}:
        raise ValidationError(message=ret[1])
    return ret[0]

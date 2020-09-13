from contextlib import contextmanager

import flask
import requests
from flask import current_app
from flask_login import current_user
from flask_principal import Identity, identity_changed, UserNeed, RoleNeed, identity_loaded
from invenio_access import authenticated_user
from invenio_records_rest.utils import allow_all
from marshmallow import ValidationError
from marshmallow import __version_info__ as marshmallow_version

from oarepo_records_draft.proxies import current_drafts


def header_links(resp):
    links = requests.utils.parse_header_links(resp.headers['link'])
    return {
        link['rel']: link['url'] for link in links
    }


def set_identity(u):
    """Sets identity in flask.g to the user."""
    identity = Identity(u.id)
    identity_changed.send(current_app._get_current_object(), identity=identity)
    assert flask.g.identity.id == u.id


@identity_loaded.connect
def identity_loaded_callback(sender, identity=None, **kwargs):
    print('Identity loaded', identity, current_user)
    if not current_user.is_authenticated:
        return

    identity.provides.add(authenticated_user)
    identity.provides.add(UserNeed(current_user.id))
    for r in current_user.roles:
        identity.provides.add(RoleNeed(r.name))


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


def isinstance_namedtuple(x):
    return (isinstance(x, tuple) and
            getattr(x, '_fields', None) is not None)


def dict_to_test(d):
    def convert(x):
        if x is None:
            return x
        if type(x) in (str, int, bool):
            return x
        if isinstance_namedtuple(x):
            return dict_to_test(x._asdict())
        if isinstance(x, dict):
            return dict_to_test(x)
        if isinstance(x, (list, tuple)):
            return [convert(y) for y in x]
        try:
            return x.__name__
        except:
            pass
        try:
            return x.__class__.__name__
        except:
            pass
        return x

    return {
        k: convert(v) for k, v in d.items()
    }


def remove_ts(d):
    if d is None:
        return d
    if isinstance(d, (list, tuple)):
        for y in d:
            remove_ts(y)
        return d
    if not isinstance(d, dict):
        return d
    for k, v in list(d.items()):
        if k in ('created', 'updated', '_bucket'):
            del d[k]
        else:
            remove_ts(v)
    return d

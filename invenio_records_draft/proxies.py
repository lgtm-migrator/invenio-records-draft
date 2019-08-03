from flask import current_app
from werkzeug.local import LocalProxy

current_drafts = LocalProxy(
    lambda: current_app.extensions['invenio-records-draft'])
"""Helper proxy to access draft state object."""

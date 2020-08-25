from flask import current_app
from werkzeug.local import LocalProxy

current_drafts = LocalProxy(lambda: current_app.extensions['oarepo-draft'])
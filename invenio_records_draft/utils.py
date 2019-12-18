from flask import current_app
from invenio.version import __version__ as __invenio_version__

try:
    from marshmallow import __version_info__ as marshmallow_version
except:
    marshmallow_version = (2, 'x')

if __invenio_version__ < '3.2':
    prefixing_needed = True
else:
    prefixing_needed = False

if marshmallow_version[0] >= 3:
    def load_dump(x):
        return dict(data_key='$schema')
else:
    def load_dump(x):
        return dict(load_from='$schema', dump_to='$schema')


def prefixed_search_index(idx):
    if prefixing_needed:
        return current_app.config.get('SEARCH_INDEX_PREFIX', '') + idx
    return idx

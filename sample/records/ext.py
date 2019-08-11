from __future__ import absolute_import, print_function

from . import config


class Records(object):
    def __init__(self, app=None):
        if app:
            self.init_app(app)

    def init_app(self, app):
        self.init_config(app)
        app.extensions['records'] = self

    def init_config(self, app):
        with_endpoints = app.config.get(
            'RECORDS_ENDPOINTS_ENABLED', True)
        for k in dir(config):
            if k.startswith('RECORDS_'):
                app.config.setdefault(k, getattr(config, k))
            elif k == 'SEARCH_UI_JSTEMPLATE_RESULTS':
                app.config['SEARCH_UI_JSTEMPLATE_RESULTS'] = getattr(
                    config, k)
            elif k == 'PIDSTORE_RECID_FIELD':
                app.config['PIDSTORE_RECID_FIELD'] = getattr(config, k)
            else:
                pass
                # for n in ['RECORDS_REST_ENDPOINTS', 'RECORDS_UI_ENDPOINTS',
                #           'RECORDS_REST_FACETS', 'RECORDS_REST_SORT_OPTIONS',
                #           'RECORDS_REST_DEFAULT_SORT']:
                #     if k == n and with_endpoints:
                #         app.config.setdefault(n, {})
                #         app.config[n].update(getattr(config, k))

        # set the draft schemas
        app.config.setdefault('INVENIO_RECORD_DRAFT_SCHEMAS', []).extend(
            config.INVENIO_RECORD_DRAFT_SCHEMAS)

        # set the draft endpoints
        app.config.setdefault('DRAFT_ENABLED_RECORDS_REST_ENDPOINTS', {}).update(
            config.DRAFT_ENABLED_RECORDS_REST_ENDPOINTS)

        app.config['RECORDS_REST_ENDPOINTS'] = {}

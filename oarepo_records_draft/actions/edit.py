from flask import redirect, url_for, jsonify
from flask.views import MethodView
from invenio_db import db
from invenio_records_rest.views import need_record_permission, pass_record
from invenio_search import current_search_client

from oarepo_records_draft.proxies import current_drafts
from oarepo_records_draft.types import RecordEndpointConfiguration, RecordContext


class EditRecordAction(MethodView):
    view_name = 'edit_{0}'

    def __init__(self,
                 endpoint: RecordEndpointConfiguration,
                 **kwargs):
        super().__init__(**kwargs)
        self.endpoint = endpoint

    @pass_record
    @need_record_permission('edit_permission_factory')
    def post(self, pid, record, **kwargs):
        with db.session.begin_nested():
            current_drafts.edit(RecordContext(record=record, record_pid=pid))
        db.session.commit()
        endpoint = 'invenio_records_rest.{0}_item'.format(self.endpoint.paired_endpoint.rest_name)
        url = url_for(endpoint, pid_value=pid.pid_value, _external=True)
        response = jsonify({
            "links": {
                "draft": url
            }
        })
        response.status_code = 302
        response.headers['location'] = url
        return response

    @property
    def edit_permission_factory(self):
        return self.endpoint.resolve('edit_permission_factory')

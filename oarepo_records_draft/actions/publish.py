from flask import url_for, jsonify
from flask.views import MethodView
from invenio_db import db
from invenio_records_rest.views import need_record_permission, pass_record

from oarepo_records_draft.proxies import current_drafts
from oarepo_records_draft.types import RecordEndpointConfiguration, RecordContext


class PublishRecordAction(MethodView):
    view_name = 'publish_{0}'

    def __init__(self,
                 endpoint: RecordEndpointConfiguration,
                 **kwargs):
        super().__init__(**kwargs)
        self.endpoint = endpoint

    @pass_record
    @need_record_permission('publish_permission_factory')
    def post(self, pid, record, **kwargs):
        with db.session.begin_nested():
            current_drafts.publish(RecordContext(record=record, record_pid=pid))
        db.session.commit()
        endpoint = 'invenio_records_rest.{0}_item'.format(self.endpoint.paired_endpoint.rest_name)
        url = url_for(endpoint, pid_value=pid.pid_value, _external=True)
        response = jsonify({
            "links": {
                "published": url
            }
        })
        response.status_code = 302
        response.headers['location'] = url
        return response

    @property
    def publish_permission_factory(self):
        return self.endpoint.resolve('publish_permission_factory')

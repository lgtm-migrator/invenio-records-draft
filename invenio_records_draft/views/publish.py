from flask import redirect, url_for
from flask.views import MethodView
from invenio_db import db
from invenio_indexer.api import RecordIndexer
from invenio_records_rest.views import need_record_permission, pass_record
from invenio_search import current_search_client

from invenio_records_draft.api import RecordContext
from invenio_records_draft.proxies import current_drafts


class PublishRecordAction(MethodView):
    view_name = 'publish_{0}'

    def __init__(self,
                 publish_permission_factory=None,
                 published_record_class=None,
                 published_pid_type=None,
                 published_endpoint_name=None,
                 **kwargs):
        super().__init__(**kwargs)
        self.publish_permission_factory = publish_permission_factory
        self.published_record_class = published_record_class
        self.published_pid_type = published_pid_type
        self.published_endpoint_name = published_endpoint_name

    @pass_record
    @need_record_permission('publish_permission_factory')
    def post(self, pid, record, **kwargs):
        current_drafts.publish(RecordContext(record=record, record_pid=pid))
        current_search_client.indices.refresh()
        current_search_client.indices.flush()
        endpoint = 'invenio_records_rest.{0}_item'.format(self.published_endpoint_name)
        return redirect(url_for(endpoint, pid_value=pid.pid_value, _external=True), code=302)

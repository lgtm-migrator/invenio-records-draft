from flask import redirect, url_for
from flask.views import MethodView
from invenio_db import db
from invenio_indexer.api import RecordIndexer
from invenio_records import Record
from invenio_records_rest.views import need_record_permission, pass_record
from invenio_search import current_search_client

from invenio_records_draft.record import DraftEnabledRecordMixin


class EditRecordAction(MethodView):
    view_name = 'edit_{0}'

    def __init__(self,
                 edit_permission_factory=None,
                 draft_pid_type=None,
                 draft_record_class=Record,
                 draft_endpoint_name=None,
                 **kwargs):
        super().__init__(**kwargs)
        self.edit_permission_factory = edit_permission_factory
        self.draft_pid_type = draft_pid_type
        self.draft_record_class = draft_record_class
        self.draft_endpoint_name = draft_endpoint_name

    @pass_record
    @need_record_permission('edit_permission_factory')
    def post(self, pid, record, **kwargs):
        with db.session.begin_nested():
            published_record, draft_record = DraftEnabledRecordMixin.draft_record(
                published_record=record, published_pid=pid,
                draft_pid_type=self.draft_pid_type, draft_record_class=self.draft_record_class)

        RecordIndexer().index(draft_record, refresh=True)
        RecordIndexer().index(published_record, refresh=True)
        current_search_client.indices.flush()  # TODO: find out why refresh above is not enough
        endpoint = 'invenio_records_rest.{0}_item'.format(self.draft_endpoint_name)
        return redirect(url_for(endpoint, pid_value=pid.pid_value, _external=True), code=302)

from flask_login import current_user
from flask_principal import Permission, RoleNeed
from invenio_records_rest.utils import allow_all
from invenio_search import RecordsSearch
from sample.indexer import RefreshingRecordIndexer

RECORD_PID = 'pid(recid,record_class="sample.record:SampleRecord")'


def allow_logged_in(*args, **kwargs):
    def can(self):
        try:
            return current_user.is_authenticated
        except:
            return False

    return type('Allow', (), {'can': can})()


RECORDS_DRAFT_ENDPOINTS = {
    'recid': dict(
        draft='drecid',
        pid_type='recid',
        pid_minter='recid',
        pid_fetcher='recid',
        default_endpoint_prefix=True,
        search_class=RecordsSearch,
        indexer_class=RefreshingRecordIndexer,
        search_index='sample',
        search_type=None,
        record_serializers={
            'application/json': 'oarepo_validate:json_response',
        },
        search_serializers={
            'application/json': 'oarepo_validate:json_search',
        },
        record_loaders={
            'application/json': 'oarepo_validate:json_loader',
            'application/json-patch+json': 'oarepo_validate:json_loader'
        },
        record_class='sample.record:SampleRecord',
        list_route='/records/',
        item_route='/records/<{0}:pid_value>'.format(RECORD_PID),
        default_media_type='application/json',
        max_result_window=10000,
        error_handlers=dict(),
        publish_permission_factory_imp=allow_logged_in,
        unpublish_permission_factory_imp=allow_logged_in,
        edit_permission_factory_imp=allow_logged_in,
    ),
    'drecid': dict(
        create_permission_factory_imp=allow_all,
        delete_permission_factory_imp=allow_all,
        update_permission_factory_imp=allow_all,
        record_class='sample.record:SampleDraftRecord',
        files=dict(
            put_file_factory=Permission(RoleNeed('role1')),
            get_file_factory=Permission(RoleNeed('role1')),
            delete_file_factory=Permission(RoleNeed('role1')),
        )
    )
}

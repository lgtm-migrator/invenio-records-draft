from invenio_indexer.api import RecordIndexer
from invenio_records_rest.utils import allow_all
from invenio_search import RecordsSearch

RECORD_PID = 'pid(recid,record_class="sample.record:SampleRecord")'

RECORDS_DRAFT_ENDPOINTS = {
    'recid': dict(
        draft='drecid',
        pid_type='recid',
        pid_minter='recid',
        pid_fetcher='recid',
        default_endpoint_prefix=True,
        search_class=RecordsSearch,
        indexer_class=RecordIndexer,
        search_index='records',
        search_type=None,
        record_serializers={
            'application/json': 'oarepo_validate:json_response',
        },
        search_serializers={
            'application/json': 'oarepo_validate:json_search',
        },
        record_loaders={
            'application/json': 'oarepo_validate:json_loader',
        },
        record_class='sample.record:SampleRecord',
        list_route='/records/',
        item_route='/records/<{0}:pid_value>'.format(RECORD_PID),
        default_media_type='application/json',
        max_result_window=10000,
        error_handlers=dict()
    ),
    'drecid': dict(
        create_permission_factory_imp=allow_all,
        delete_permission_factory_imp=allow_all,
        update_permission_factory_imp=allow_all,
    )
}

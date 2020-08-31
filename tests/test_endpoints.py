from oarepo_records_draft.proxies import current_drafts
from tests.helpers import dict_to_test


def test_endpoints(app):
    assert len(current_drafts.managed_records) == 1
    record = current_drafts.managed_records[0]
    assert dict_to_test(record.published.rest) == {
        'pid_type': 'recid',
        'pid_minter': 'recid',
        'pid_fetcher': 'recid',
        'default_endpoint_prefix': True,
        'search_class': 'RecordsSearch',
        'indexer_class': 'RefreshingRecordIndexer',
        'search_index': 'sample',
        'search_type': None,
        'record_serializers': {
            'application/json': 'oarepo_validate:json_response'
        },
        'search_serializers': {
            'application/json': 'oarepo_validate:json_search'
        },
        'record_loaders': {
            'application/json': 'oarepo_validate:json_loader',
            'application/json-patch+json': 'oarepo_validate:json_loader'
        },
        'record_class': 'sample.record:SampleRecord',
        'list_route': '/records/',
        'item_route': '/records/<pid(recid,record_class="sample.record:SampleRecord"):pid_value>',
        'default_media_type': 'application/json',
        'max_result_window': 10000,
        'create_permission_factory_imp': 'deny_all',
        'delete_permission_factory_imp': 'deny_all',
        'update_permission_factory_imp': 'deny_all',
        'list_permission_factory_imp': 'allow_all',
        'read_permission_factory_imp': 'check_elasticsearch',
        'links_factory_imp': 'PublishedLinksFactory'
    }
    assert dict_to_test(record.draft.rest) == {
        'record_class': 'sample.record:SampleRecordDraft',
        'default_endpoint_prefix': True,
        'default_media_type': 'application/json',
        'max_result_window': 10000,
        'record_loaders': {
            'application/json': 'oarepo_validate:json_loader',
            'application/json-patch+json': 'oarepo_validate:json_loader'
        },
        'record_serializers': {
            'application/json': 'oarepo_validate:json_response'
        },
        'search_serializers': {
            'application/json': 'oarepo_validate:json_search'
        },
        'search_class': 'RecordsSearch',
        'indexer_class': 'RefreshingRecordIndexer',
        'create_permission_factory_imp': 'allow_all',
        'delete_permission_factory_imp': 'allow_all',
        'update_permission_factory_imp': 'allow_all',
        'list_permission_factory_imp': 'allow_all',
        'read_permission_factory_imp': 'check_elasticsearch',
        'pid_type': 'drecid',
        'list_route': '/draft/records/',
        'item_route': '/draft/records/<pid(drecid,record_class="sample.record:SampleRecordDraft"):pid_value>',
        'pid_fetcher': 'drecid_fetcher',
        'pid_minter': 'drecid_minter',
        'search_index': 'draft-sample',
        'links_factory_imp': 'DraftLinksFactory'
    }
    assert record.published.rest_name == 'recid'
    assert record.draft.rest_name == 'drecid'

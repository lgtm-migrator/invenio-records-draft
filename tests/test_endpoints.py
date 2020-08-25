from oarepo_records_draft.proxies import current_drafts
from tests.helpers import dict_to_test


def test_endpoints(app):
    assert dict_to_test(current_drafts.endpoints) == {
        'recid': dict(
            published_name='recid',
            draft_name='drecid',
            published_endpoint={
                'pid_type': 'recid',
                'pid_minter': 'recid',
                'pid_fetcher': 'recid',
                'default_endpoint_prefix': True,
                'search_class': 'RecordsSearch',
                'indexer_class': 'RecordIndexer',
                'search_index': 'records',
                'search_type': None,
                'record_serializers': {
                    'application/json': 'oarepo_validate:json_response'
                },
                'search_serializers': {
                    'application/json': 'oarepo_validate:json_search'
                },
                'record_loaders': {
                    'application/json': 'oarepo_validate:json_loader'
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
            },
            draft_endpoint={
                'record_class': 'sample.record:SampleRecordDraft',
                'default_endpoint_prefix': True,
                'default_media_type': 'application/json',
                'max_result_window': 10000,
                'record_loaders': {
                    'application/json': 'oarepo_validate:json_loader'
                },
                'record_serializers': {
                    'application/json': 'oarepo_validate:json_response'
                },
                'search_serializers': {
                    'application/json': 'oarepo_validate:json_search'
                },
                'search_class': 'RecordsSearch',
                'indexer_class': 'RecordIndexer',
                'create_permission_factory_imp': 'allow_all',
                'delete_permission_factory_imp': 'allow_all',
                'update_permission_factory_imp': 'allow_all',
                'list_permission_factory_imp': 'allow_all',
                'read_permission_factory_imp': 'check_elasticsearch',
                'pid_type': 'drecid',
                'list_route': '/drafts/records/',
                'item_route': '/drafts/records/<pid(drecid,record_class="sample.record:SampleRecordDraft"):pid_value>',
                'pid_fetcher': 'drecid_fetcher',
                'pid_minter': 'drecid_minter',
                'search_index': 'draft-records',
                'links_factory_imp': 'DraftLinksFactory'
            }
        )
    }

from invenio_search import current_search, current_search_client
from invenio_search.cli import destroy, init

from invenio_records_draft.cli import make_mappings
from invenio_records_draft.proxies import current_drafts
from invenio_records_draft.utils import build_index_name, prefixed_search_index


def test_mapping(app, schemas):
    assert prefixed_search_index('draft-records') in current_search.aliases
    assert (
            prefixed_search_index('draft-records-record-v1.0.0')
            in current_search.aliases[prefixed_search_index('draft-records')]
    )
    assert prefixed_search_index('draft-records-record-v1.0.0') in current_search.mappings


def test_make_mappings(app):
    runner = app.test_cli_runner()
    result = runner.invoke(make_mappings)
    print(result.output)
    assert result.exit_code == 0
    for schema in app.config['INVENIO_RECORD_DRAFT_SCHEMAS']:
        schema = current_drafts.preprocess_config(schema)
        draft_mapping_file = schema['draft_mapping_file']
        assert f'Created mapping {draft_mapping_file}' in result.output


def test_publish_mappings(app, mappings):
    runner = app.test_cli_runner()
    result = runner.invoke(destroy, ['--yes-i-know', '--force'])
    if result.exit_code:
        print(result.output)
    assert result.exit_code == 0
    result = runner.invoke(init)
    if result.exit_code:
        print(result.output)
    assert result.exit_code == 0
    aliases = current_search_client.indices.get_alias("*")

    assert build_index_name('records-record-v1.0.0') in aliases
    assert build_index_name('draft-records-record-v1.0.0') in aliases

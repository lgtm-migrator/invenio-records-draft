from invenio_search import current_search_client


def test_es_mapping(app):
    current_search = app.extensions['invenio-search']

    print(current_search.cluster_version)
    assert 'draft-sample' in current_search.active_aliases

    list(current_search.delete(ignore=True))    # convert from generator
    list(current_search.create())               # convert from generator

    aliases = set()
    for v in current_search_client.indices.get_alias("*").values():
        aliases.update(v['aliases'].keys())
    assert 'test-sample' in aliases
    assert 'test-draft-sample' in aliases

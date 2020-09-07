from oarepo_records_draft.merge import draft_merger


def test_merger():
    assert draft_merger.merge([{'a': 1}], [{'b': 2}]) == [{'a': 1, 'b': 2}]

    assert draft_merger.merge([{'a': 1}], [{'b': 2}, {'c': 3}]) == [{'a': 1, 'b': 2}, {'c': 3}]

    assert draft_merger.merge([{'a': 1}], [{'a': 2}, {'c': 3}]) == [{'a': 2}, {'c': 3}]

    assert draft_merger.merge([{'a': 1, 'b': [1, 2, 3]}], [{'a': 1}, {'c': 3}]) == [
        {'a': 1, 'b': [1, 2, 3]}, {'c': 3}
    ]

    assert draft_merger.merge([{'a': 1, 'b': [1, 2, 3]}], [{'a': 1, 'b': [2, 3]}, {'c': 3}]) == [
        {'a': 1, 'b': [2, 3, 3]}, {'c': 3}
    ]

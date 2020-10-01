import pytest

from tests.test_files import can_import_files


@pytest.mark.skipif(can_import_files(), reason="Running without invenio files")
def test_uploader(app, db, client, draft_record, test_users):
    # create
    client.get('/test/login/1')

    resp = client.put('/draft/records/1/files/test-uploader', data=b'test', headers={
        'Content-Type': 'text/plain'
    })
    assert resp.status_code == 201
    assert resp.json == {
        'test-uploader': True,
        'url': 'http://localhost:5000/draft/records/1/files/_test'
    }

    resp = client.get('/draft/records/1/files/test-uploader')
    assert resp.status_code == 200
    assert resp.data == b'blah'

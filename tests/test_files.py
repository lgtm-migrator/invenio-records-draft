import pytest


def can_import_files():
    try:
        import invenio_records_files
        return False
    except:
        return True


pytestmark = pytest.mark.skipif(can_import_files(), reason="No invenio files imported")


def test_upload_links(app, db, client, draft_record):
    resp = client.get('/draft/records/1')
    assert resp.status_code == 200
    assert resp.json['links'] == {
        'self': 'http://localhost:5000/draft/records/1',
        'attachments': 'http://localhost:5000/draft/records/1/attachments'
    }


def test_upload_attachment_not_authenticated(app, db, client, draft_record):
    resp = client.put('/draft/records/1/attachments/test.txt', data=b'test', headers={
        'Content-Type': 'text/plain'
    })
    assert resp.status_code == 401


def test_rest_attachment_authenticated(app, db, client, draft_record, test_users):
    # create

    client.get('/test/login/3')
    resp = client.put('/draft/records/1/attachments/test.txt', data=b'test', headers={
        'Content-Type': 'text/plain'
    })
    assert resp.status_code == 403

    client.get('/test/logout')
    client.get('/test/login/1')

    resp = client.put('/draft/records/1/attachments/test.txt', data=b'test', headers={
        'Content-Type': 'text/plain'
    })
    assert resp.status_code == 201
    uploaded_file = resp.json
    assert 'bucket' in uploaded_file
    assert uploaded_file['checksum'] == 'md5:098f6bcd4621d373cade4e832627b4f6'
    assert uploaded_file['key'] == 'test.txt'
    assert 'file_id' in uploaded_file
    assert 'version_id' in uploaded_file
    assert uploaded_file['size'] == 4

    # listing

    client.get('/test/logout')
    client.get('/test/login/3')

    resp = client.get('/draft/records/1/attachments')
    assert resp.status_code == 200
    assert resp.json == []  # user 3 has no rights for attachments

    client.get('/test/logout')
    client.get('/test/login/1')

    resp = client.get('/draft/records/1/attachments')
    assert resp.status_code == 200
    assert resp.json == [
        uploaded_file
    ]

    # download

    client.get('/test/logout')
    client.get('/test/login/3')

    resp = client.get('/draft/records/1/attachments/test.txt')
    assert resp.status_code == 403

    client.get('/test/logout')
    client.get('/test/login/1')

    resp = client.get('/draft/records/1/attachments/test.txt')
    assert resp.status_code == 200
    assert resp.data == b'test'

    # delete

    client.get('/test/logout')
    client.get('/test/login/3')

    resp = client.delete('/draft/records/1/attachments/test.txt')
    assert resp.status_code == 403

    client.get('/test/logout')
    client.get('/test/login/1')

    resp = client.delete('/draft/records/1/attachments/test.txt')
    assert resp.status_code == 200
    assert resp.json == uploaded_file

import uuid

import pytest
from invenio_pidstore.errors import PIDDoesNotExistError
from invenio_pidstore.models import PersistentIdentifier, PIDStatus
from invenio_records import Record

from invenio_records_draft.record import (
    DraftEnabledRecordMixin,
    InvalidRecordException,
    MarshmallowValidator,
)


class TestDraftRecord(DraftEnabledRecordMixin, Record):
    schema = None

    def validate(self, **kwargs):
        self['$schema'] = self.schema
        return super().validate(**kwargs)

    draft_validator = MarshmallowValidator(
        'sample.records.marshmallow:MetadataSchemaV1',
        'records/record-v1.0.0.json'
    )


class TestPublishedRecord(DraftEnabledRecordMixin, Record):
    schema = None

    def validate(self, **kwargs):
        self['$schema'] = self.schema
        return super().validate(**kwargs)


def test_publish_record(app, db, schemas):
    TestDraftRecord.schema = schemas['draft']
    TestPublishedRecord.schema = schemas['published']
    with db.session.begin_nested():
        draft_uuid = uuid.uuid4()

        rec = TestDraftRecord.create({
            'id': '1'
        }, id_=draft_uuid)
        draft_pid = PersistentIdentifier.create(
            pid_type='drecid', pid_value='1', status=PIDStatus.REGISTERED,
            object_type='rec', object_uuid=draft_uuid
        )

        with pytest.raises(InvalidRecordException):
            # title is required but not in rec, so should fail
            rec.publish(draft_pid,
                        TestPublishedRecord, 'recid',
                        remove_draft=True)

        with pytest.raises(PIDDoesNotExistError):
            # no record should be created
            PersistentIdentifier.get(pid_type='recid', pid_value='1')

        # make the record valid
        rec['title'] = 'blah'
        rec.commit()

        # and publish it again
        rec.publish(draft_pid,
                    TestPublishedRecord, 'recid',
                    remove_draft=True)

        # draft should be gone
        draft_pid = PersistentIdentifier.get(pid_type='drecid', pid_value='1')
        assert draft_pid.status == PIDStatus.DELETED
        rec = TestDraftRecord.get_record(draft_uuid, with_deleted=True)
        assert rec.model.json is None

        published_pid = PersistentIdentifier.get(pid_type='recid', pid_value='1')
        assert published_pid.status == PIDStatus.REGISTERED
        rec = TestPublishedRecord.get_record(published_pid.object_uuid)
        assert rec.model.json is not None


def test_publish_record_marshmallow(app, db, schemas):
    TestDraftRecord.schema = schemas['draft']
    TestPublishedRecord.schema = schemas['published']
    with db.session.begin_nested():
        draft_uuid = uuid.uuid4()

        rec = TestDraftRecord.create({
            'id': '1'
        }, id_=draft_uuid)
        draft_pid = PersistentIdentifier.create(
            pid_type='drecid', pid_value='1', status=PIDStatus.REGISTERED,
            object_type='rec', object_uuid=draft_uuid
        )

        with pytest.raises(InvalidRecordException):
            # title is required but not in rec, so should fail
            rec.publish(draft_pid,
                        TestPublishedRecord, 'recid',
                        remove_draft=True)

        with pytest.raises(PIDDoesNotExistError):
            # no record should be created
            PersistentIdentifier.get(pid_type='recid', pid_value='1')

        # make the record valid
        rec['title'] = 'blah'
        rec.commit()

        assert rec['invenio_draft_validation']['valid']

        # and publish it again
        rec.publish(draft_pid,
                    TestPublishedRecord, 'recid',
                    remove_draft=True)

        # draft should be gone
        draft_pid = PersistentIdentifier.get(pid_type='drecid', pid_value='1')
        assert draft_pid.status == PIDStatus.DELETED
        rec = TestDraftRecord.get_record(draft_uuid, with_deleted=True)
        assert rec.model.json is None

        published_pid = PersistentIdentifier.get(pid_type='recid', pid_value='1')
        assert published_pid.status == PIDStatus.REGISTERED
        rec = TestPublishedRecord.get_record(published_pid.object_uuid)
        assert rec.model.json is not None


def test_publish_record_with_previous_version(app, db, schemas):
    TestDraftRecord.schema = schemas['draft']
    TestPublishedRecord.schema = schemas['published']
    with db.session.begin_nested():
        published_uuid = uuid.uuid4()
        PersistentIdentifier.create(
            pid_type='recid', pid_value='1', status=PIDStatus.REGISTERED,
            object_type='rec', object_uuid=published_uuid
        )
        published_record = TestPublishedRecord.create({
            'id': '1',
            'title': '11'
        }, id_=published_uuid)
        assert published_record.revision_id == 0

        draft_uuid = uuid.uuid4()
        draft_pid = PersistentIdentifier.create(
            pid_type='drecid', pid_value='1', status=PIDStatus.REGISTERED,
            object_type='rec', object_uuid=draft_uuid
        )
        draft_record = TestDraftRecord.create({
            'id': '1',
            'title': '22'
        }, id_=draft_uuid)
        assert draft_record.revision_id == 0

        print(draft_record['invenio_draft_validation'])

        # and publish it again
        draft_record.publish(draft_pid,
                             TestPublishedRecord, 'recid',
                             remove_draft=True)

        # draft should be gone
        draft_pid = PersistentIdentifier.get(pid_type='drecid', pid_value='1')
        assert draft_pid.status == PIDStatus.DELETED
        rec = TestDraftRecord.get_record(draft_uuid, with_deleted=True)
        assert rec.model.json is None

        published_pid = PersistentIdentifier.get(pid_type='recid', pid_value='1')
        assert published_pid.status == PIDStatus.REGISTERED
        rec = TestPublishedRecord.get_record(published_pid.object_uuid)
        assert rec.model.json is not None
        assert rec['title'] == '22'
        assert rec.revision_id == 1


def test_publish_deleted_published(app, db, schemas):
    TestDraftRecord.schema = schemas['draft']
    TestPublishedRecord.schema = schemas['published']
    with db.session.begin_nested():
        published_uuid = uuid.uuid4()
        published_record = TestPublishedRecord.create({
            'id': '1',
            'title': '11'
        }, id_=published_uuid)
        published_pid = PersistentIdentifier.create(
            pid_type='recid', pid_value='1', status=PIDStatus.REGISTERED,
            object_type='rec', object_uuid=published_uuid
        )
        assert published_record.revision_id == 0

        draft_uuid = uuid.uuid4()
        rec = TestDraftRecord.create({
            'id': '1',
            'title': '22'
        }, id_=draft_uuid)
        draft_pid = PersistentIdentifier.create(
            pid_type='drecid', pid_value='1', status=PIDStatus.REGISTERED,
            object_type='rec', object_uuid=draft_uuid
        )

    with db.session.begin_nested():
        published_record.delete()
        published_pid.status = PIDStatus.DELETED
        db.session.add(published_pid)

    with db.session.begin_nested():
        rec = TestDraftRecord.get_record(draft_uuid)
        draft_pid = PersistentIdentifier.get(pid_type='drecid', pid_value='1')
        rec.publish(draft_pid,
                    TestPublishedRecord, 'recid',
                    remove_draft=True)

    with db.session.begin_nested():
        # draft should be gone
        draft_pid = PersistentIdentifier.get(pid_type='drecid', pid_value='1')
        assert draft_pid.status == PIDStatus.DELETED
        rec = TestDraftRecord.get_record(draft_uuid, with_deleted=True)
        assert rec.model.json is None

        published_pid = PersistentIdentifier.get(pid_type='recid', pid_value='1')
        assert published_pid.status == PIDStatus.REGISTERED
        rec = TestPublishedRecord.get_record(published_pid.object_uuid)
        assert rec['title'] == '22'
        # revision 0 original, 1 deleted, 2 temporarily reverted to orig, 3 published
        assert rec.revision_id == 3


def test_publish_redirected_published(app, db, schemas):
    TestDraftRecord.schema = schemas['draft']
    TestPublishedRecord.schema = schemas['published']
    with db.session.begin_nested():
        published_uuid = uuid.uuid4()
        published_record = TestPublishedRecord.create({
            'id': '1',
            'title': '11'
        }, id_=published_uuid)
        published_pid = PersistentIdentifier.create(
            pid_type='recid', pid_value='1', status=PIDStatus.REGISTERED,
            object_type='rec', object_uuid=published_uuid
        )
        assert published_record.revision_id == 0

        draft_uuid = uuid.uuid4()
        rec = TestDraftRecord.create({
            'id': '1',
            'title': '22'
        }, id_=draft_uuid)
        draft_pid = PersistentIdentifier.create(
            pid_type='drecid', pid_value='1', status=PIDStatus.REGISTERED,
            object_type='rec', object_uuid=draft_uuid
        )

    with db.session.begin_nested():
        published_record.delete()
        published_pid.status = PIDStatus.REDIRECTED
        db.session.add(published_pid)

    with db.session.begin_nested():
        rec = TestDraftRecord.get_record(draft_uuid)
        draft_pid = PersistentIdentifier.get(pid_type='drecid', pid_value='1')
        with pytest.raises(NotImplementedError):
            rec.publish(draft_pid,
                        TestPublishedRecord, 'recid',
                        remove_draft=True)


def test_unpublish_record(app, db, schemas):
    TestDraftRecord.schema = schemas['draft']
    TestPublishedRecord.schema = schemas['published']
    with db.session.begin_nested():
        published_uuid = uuid.uuid4()
        published_record = TestPublishedRecord.create({
            'id': '1',
            'title': '11'
        }, id_=published_uuid)
        published_pid = PersistentIdentifier.create(
            pid_type='recid', pid_value='1', status=PIDStatus.REGISTERED,
            object_type='rec', object_uuid=published_uuid
        )
        assert published_record.revision_id == 0

        published_record.unpublish(published_pid,
                                   TestDraftRecord, 'drecid')

        # published version should be gone
        published_pid = PersistentIdentifier.get(pid_type='recid', pid_value='1')
        assert published_pid.status == PIDStatus.DELETED
        rec = TestDraftRecord.get_record(published_uuid, with_deleted=True)
        assert rec.model.json is None

        draft_pid = PersistentIdentifier.get(pid_type='drecid', pid_value='1')
        assert draft_pid.status == PIDStatus.REGISTERED
        rec = TestDraftRecord.get_record(draft_pid.object_uuid)
        assert rec.model.json is not None
        assert rec['title'] == '11'
        assert rec.revision_id == 0


def test_unpublish_record_existing_draft(app, db, schemas):
    TestDraftRecord.schema = schemas['draft']
    TestPublishedRecord.schema = schemas['published']
    with db.session.begin_nested():
        published_uuid = uuid.uuid4()
        published_record = TestPublishedRecord.create({
            'id': '1',
            'title': '11'
        }, id_=published_uuid)
        published_pid = PersistentIdentifier.create(
            pid_type='recid', pid_value='1', status=PIDStatus.REGISTERED,
            object_type='rec', object_uuid=published_uuid
        )
        assert published_record.revision_id == 0

        draft_uuid = uuid.uuid4()
        draft_record = TestDraftRecord.create({
            'id': '1',
            'title': '22'
        }, id_=draft_uuid)
        draft_pid = PersistentIdentifier.create(
            pid_type='drecid', pid_value='1', status=PIDStatus.REGISTERED,
            object_type='rec', object_uuid=draft_uuid
        )
        assert draft_record.revision_id == 0

        published_record.unpublish(published_pid,
                                   TestDraftRecord, 'drecid')

        # published version should be gone
        published_pid = PersistentIdentifier.get(pid_type='recid', pid_value='1')
        assert published_pid.status == PIDStatus.DELETED
        rec = TestDraftRecord.get_record(published_uuid, with_deleted=True)
        assert rec.model.json is None

        draft_pid = PersistentIdentifier.get(pid_type='drecid', pid_value='1')
        assert draft_pid.status == PIDStatus.REGISTERED
        rec = TestDraftRecord.get_record(draft_pid.object_uuid)
        assert rec.model.json is not None
        assert rec['title'] == '22'  # should not be changed on a newer record
        assert rec.revision_id == 0


def test_unpublish_record_redirected_draft(app, db, schemas):
    TestDraftRecord.schema = schemas['draft']
    TestPublishedRecord.schema = schemas['published']
    with db.session.begin_nested():
        published_uuid = uuid.uuid4()
        published_record = TestPublishedRecord.create({
            'id': '1',
            'title': '11'
        }, id_=published_uuid)
        published_pid = PersistentIdentifier.create(
            pid_type='recid', pid_value='1', status=PIDStatus.REGISTERED,
            object_type='rec', object_uuid=published_uuid
        )
        assert published_record.revision_id == 0

        draft_uuid = uuid.uuid4()
        draft_record = TestDraftRecord.create({
            'id': '1',
            'title': '22'
        }, id_=draft_uuid)
        draft_pid = PersistentIdentifier.create(
            pid_type='drecid', pid_value='1', status=PIDStatus.REGISTERED,
            object_type='rec', object_uuid=draft_uuid
        )
        assert draft_record.revision_id == 0

    with db.session.begin_nested():
        draft_record.delete()
        draft_pid.status = PIDStatus.REDIRECTED
        db.session.add(draft_pid)

    with db.session.begin_nested():
        with pytest.raises(NotImplementedError):
            published_record.unpublish(published_pid,
                                       TestDraftRecord, 'drecid')


def test_draft_record(app, db, schemas):
    TestDraftRecord.schema = schemas['draft']
    TestPublishedRecord.schema = schemas['published']
    with db.session.begin_nested():
        published_uuid = uuid.uuid4()
        published_record = TestPublishedRecord.create({
            'id': '1',
            'title': '11'
        }, id_=published_uuid)
        published_pid = PersistentIdentifier.create(
            pid_type='recid', pid_value='1', status=PIDStatus.REGISTERED,
            object_type='rec', object_uuid=published_uuid
        )
        assert published_record.revision_id == 0

        published_record.draft(published_pid,
                               TestDraftRecord, 'drecid')

        # published version should be there unchanged
        published_pid = PersistentIdentifier.get(pid_type='recid', pid_value='1')
        assert published_pid.status == PIDStatus.REGISTERED
        rec = TestDraftRecord.get_record(published_uuid, with_deleted=True)
        assert rec['title'] == '11'
        assert rec.revision_id == 0

        # draft version should appear
        draft_pid = PersistentIdentifier.get(pid_type='drecid', pid_value='1')
        assert draft_pid.status == PIDStatus.REGISTERED
        rec = TestDraftRecord.get_record(draft_pid.object_uuid)
        assert rec.model.json is not None
        assert rec['title'] == '11'
        assert rec.revision_id == 0


def test_draft_record_existing_draft(app, db, schemas):
    TestDraftRecord.schema = schemas['draft']
    TestPublishedRecord.schema = schemas['published']
    with db.session.begin_nested():
        published_uuid = uuid.uuid4()
        published_record = TestPublishedRecord.create({
            'id': '1',
            'title': '11'
        }, id_=published_uuid)
        published_pid = PersistentIdentifier.create(
            pid_type='recid', pid_value='1', status=PIDStatus.REGISTERED,
            object_type='rec', object_uuid=published_uuid
        )
        assert published_record.revision_id == 0

        draft_uuid = uuid.uuid4()
        draft_record = TestDraftRecord.create({
            'id': '1',
            'title': '22'
        }, id_=draft_uuid)
        draft_pid = PersistentIdentifier.create(
            pid_type='drecid', pid_value='1', status=PIDStatus.REGISTERED,
            object_type='rec', object_uuid=draft_uuid
        )
        assert draft_record.revision_id == 0

        published_record.draft(published_pid,
                               TestDraftRecord, 'drecid')

        # published version should be there unchanged
        published_pid = PersistentIdentifier.get(pid_type='recid', pid_value='1')
        assert published_pid.status == PIDStatus.REGISTERED
        rec = TestDraftRecord.get_record(published_uuid, with_deleted=True)
        assert rec['title'] == '11'
        assert rec.revision_id == 0

        # draft version should be there unchanged
        draft_pid = PersistentIdentifier.get(pid_type='drecid', pid_value='1')
        assert draft_pid.status == PIDStatus.REGISTERED
        rec = TestDraftRecord.get_record(draft_pid.object_uuid)
        assert rec.model.json is not None
        assert rec['title'] == '22'  # should not be changed on a newer record
        assert rec.revision_id == 0


def test_draft_record_deleted_draft(app, db, schemas):
    TestDraftRecord.schema = schemas['draft']
    TestPublishedRecord.schema = schemas['published']
    with db.session.begin_nested():
        published_uuid = uuid.uuid4()
        published_record = TestPublishedRecord.create({
            'id': '1',
            'title': '11'
        }, id_=published_uuid)
        published_pid = PersistentIdentifier.create(
            pid_type='recid', pid_value='1', status=PIDStatus.REGISTERED,
            object_type='rec', object_uuid=published_uuid
        )
        assert published_record.revision_id == 0

        draft_uuid = uuid.uuid4()
        draft_record = TestDraftRecord.create({
            'id': '1',
            'title': '22'
        }, id_=draft_uuid)
        draft_pid = PersistentIdentifier.create(
            pid_type='drecid', pid_value='1', status=PIDStatus.REGISTERED,
            object_type='rec', object_uuid=draft_uuid
        )
        assert draft_record.revision_id == 0

    with db.session.begin_nested():
        draft_record.delete()
        draft_pid.status = PIDStatus.DELETED
        db.session.add(draft_pid)

    with db.session.begin_nested():
        published_record.draft(published_pid,
                               TestDraftRecord, 'drecid')

        # published version should be there unchanged
        published_pid = PersistentIdentifier.get(pid_type='recid', pid_value='1')
        assert published_pid.status == PIDStatus.REGISTERED
        rec = TestDraftRecord.get_record(published_uuid, with_deleted=True)
        assert rec['title'] == '11'
        assert rec.revision_id == 0

        # draft version should be there unchanged
        draft_pid = PersistentIdentifier.get(pid_type='drecid', pid_value='1')
        assert draft_pid.status == PIDStatus.REGISTERED
        rec = TestDraftRecord.get_record(draft_pid.object_uuid)
        assert rec.model.json is not None
        assert rec['title'] == '11'
        assert rec.revision_id == 3

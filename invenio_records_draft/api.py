import uuid
from collections import namedtuple
from typing import List, Dict

from invenio_db import db
from invenio_indexer.api import RecordIndexer
from invenio_pidstore.errors import PIDDoesNotExistError
from invenio_pidstore.models import PersistentIdentifier, PIDStatus

from invenio_records_draft.record import InvalidRecordException, DraftEnabledRecordMixin
from invenio_records_draft.signals import collect_records, CollectAction, check_can_publish, before_publish, \
    after_publish, before_record_published
import logging

logger = logging.getLogger('invenio-records-draft.api')


class RecordContext:
    def __init__(self, record_pid, record, **kwargs):
        self.record_pid = record_pid
        self.record = record
        for k, v in kwargs.items():
            setattr(self, k, v)

    @property
    def record_uuid(self):
        return self.record.id


RecordType = namedtuple('RecordType', 'record_class pid_type')


class RecordDraftApi:

    def __init__(self):
        self.pid_type_to_record_class = {}
        self.draft_pidtype_to_published: Dict[str, RecordType] = {}

    @staticmethod
    def collect_records_for_action(record: RecordContext, action) -> List[RecordContext]:
        records_to_publish_map = set()
        records_to_publish = [record]
        records_to_publish_queue = [record]
        records_to_publish_map.add(record.record_uuid)

        while records_to_publish_queue:
            rec = records_to_publish_queue.pop(0)
            for _, collected_records in collect_records.send(record, record=rec, action=action):
                collect_record: RecordContext
                for collect_record in collected_records:
                    if collect_record.record_uuid in records_to_publish_map:
                        continue
                    records_to_publish_map.add(collect_record.record_uuid)
                    records_to_publish.append(collect_record)
                    records_to_publish_queue.append(collect_record)
        return records_to_publish

    def publish(self, record: RecordContext):
        with db.session.begin_nested():
            # collect all records to be published (for example, references etc)
            collected_records = self.collect_records_for_action(record, CollectAction.PUBLISH)

            # for each collected record, check if can be published
            for draft_record in collected_records:
                check_can_publish.send(record, draft_record)

            before_publish.send(collected_records)

            result = []
            # publish in reversed order
            for draft_record in reversed(collected_records):
                draft_pid = draft_record.record_pid
                published_record_class = self.published_record_class_for_draft_pid(draft_pid)
                published_record_pid_type = self.published_record_pid_type_for_draft_pid(draft_pid)
                published_record, published_pid = self.publish_record_internal(
                    draft_record.record, draft_pid,
                    published_record_class, published_record_pid_type
                )
                published_record_context = RecordContext(published_record, published_pid)
                result.append((draft_record, published_record_context))

            after_publish.send(result)

            for draft_record, published_record in result:
                # delete the record
                draft_record.record.delete()
                # mark all object pids as deleted
                all_pids = PersistentIdentifier.query.filter(
                    PersistentIdentifier.object_type == draft_record.record_pid.draft_pid.object_type,
                    PersistentIdentifier.object_uuid == draft_record.record_pid.draft_pid.object_uuid,
                ).all()
                for rec_pid in all_pids:
                    if not rec_pid.is_deleted():
                        rec_pid.delete()

                published_record.record.commit()
        db.session.commit()
        for _, published_record in result:
            RecordIndexer().index(published_record)

        return result

    def pid_for_record(self, rec):
        pid_list = PersistentIdentifier.query.filter_by(object_type='rec', object_uuid=rec.id)
        for pid in pid_list:
            if pid.pid_type in self.pid_type_to_record_class:
                return pid

    def published_record_class_for_draft_pid(self, draft_pid):
        return self.draft_pidtype_to_published[draft_pid.pid_type].record_class

    def published_record_pid_type_for_draft_pid(self, draft_pid):
        return self.draft_pidtype_to_published[draft_pid.pid_type].pid_type

    def publish_record_internal(self, draft_record, draft_pid,
                                published_record_class,
                                published_pid_type):

        # clone metadata
        metadata = dict(draft_record)
        if 'invenio_draft_validation' in metadata:
            if not metadata['invenio_draft_validation']['valid']:
                raise InvalidRecordException('Can not publish invalid record',
                                             errors=metadata['invenio_draft_validation']['errors'])
            del metadata['invenio_draft_validation']

        # note: the passed record must fill in the schema otherwise the published record will be
        # without any schema and will not get indexed
        metadata.pop('$schema', None)

        try:
            published_pid = PersistentIdentifier.get(published_pid_type, draft_pid.pid_value)

            if published_pid.status == PIDStatus.DELETED:
                # the draft is deleted, resurrect it
                # change the pid to registered
                published_pid.status = PIDStatus.REGISTERED
                db.session.add(published_pid)

                # and fetch the draft record and update its metadata
                return self._update_published_record(
                    published_pid, metadata, None, published_record_class)

            elif published_pid.status == PIDStatus.REGISTERED:
                # fetch the draft record and update its metadata
                # if it is older than the published one
                return self._update_published_record(
                    published_pid, metadata,
                    draft_record.updated, published_record_class)

            raise NotImplementedError('Can not unpublish record to draft record '
                                      'with pid status %s. Only registered or deleted '
                                      'statuses are implemented', published_pid.status)
        except PIDDoesNotExistError:
            pass

        # create a new draft record. Do not call minter as the pid value will be the
        # same as the pid value of the published record
        id = uuid.uuid4()
        before_record_published.send(draft_record, metadata=metadata)
        published_record = published_record_class.create(metadata, id_=id)
        published_pid = PersistentIdentifier.create(pid_type=published_pid_type,
                                                    pid_value=draft_pid.pid_value, status=PIDStatus.REGISTERED,
                                                    object_type='rec', object_uuid=id)
        return published_record, published_pid

    def _update_published_record(self, published_pid, metadata,
                                 timestamp, published_record_class):
        published_record = published_record_class.get_record(
            published_pid.object_uuid, with_deleted=True)
        # if deleted, revert to last non-deleted revision
        revision_id = published_record.revision_id
        while published_record.model.json is None and revision_id > 0:
            revision_id -= 1
            published_record.revert(revision_id)

        if not timestamp or published_record.updated < timestamp:
            before_record_published.send(published_record, metadata=metadata)
            published_record.update(metadata)
            if not published_record['$schema']:  # pragma no cover
                logger.warning('Updated draft record does not have a $schema metadata. '
                               'Please use a Record implementation that adds $schema '
                               '(for example in validate() method). Draft PID Type %s',
                               published_pid.pid_type)

        return published_record, published_pid

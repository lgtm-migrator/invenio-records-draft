import functools
import logging
import uuid
from typing import List, Union

import invenio_indexer.config
from invenio_base.signals import app_loaded
from invenio_db import db
from invenio_indexer.api import RecordIndexer
from invenio_indexer.utils import schema_to_index
from invenio_pidstore.errors import PIDDoesNotExistError
from invenio_pidstore.models import PersistentIdentifier, PIDStatus
from invenio_records import Record
from invenio_search import current_search, current_search_client
from oarepo_validate.record import AllowedSchemaMixin

from oarepo_records_draft.mappings import setup_draft_mappings
from oarepo_records_draft.types import DraftManagedRecords
from .exceptions import InvalidRecordException
from .signals import collect_records, CollectAction, check_can_publish, before_publish, after_publish, check_can_edit, \
    before_edit, after_edit, check_can_unpublish, before_unpublish, after_unpublish, before_publish_record, \
    before_unpublish_record
from .types import RecordContext, Endpoints
from .views import register_blueprint

logger = logging.getLogger(__name__)


def setup_indexer(app):
    if app.config['INDEXER_RECORD_TO_INDEX'] == invenio_indexer.config.INDEXER_RECORD_TO_INDEX:
        app.config['INDEXER_RECORD_TO_INDEX'] = 'oarepo_records_draft.record.record_to_index'


class RecordsDraftState:
    def __init__(self, app):
        self.app = app
        self.managed_records = None  # type: DraftManagedRecords

    def app_loaded(self, _sender, app=None, **kwargs):
        with app.app_context():
            app.config['RECORDS_REST_ENDPOINTS'].setup_endpoints()
            self._collect_mappings()
            setup_indexer(app)
            setup_draft_mappings(self.managed_records, app)
            register_blueprint(app, self)

    def _collect_mappings(self):
        index_names = current_search.mappings.keys()
        for rec in self.managed_records:
            published_record = rec.published.record_class
            if issubclass(published_record, AllowedSchemaMixin):
                published_record._prepare_schemas()

            for json_schema in published_record.ALLOWED_SCHEMAS:
                index_name = schema_to_index(json_schema, index_names=index_names)[0]
                rec.published.set_index(json_schema, index_name)
                rec.draft.set_index(json_schema, index_name)

    @staticmethod
    def collect_records_for_action(record: RecordContext, action) -> List[RecordContext]:
        records_to_publish_map = set()
        records_to_publish = [record]
        records_to_publish_queue = [record]
        records_to_publish_map.add(record.record_uuid)

        while records_to_publish_queue:
            rec = records_to_publish_queue.pop(0)
            for _, collected_records in collect_records.send(record,
                                                             record=rec,
                                                             action=action):
                # collect_record: RecordContext
                for collect_record in (collected_records or []):
                    if collect_record.record_uuid in records_to_publish_map:
                        continue
                    records_to_publish_map.add(collect_record.record_uuid)
                    records_to_publish.append(collect_record)
                    records_to_publish_queue.append(collect_record)
        return records_to_publish

    def endpoint_for_pid(self, pid):
        return self.endpoint_for_pid_type(pid.pid_type)

    def endpoint_for_record(self, record):
        return self.endpoint_for_record_class(type(record))

    @functools.lru_cache(maxsize=32)
    def endpoint_for_record_class(self, clz):
        return self.managed_records.by_record_class(clz)

    @functools.lru_cache(maxsize=32)
    def endpoint_for_pid_type(self, pid_type):
        return self.managed_records.by_pid_type[pid_type]

    def publish(self, record: Union[RecordContext, Record], record_pid=None):
        if isinstance(record, Record):
            record = RecordContext(record=record, record_pid=record_pid)

        with db.session.begin_nested():
            # collect all records to be published (for example, references etc)
            collected_records = self.collect_records_for_action(record, CollectAction.PUBLISH)

            # for each collected record, check if can be published
            for draft_record in collected_records:
                check_can_publish.send(record, record=draft_record)

            before_publish.send(collected_records)

            result = []
            # publish in reversed order
            for draft_record in reversed(collected_records):
                draft_pid = draft_record.record_pid
                endpoint = self.endpoint_for_pid_type(draft_pid.pid_type)
                assert endpoint.published is False
                published_record_class = endpoint.paired_endpoint.record_class
                published_record_pid_type = endpoint.paired_endpoint.rest_name
                published_record, published_pid = self.publish_record_internal(
                    draft_record, published_record_class,
                    published_record_pid_type, collected_records
                )
                published_record_context = RecordContext(record=published_record,
                                                         record_pid=published_pid)
                result.append((draft_record, published_record_context))

            after_publish.send(result)

            for draft_record, published_record in result:
                # delete the record
                draft_record.record.delete()
                try:
                    RecordIndexer().delete(draft_record.record, refresh=True)
                except:
                    logger.debug('Error deleting record', draft_record.record_pid)
                RecordIndexer().index(published_record.record)
                # mark all object pids as deleted
                all_pids = PersistentIdentifier.query.filter(
                    PersistentIdentifier.object_type == draft_record.record_pid.object_type,
                    PersistentIdentifier.object_uuid == draft_record.record_pid.object_uuid,
                ).all()
                for rec_pid in all_pids:
                    if not rec_pid.is_deleted():
                        rec_pid.delete()

                published_record.record.commit()

        current_search_client.indices.refresh()
        current_search_client.indices.flush()

        return result

    def edit(self, record: Union[RecordContext, Record], record_pid=None):
        if isinstance(record, Record):
            record = RecordContext(record=record, record_pid=record_pid)

        with db.session.begin_nested():
            # collect all records to be draft (for example, references etc)
            collected_records = self.collect_records_for_action(record, CollectAction.EDIT)

            # for each collected record, check if can be draft
            for published_record in collected_records:
                check_can_edit.send(record, record=published_record)

            before_edit.send(collected_records)

            result = []
            # publish in reversed order
            for published_record in reversed(collected_records):
                published_pid = published_record.record_pid
                endpoint = self.endpoint_for_pid_type(published_pid.pid_type)
                assert endpoint.published
                draft_record_class = endpoint.paired_endpoint.record_class
                draft_record_pid_type = endpoint.paired_endpoint.rest_name
                draft_record, draft_pid = self.draft_record_internal(
                    published_record, published_pid,
                    draft_record_class, draft_record_pid_type,
                    collected_records
                )
                draft_record_context = RecordContext(record=draft_record, record_pid=draft_pid)
                result.append((published_record, draft_record_context))

            after_edit.send(result)

            for published_record, draft_record in result:
                draft_record.record.commit()
                RecordIndexer().index(draft_record.record)

        current_search_client.indices.refresh()
        current_search_client.indices.flush()

        return result

    def unpublish(self, record: Union[RecordContext, Record], record_pid=None):
        if isinstance(record, Record):
            record = RecordContext(record=record, record_pid=record_pid)

        with db.session.begin_nested():
            # collect all records to be draft (for example, references etc)
            collected_records = self.collect_records_for_action(record, CollectAction.UNPUBLISH)

            # for each collected record, check if can be draft
            for published_record in collected_records:
                check_can_unpublish.send(record, record=published_record)

            before_unpublish.send(collected_records)

            result = []
            # publish in reversed order
            for published_record in reversed(collected_records):
                published_pid = published_record.record_pid
                endpoint = self.endpoint_for_pid_type(published_pid.pid_type)
                assert endpoint.published
                draft_record_class = endpoint.paired_endpoint.record_class
                draft_record_pid_type = endpoint.paired_endpoint.rest_name
                draft_record, draft_pid = self.draft_record_internal(
                    published_record, published_pid,
                    draft_record_class, draft_record_pid_type,
                    collected_records
                )
                draft_record_context = RecordContext(record=draft_record, record_pid=draft_pid)
                result.append((published_record, draft_record_context))

            after_unpublish.send(result)

            for published_record, draft_record in result:
                # delete the record
                published_record.record.delete()
                try:
                    RecordIndexer().delete(published_record.record, refresh=True)
                except:
                    logger.debug('Error deleting record', published_record.record_pid)
                draft_record.record.commit()
                RecordIndexer().index(draft_record.record)
                # mark all object pids as deleted
                all_pids = PersistentIdentifier.query.filter(
                    PersistentIdentifier.object_type == published_record.record_pid.object_type,
                    PersistentIdentifier.object_uuid == published_record.record_pid.object_uuid,
                ).all()
                for rec_pid in all_pids:
                    if not rec_pid.is_deleted():
                        rec_pid.delete()

        current_search_client.indices.refresh()
        current_search_client.indices.flush()

        return result

    def publish_record_internal(self, record_context,
                                published_record_class,
                                published_pid_type,
                                collected_records):
        draft_record = record_context.record
        draft_pid = record_context.record_pid
        # clone metadata
        metadata = dict(draft_record)
        if 'oarepo:validity' in metadata:
            if not metadata['oarepo:validity']['valid']:
                raise InvalidRecordException('Can not publish invalid record',
                                             errors=metadata['oarepo:validity']['errors'])
            del metadata['oarepo:validity']

        before_publish_record.send(draft_record, metadata=metadata, record=record_context,
                                   collected_records=collected_records)
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
        published_record = published_record_class.create(metadata, id_=id)
        published_pid = PersistentIdentifier.create(pid_type=published_pid_type,
                                                    pid_value=draft_pid.pid_value,
                                                    status=PIDStatus.REGISTERED,
                                                    object_type='rec', object_uuid=id)
        return published_record, published_pid

    def _update_published_record(self, published_pid, metadata,
                                 timestamp, published_record_class):
        published_record = published_record_class.get_record(
            published_pid.object_uuid, with_deleted=True)
        # if deleted, revert to last non-deleted revision
        if published_record.model.json is None:
            revision_id = published_record.revision_id
            while published_record.model.json is None and revision_id > 0:
                revision_id -= 1
                published_record.revert(revision_id)

        if not timestamp or published_record.updated < timestamp:
            published_record.update(metadata)
            if not published_record.get('$schema'):  # pragma no cover
                logger.warning('Updated draft record does not have a $schema metadata. '
                               'Please use a Record implementation that adds $schema '
                               '(in validate() and update() method). Draft PID Type %s',
                               published_pid.pid_type)

        published_record.commit()

        return published_record, published_pid

    def draft_record_internal(self, published_record_context, published_pid,
                              draft_record_class, draft_pid_type, collected_records):
        metadata = dict(published_record_context.record)

        before_unpublish_record.send(published_record_context.record, metadata=metadata,
                                     record=published_record_context,
                                     collected_records=collected_records)

        try:
            draft_pid = PersistentIdentifier.get(draft_pid_type, published_pid.pid_value)

            if draft_pid.status == PIDStatus.DELETED:
                # the draft is deleted, resurrect it
                # change the pid to registered
                draft_pid.status = PIDStatus.REGISTERED
                db.session.add(draft_pid)

                # and fetch the draft record and update its metadata
                return self._update_draft_record(
                    draft_pid, metadata, None, draft_record_class)

            elif draft_pid.status == PIDStatus.REGISTERED:
                # fetch the draft record and update its metadata
                # if it is older than the published one
                return self._update_draft_record(
                    draft_pid, metadata,
                    published_record_context.record.updated, draft_record_class)

            raise NotImplementedError('Can not unpublish record to draft record '
                                      'with pid status %s. Only registered or deleted '
                                      'statuses are implemented', draft_pid.status)
        except PIDDoesNotExistError:
            pass

        # create a new draft record. Do not call minter as the pid value will be the
        # same as the pid value of the published record
        id = uuid.uuid4()
        draft_record = draft_record_class.create(metadata, id_=id)
        draft_pid = PersistentIdentifier.create(pid_type=draft_pid_type,
                                                pid_value=published_pid.pid_value,
                                                status=PIDStatus.REGISTERED,
                                                object_type='rec', object_uuid=id)
        return draft_record, draft_pid

    def _update_draft_record(self, draft_pid, metadata,
                             timestamp, draft_record_class):
        draft_record = draft_record_class.get_record(draft_pid.object_uuid,
                                                     with_deleted=True)

        # if deleted, revert to last non-deleted revision
        revision_id = draft_record.revision_id
        while draft_record.model.json is None and revision_id > 0:
            revision_id -= 1
            draft_record.revert(revision_id)

        if not timestamp or draft_record.updated < timestamp:
            draft_record.update(metadata)
            if not draft_record['$schema']:  # pragma no cover
                logger.warning('Updated draft record does not have a $schema metadata. '
                               'Please use a Record implementation that adds $schema '
                               '(for example in validate() method). Draft PID Type %s',
                               draft_pid.pid_type)

        draft_record.commit()

        return draft_record, draft_pid


class RecordsDraft(object):
    def __init__(self, app=None):
        if app:
            self.init_app(app)

    def init_app(self, app):
        self.init_config(app)
        _state = RecordsDraftState(app)
        app.extensions['oarepo-draft'] = _state
        app_loaded.connect(_state.app_loaded)

    def init_config(self, app):
        app.config.setdefault('RECORDS_DRAFT_ENDPOINTS', {})
        app.config['RECORDS_REST_ENDPOINTS'] = Endpoints(app, app.config.get('RECORDS_REST_ENDPOINTS', {}))

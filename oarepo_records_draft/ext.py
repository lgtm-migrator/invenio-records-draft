import copy
import functools
import logging
import traceback
import uuid
from collections import namedtuple
from typing import List, Union

import invenio_indexer.config
import pkg_resources
from invenio_base.signals import app_loaded
from invenio_base.utils import obj_or_import_string
from invenio_db import db
from invenio_files_rest.models import ObjectVersion, ObjectVersionTag
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
    before_unpublish_record, after_publish_record, file_published
from .types import RecordContext, Endpoints
from .views import register_blueprint

logger = logging.getLogger(__name__)

PublishedDraftRecordPair = namedtuple(
    'PublishedDraftRecordPair',
    'published_context draft_context primary')


def setup_indexer(app):
    if app.config['INDEXER_RECORD_TO_INDEX'] == invenio_indexer.config.INDEXER_RECORD_TO_INDEX:
        app.config['INDEXER_RECORD_TO_INDEX'] = 'oarepo_records_draft.record.record_to_index'
        # in case it has already been used
        app.extensions['invenio-indexer'].record_to_index = \
            obj_or_import_string('oarepo_records_draft.record.record_to_index')


class RecordsDraftState:
    def __init__(self, app):
        self.app = app
        self.managed_records = None  # type: DraftManagedRecords
        self._uploaders = None
        self._extra_actions = None

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
            for _, collected_records in collect_records.send(
                    record,
                    record_context=rec,
                    record=rec,  # back compatibility, deprecated
                    action=action
            ):
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

    def indexer_for_record(self, record):
        indexer_class = self.indexer_class_for_record_class(type(record))
        if indexer_class:
            return indexer_class()
        return None

    @functools.lru_cache(maxsize=32)
    def indexer_class_for_record_class(self, clz):
        endpoint = self.managed_records.by_record_class(clz)
        if endpoint:
            indexer = endpoint.rest.get('indexer_class', 'invenio_indexer.api.RecordIndexer')
            return obj_or_import_string(indexer)
        else:
            return obj_or_import_string('invenio_indexer.api.RecordIndexer')

    @functools.lru_cache(maxsize=32)
    def endpoint_for_pid_type(self, pid_type):
        return self.managed_records.by_pid_type[pid_type]

    def endpoint_for_metadata(self, metadata):
        is_draft = 'oarepo:validity' in metadata
        schema = metadata.get('$schema', None)
        if not schema:
            return None
        return self.endpoint_for_schema(schema, is_draft)

    @functools.lru_cache(maxsize=32)
    def endpoint_for_schema(self, schema, is_draft):
        return self.managed_records.by_schema(schema, is_draft)

    @property
    def uploaders(self):
        if self._uploaders is None:
            uploaders = []
            for entry_point in pkg_resources.iter_entry_points('oarepo_records_draft.uploaders'):
                uploaders.append(entry_point.load())
            uploaders.sort(key=lambda opener: -getattr(opener, '_priority', 10))
            self._uploaders = uploaders
        return self._uploaders

    @property
    def extra_actions(self):
        if self._extra_actions is None:
            extra_actions = []
            for entry_point in pkg_resources.iter_entry_points('oarepo_records_draft.extra_actions'):
                extra_actions.append(entry_point.load())
            extra_actions.sort(key=lambda opener: -getattr(opener, '_priority', 10))
            self._extra_actions = extra_actions
        return self._extra_actions

    def publish(
            self, record: Union[RecordContext, Record], record_pid=None,
            require_valid=True
    ):
        if isinstance(record, Record):
            record = RecordContext(record=record, record_pid=record_pid)

        indices = set()

        with db.session.begin_nested():
            # collect all records to be published (for example, references etc)
            collected_records = self.collect_records_for_action(record, CollectAction.PUBLISH)

            # for each collected record, check if can be published
            for draft_record in collected_records:
                check_can_publish.send(record, record=draft_record)
                if 'oarepo:validity' in draft_record.record:
                    if require_valid and not draft_record.record['oarepo:validity']['valid']:
                        raise InvalidRecordException('Can not publish invalid record',
                                                     errors=draft_record.record['oarepo:validity']['errors'])

            before_publish.send(collected_records)

            result: List[PublishedDraftRecordPair] = []

            # publish in reversed order
            for draft_record_context in reversed(collected_records):
                draft_pid = draft_record_context.record_pid
                endpoint = self.endpoint_for_pid_type(draft_pid.pid_type)
                assert endpoint.published is False
                published_record_class = endpoint.paired_endpoint.record_class
                published_record_pid_type = endpoint.paired_endpoint.pid_type
                published_record, published_pid = self.publish_record_internal(
                    draft_record_context, published_record_class,
                    published_record_pid_type, collected_records
                )
                published_record_context = RecordContext(record=published_record,
                                                         record_pid=published_pid)
                result.append(PublishedDraftRecordPair(
                    draft_context=draft_record_context,
                    published_context=published_record_context,
                    primary=draft_record_context.record == record.record))
                draft_record_context.published_record_context = published_record_context
                published_record_context.draft_record_context = draft_record_context

            after_publish.send(result)

            for rp in result:
                # delete the record
                draft_record_context = rp.draft_context
                published_record_context = rp.published_context
                draft_record_context.record.delete()
                draft_indexer = self.indexer_for_record(draft_record_context.record)
                try:
                    if draft_indexer and draft_indexer.record_to_index(draft_record_context.record)[0]:
                        draft_indexer.delete(draft_record_context.record, refresh=True)
                except:
                    logger.debug('Error deleting record', draft_record_context.record_pid)
                    traceback.print_exc()

                published_indexer = self.indexer_for_record(published_record_context.record)
                if published_indexer and published_indexer.record_to_index(published_record_context.record)[0]:
                    published_indexer.index(published_record_context.record)

                # mark all object pids as deleted
                all_pids = PersistentIdentifier.query.filter(
                    PersistentIdentifier.object_type == draft_record_context.record_pid.object_type,
                    PersistentIdentifier.object_uuid == draft_record_context.record_pid.object_uuid,
                ).all()
                for rec_pid in all_pids:
                    if not rec_pid.is_deleted():
                        rec_pid.delete()

                published_record_context.record.commit()

                indices.add(self.index_for_record(published_record_context.record))
                indices.add(self.index_for_record(draft_record_context.record))

        for index in indices:
            if not index:
                continue
            current_search_client.indices.refresh(index=index)
            current_search_client.indices.flush(index=index)

        result.reverse()
        return result

    def edit(self, record: Union[RecordContext, Record], record_pid=None):
        if isinstance(record, Record):
            record = RecordContext(record=record, record_pid=record_pid)

        indices = set()

        with db.session.begin_nested():
            # collect all records to be draft (for example, references etc)
            collected_records = self.collect_records_for_action(record, CollectAction.EDIT)

            # for each collected record, check if can be draft
            for published_record in collected_records:
                check_can_edit.send(record, record=published_record)

            before_edit.send(collected_records)

            result: List[PublishedDraftRecordPair] = []
            # publish in reversed order
            for published_record_context in reversed(collected_records):
                published_pid = published_record_context.record_pid
                endpoint = self.endpoint_for_pid_type(published_pid.pid_type)
                assert endpoint.published
                draft_record_class = endpoint.paired_endpoint.record_class
                draft_record_pid_type = endpoint.paired_endpoint.rest_name
                draft_record, draft_pid = self.draft_record_internal(
                    published_record_context, published_pid,
                    draft_record_class, draft_record_pid_type,
                    collected_records
                )
                draft_record_context = RecordContext(record=draft_record, record_pid=draft_pid)
                result.append(PublishedDraftRecordPair(
                    published_context=published_record_context,
                    draft_context=draft_record_context,
                    primary=published_record_context.record == record.record))

                draft_record_context.published_record_context = published_record_context
                published_record_context.draft_record_context = draft_record_context

            after_edit.send(result)

            for rp in result:
                published_record_context = rp.published_context
                draft_record_context = rp.draft_context
                draft_record_context.record.commit()
                draft_indexer = self.indexer_for_record(draft_record_context.record)
                if draft_indexer and draft_indexer.record_to_index(draft_record_context.record)[0]:
                    draft_indexer.index(draft_record_context.record)

                indices.add(self.index_for_record(published_record_context.record))
                indices.add(self.index_for_record(draft_record_context.record))

        for index in indices:
            if not index:
                continue
            current_search_client.indices.refresh(index=index)
            current_search_client.indices.flush(index=index)

        result.reverse()
        return result

    def unpublish(self, record: Union[RecordContext, Record], record_pid=None):
        if isinstance(record, Record):
            record = RecordContext(record=record, record_pid=record_pid)

        indices = set()

        with db.session.begin_nested():
            # collect all records to be draft (for example, references etc)
            collected_records = self.collect_records_for_action(record, CollectAction.UNPUBLISH)

            # for each collected record, check if can be draft
            for published_record in collected_records:
                check_can_unpublish.send(record, record=published_record)

            before_unpublish.send(collected_records)

            result: List[PublishedDraftRecordPair] = []
            # publish in reversed order
            for published_record_context in reversed(collected_records):
                published_pid = published_record_context.record_pid
                endpoint = self.endpoint_for_pid_type(published_pid.pid_type)
                assert endpoint.published
                draft_record_class = endpoint.paired_endpoint.record_class
                draft_record_pid_type = endpoint.paired_endpoint.pid_type
                draft_record, draft_pid = self.draft_record_internal(
                    published_record_context, published_pid,
                    draft_record_class, draft_record_pid_type,
                    collected_records
                )
                draft_record_context = RecordContext(record=draft_record, record_pid=draft_pid)
                result.append(PublishedDraftRecordPair(
                    published_context=published_record_context,
                    draft_context=draft_record_context,
                    primary=published_record_context.record == record.record))

                draft_record_context.published_record_context = published_record_context
                published_record_context.draft_record_context = draft_record_context

            after_unpublish.send(result)

            for rp in result:
                published_record_context = rp.published_context
                draft_record_context = rp.draft_context
                # delete the record
                published_record_context.record.delete()
                published_indexer = self.indexer_for_record(published_record_context.record)
                try:
                    if published_indexer and published_indexer.record_to_index(published_record_context.record)[0]:
                        RecordIndexer().delete(published_record_context.record, refresh=True)
                except:
                    logger.debug('Error deleting record', published_record_context.record_pid)
                    traceback.print_exc()

                draft_record_context.record.commit()
                draft_indexer = self.indexer_for_record(draft_record_context.record)
                if draft_indexer and draft_indexer.record_to_index(draft_record_context.record)[0]:
                    draft_indexer.index(draft_record_context.record)
                # mark all object pids as deleted
                all_pids = PersistentIdentifier.query.filter(
                    PersistentIdentifier.object_type == published_record_context.record_pid.object_type,
                    PersistentIdentifier.object_uuid == published_record_context.record_pid.object_uuid,
                ).all()
                for rec_pid in all_pids:
                    if not rec_pid.is_deleted():
                        rec_pid.delete()

                indices.add(self.index_for_record(published_record_context.record))
                indices.add(self.index_for_record(draft_record_context.record))

        for index in indices:
            if not index:
                continue
            current_search_client.indices.refresh(index=index)
            current_search_client.indices.flush(index=index)

        result.reverse()
        return result

    def publish_record_internal(self, record_context,
                                published_record_class,
                                published_pid_type,
                                collected_records):
        draft_record = record_context.record
        draft_pid = record_context.record_pid

        # clone metadata
        metadata = copy.deepcopy(dict(draft_record))
        if 'oarepo:validity' in metadata:
            del metadata['oarepo:validity']
        metadata.pop('oarepo:draft', True)

        try:
            published_pid = PersistentIdentifier.get(published_pid_type, draft_pid.pid_value)
        except PIDDoesNotExistError:
            published_pid = None

        before_publish_record.send(draft_record, metadata=metadata,
                                   record_context=record_context,
                                   record=record_context,  # back compatibility, deprecated
                                   collected_records=collected_records)

        if published_pid:
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

        # create a new draft record. Do not call minter as the pid value will be the
        # same as the pid value of the published record
        id = uuid.uuid4()
        published_record = published_record_class.create(metadata, id_=id)
        published_pid = PersistentIdentifier.create(pid_type=published_pid_type,
                                                    pid_value=draft_pid.pid_value,
                                                    status=PIDStatus.REGISTERED,
                                                    object_type='rec', object_uuid=id)

        if hasattr(draft_record, 'bucket'):
            self._publish_files(draft_record, published_record)
            published_record.files.flush()
            db.session.add(published_record.model)

        after_publish_record.send(draft_record,
                                  published_record=published_record,
                                  published_pid=published_pid,
                                  collected_records=collected_records)
        return published_record, published_pid

    def _publish_files(self, draft_record, published_record):
        draft_by_key = {
            x['key']: x for x in draft_record.get('_files', [])
        }
        published_files = []
        for ov in ObjectVersion.get_by_bucket(bucket=draft_record.bucket):
            file_md = copy.copy(draft_by_key.get(ov.key, {}))
            if self._publish_file(draft_record, ov, published_record, file_md):
                published_files.append(file_md)
        published_record['_files'] = published_files

    def _publish_file(self, draft_record, ov, published_record, file_md):
        bucket = published_record.bucket
        new_ob = ObjectVersion.create(
            bucket,
            ov.key,
            _file_id=ov.file_id
        )

        tags = {tag.key: tag.value for tag in ov.tags}
        for _, res in file_published.send(
                draft_record, draft_record=draft_record,
                published_record=published_record, object_version=ov,
                tags=tags, metadata=file_md):
            if res is False:
                return False  # skip this file

        for key, value in tags:
            ObjectVersionTag.create_or_update(
                object_version=new_ob,
                key=key,
                value=value)

        return True

    def index_for_record(self, record):
        indexer: RecordIndexer = self.indexer_for_record(record)
        if not indexer:
            return None
        index, doctype = indexer.record_to_index(record)
        if not index:
            return None
        return indexer._prepare_index(index, doctype)[0]

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
        after_publish_record.send(published_record,
                                  published_record=published_record,
                                  published_pid=published_pid)

        return published_record, published_pid

    def draft_record_internal(self, published_record_context, published_pid,
                              draft_record_class, draft_pid_type, collected_records):
        metadata = copy.deepcopy(dict(published_record_context.record))

        before_unpublish_record.send(published_record_context.record, metadata=metadata,
                                     record_context=published_record_context,
                                     record=published_record_context,  # back compatibility, deprecated
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


@file_published.connect
def replace_urls(sender, draft_record=None, published_record=None,
                 object_version=None, tags=None, metadata=None, **kwargs):
    if hasattr(draft_record, 'canonical_url') and hasattr(published_record, 'canonical_url'):
        draft_url = draft_record.canonical_url
        published_url = published_record.canonical_url

        if not draft_url.endswith('/'):
            draft_url += '/'

        if not published_url.endswith('/'):
            published_url += '/'

        for tag_name, tag_value in list(tags.items()):
            if tag_value.startswith(draft_url):
                tags[tag_name] = published_url + tag_value[len(draft_url):]

        for key, value in list(metadata.items()):
            if isinstance(value, str) and value.startswith(draft_url):
                metadata[key] = published_url + value[len(draft_url):]
    return True

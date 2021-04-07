import datetime
import itertools
import json
import traceback
from multiprocessing import Pool

import click
from elasticsearch.helpers import bulk
from flask import current_app
from flask.cli import with_appcontext
from invenio_app.factory import create_api
from invenio_db import db
from invenio_indexer.utils import _es7_expand_action
from invenio_pidstore.models import PersistentIdentifier, PIDStatus

from oarepo_records_draft import current_drafts
from oarepo_records_draft.types import RecordEndpointConfiguration

try:
    from tqdm import tqdm
except ImportError:
    def tqdm(iterable, disable=False):
        return iterable


def grouper(n, iterable):
    iterable = iter(iterable)
    return iter(lambda: list(itertools.islice(iterable, n)), [])


@click.group(name='oarepo:drafts')
def drafts():
    """OARepo record drafts commands."""


@drafts.command('reindex')
@click.option('--pid-type', '-t', help='Limit revalidate to a given pid type')
@click.option('--pid', '-p', help='Limit revalidate to a given pid of form pid_type:pid_value')
@click.option('--processes', default=5, help='Number of database processes')
@click.option('--bulk-size', default=500, help='Number of records to index at the same time')
@click.option('--save/--no-save', '-s', default=False, help='If the validation is successful, commit the record')
@click.option('--verbose/--quiet', '-v', default=False, help='Print details')
@with_appcontext
def reindex_records(pid_type, pid, save, verbose, processes, bulk_size):
    if pid:
        return index_single_pid(pid, verbose)

    start = datetime.datetime.now()
    if pid_type:
        pid_types = {pid_type}
    else:
        pid_types = set([
            *[x.draft.pid_type for x in current_drafts.managed_records],
            *[x.published.pid_type for x in current_drafts.managed_records]
        ])

    with Pool(processes=processes) as pool:
        req_timeout = current_app.config['INDEXER_BULK_REQUEST_TIMEOUT']
        results = []
        if verbose:
            print('Generating indexing tasks')
        for pid_type in tqdm(pid_types, disable=not verbose):
            object_uuids = [x[0] for x in db.session.query(PersistentIdentifier.object_uuid).filter(
                PersistentIdentifier.pid_type == pid_type,
                PersistentIdentifier.status == PIDStatus.REGISTERED.value)]
            if not len(object_uuids):
                continue
            for object_uuids_group in grouper(bulk_size, object_uuids):
                results.append(
                    pool.apply_async(bulk_indexer,
                                     args=(pid_type, object_uuids_group, req_timeout)))
        ok = 0
        errors = 0
        if verbose:
            print('Gathering indexing results')
        for res in tqdm(results, disable=not verbose):
            res_ok, res_errors = res.get()
            ok += res_ok
            if res_errors:
                errors += len(res_errors)
                if verbose:
                    for err in res_errors:
                        print(json.dumps(err, default=lambda x: str(x)))
        end = datetime.datetime.now()
        if verbose:
            print(f'Total {ok} ok, {errors} errors in {end - start}')


bulk_app = []


def bulk_indexer(pid_type, object_uuids, req_timeout):
    exceptions = []
    try:
        if not bulk_app:
            bulk_app.append(create_api())

        with bulk_app[0].app_context():
            endpoint: RecordEndpointConfiguration = current_drafts.endpoint_for_pid_type(pid_type)
            record_class = endpoint.record_class
            indexer_class = endpoint.indexer_class

            indexer = indexer_class()
            # force record class
            indexer.record_cls = record_class

            def get_indexing_data(record_uuid):
                try:
                    return indexer._index_action({"id": record_uuid})
                except Exception as e:
                    exceptions.append({
                        'record_uuid': str(record_uuid),
                        'message': str(e),
                        'traceback': traceback.format_exc(),
                    })
                return {}

            recs = (get_indexing_data(record_uuid) for record_uuid in object_uuids)

            success, errors = bulk(
                indexer.client,
                recs,
                stats_only=False,
                request_timeout=req_timeout,
                expand_action_callback=_es7_expand_action,
                raise_on_error=False
            )

            return success, [
                *errors,
                *exceptions
            ]
    except Exception as e:
        if len(object_uuids) == 1:
            return 0, [{
                'message': str(e),
                'traceback': traceback.format_exc()
            }, *exceptions]
        else:
            # index what could be indexed
            ok = 0
            errors = []
            if len(object_uuids) > 4:
                # split into two halves and try for each half
                mid = len(object_uuids) / 2
                object_uuids = [
                    object_uuids[:mid],
                    object_uuids[mid:]
                ]
            else:
                # try for each element
                object_uuids = [[x] for x in object_uuids]
            for uuids in object_uuids:
                p_ok, p_errors = bulk_indexer(pid_type, uuids, req_timeout)
                ok += p_ok
                errors.extend(p_errors)
            return ok, errors


def index_single_pid(pid, verbose):
    pid_type, pid_value = pid.split(':', maxsplit=1)
    pids = PersistentIdentifier.query.filter(
        PersistentIdentifier.pid_type == pid_type,
        PersistentIdentifier.pid_value == pid_value,
        PersistentIdentifier.status == PIDStatus.REGISTERED.value
    )
    endpoint: RecordEndpointConfiguration = current_drafts.endpoint_for_pid_type(pid_type)
    record_class = endpoint.record_class
    indexer_class = endpoint.indexer_class
    for pid in pids:
        if verbose:
            print('Processing pid', pid)
        try:
            record = record_class.get_record(pid.object_uuid)
            indexer_class().index(record)
        except Exception as e:
            if verbose:
                print('    INVALID, exception', e)
                traceback.print_exc()

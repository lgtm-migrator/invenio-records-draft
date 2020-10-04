import copy
import json
import traceback
from typing import Iterable

import click
from flask import current_app
from flask.cli import with_appcontext
from invenio_base.utils import obj_or_import_string
from invenio_indexer.api import RecordIndexer
from invenio_pidstore.models import PersistentIdentifier, PIDStatus
from invenio_records import Record


@click.group(name='oarepo:drafts')
def drafts():
    """OARepo record drafts commands."""


@drafts.command('reindex')
@click.option('--pid-type', '-t', help='Limit revalidate to a given pid type')
@click.option('--pid', '-p', help='Limit revalidate to a given pid of form pid_type:pid_value')
@click.option('--save/--no-save', '-s', default=False, help='If the validation is successful, commit the record')
@click.option('--verbose/--quiet', '-v', default=False, help='Print details')
@with_appcontext
def reindex_records(pid_type=None, pid=None, save=False, verbose=False):
    pids: Iterable[PersistentIdentifier]
    if pid_type:
        pids = PersistentIdentifier.query.filter(
            PersistentIdentifier.pid_type == pid_type,
            PersistentIdentifier.status == PIDStatus.REGISTERED.value)
    elif pid:
        pid_type, pid_value = pid.split(':', maxsplit=1)
        pids = PersistentIdentifier.query.filter(
            PersistentIdentifier.pid_type == pid_type,
            PersistentIdentifier.pid_value == pid_value,
            PersistentIdentifier.status == PIDStatus.REGISTERED.value
        )
    else:
        pids = PersistentIdentifier.query.filter(
            PersistentIdentifier.status == PIDStatus.REGISTERED.value)

    pid_type_to_record_class = {}
    for k, rec in current_app.config.get('RECORDS_REST_ENDPOINTS', {}).items():
        pid_type_to_record_class[rec['pid_type']] = obj_or_import_string(rec.get('record_class', Record))

    pid_type_to_indexer = {}
    for k, rec in current_app.config.get('RECORDS_REST_ENDPOINTS', {}).items():
        pid_type_to_indexer[rec['pid_type']] = obj_or_import_string(rec.get('indexer_class', RecordIndexer))

    for pid in pids:
        if pid.pid_type not in pid_type_to_indexer or not pid_type_to_indexer[pid.pid_type]:
            if verbose:
                print('Skipping pid', pid)
                continue
        if verbose:
            print('Processing pid', pid)
        try:
            record = pid_type_to_record_class[pid.pid_type].get_record(pid.object_uuid)
            pid_type_to_indexer[pid.pid_type]().index(record)
        except Exception as e:
            if verbose:
                print('    INVALID, exception', e)
                traceback.print_exc()

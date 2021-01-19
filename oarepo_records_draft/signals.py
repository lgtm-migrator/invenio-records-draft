from __future__ import absolute_import, print_function

from enum import Enum

from blinker import Namespace

_signals = Namespace()


class CollectAction(Enum):
    PUBLISH = 'publish'
    UNPUBLISH = 'unpublish'
    EDIT = 'edit'


collect_records = _signals.signal('collect_records')
"""Signal sent to collect all objects that should be published.

:param  record_context: the record being published
:param  action: CollectAction
:return list of RecordContext instances of records that should be published
"""

check_can_publish = _signals.signal('check_can_publish')
"""Check if the record can be published. Called from within a request context.
Should raise an exception if the caller does not have permission to publish
or if there is any condition prohibiting the publishing.

:param  record: the record being published
"""

before_publish = _signals.signal('before_publish')
"""
A notification called before the records are published

:param records: a list of records to publish.
"""

before_publish_record = _signals.signal('before_publish_record')
"""
A notification called before a record is published

:param metadata: metadata of the published record
:param record_context: RecordContext of the draft record
:param collected_records: All collected records
"""

after_publish_record = _signals.signal('after_publish_record')
"""
A notification called after a record is published

:param published_record
:param published_pid
"""

after_publish = _signals.signal('after_publish')
"""
A notification called after the records have been published

:param records: a list of tuples (draft_record, published_record). The draft record
has already been invalidated.
"""

check_can_unpublish = _signals.signal('check_can_unpublish')
"""Check if the record can be unpublished. Called from within a request context.
Should raise an exception if the caller does not have permission to unpublish
or if there is any condition prohibiting the unpublishing.

:param  record: the record being unpublished
"""

before_unpublish = _signals.signal('before_unpublish')
"""
A notification called before the records are unpublished

:param records: a list of records to unpublish
"""

before_unpublish_record = _signals.signal('before_unpublish_record')
"""
A notification called before a record is published

:param metadata: metadata of the published record
:param record_context: RecordContext of the draft record
:param collected_records: All collected records
"""

after_unpublish = _signals.signal('after_unpublish')
"""
A notification called after the records have been unpublished

:param records: a list of tuples (published_record, draft_record). The published
record is marked as unpublished (PID suspended)
"""

check_can_edit = _signals.signal('check_can_edit')
"""Check if the record can be edited. Called from within a request context.
Should raise an exception if the caller does not have permission to edit
or if there is any condition prohibiting the editing.

:param  record: the record being edited
"""

before_edit = _signals.signal('before_edit')
"""
A notification called before the records are edited

:param records: a list of records to edit
"""

after_edit = _signals.signal('after_edit')
"""
A notification called after the records have been prepared for editing

:param records: a list of tuples (published_record, draft_record). The published
record is marked as is.
"""

file_before_uploaded = _signals.signal('file_before_uploaded')
"""
A notification aka rest's file_uploaded but tied to a record and called before the file object has been created

:param sender ObjectVersion 
:param record file's record
:param key    created file object key
:param files  FileIterator on the record
:param pid    PersistentIdentifier of the record
"""

file_uploaded = _signals.signal('file_uploaded')
"""
A notification aka rest's file_uploaded but tied to a record

:param sender ObjectVersion 
:param record file's record
:param file   FileObject on the record
:param files  FileIterator on the record
:param pid    PersistentIdentifier of the record
"""
file_uploaded_before_flush = _signals.signal('file_uploaded_before_flush')
"""
A notification aka rest's file_uploaded but tied to a record and called before the record files 
have been flushed to record metadata

:param sender file's record 
:param record file's record
:param file   FileObject on the record
:param files  FileIterator on the record
:param pid    PersistentIdentifier of the record
"""

file_uploaded_before_commit = _signals.signal('file_uploaded_before_commit')
"""
A notification aka rest's file_uploaded but tied to a record and called before the record has been committed

:param sender file's record 
:param record file's record
:param file   FileObject on the record
:param files  FileIterator on the record
:param pid    PersistentIdentifier of the record
"""

file_downloaded = _signals.signal('file_downloaded')
"""
A notification aka rest's file_downloaded but tied to a record

:param sender ObjectVersion 
:param record file's record
:param files  record's .files
:param file   FileObject on the record
:param pid    PersistentIdentifier of the record
"""

file_before_deleted = _signals.signal('file_before_deleted')
"""
A notification aka rest's file_deleted but tied to a record and called before the deletion has been run

:param sender file's record 
:param record file's record
:param files  record's .files
:param file   FileObject on the record
:param pid    PersistentIdentifier of the record
"""


file_deleted_before_commit = _signals.signal('file_deleted_before_commit')
"""
A notification aka rest's file_deleted but tied to a record and called before the record has been committed

:param sender file's record 
:param record file's record
:param files  record's .files
:param file   FileObject on the record
:param pid    PersistentIdentifier of the record
"""

file_deleted_before_flush = _signals.signal('file_deleted_before_flush')
"""
A notification aka rest's file_deleted but tied to a record and called before the record's files have been flushed

:param sender file's record 
:param record file's record
:param files  record's .files
:param file   FileObject on the record
:param pid    PersistentIdentifier of the record
"""

file_deleted = _signals.signal('file_deleted')
"""
A notification aka rest's file_deleted but tied to a record

:param sender ObjectVersion 
:param record file's record
:param files  record's .files
:param file   FileObject on the record
:param pid    PersistentIdentifier of the record
"""

file_before_metadata_modified = _signals.signal('file_before_metadata_modified')
"""
A notification send before file's metadata are modified

:param sender file's record 
:param record file's record
:param files  record's .files
:param file   FileObject on the record
:param pid    PersistentIdentifier of the record
:param metadata form metadata to be set up
"""

file_after_metadata_modified = _signals.signal('file_before_metadata_modified')
"""
A notification send before file's metadata are modified

:param sender file's record 
:param record file's record
:param files  record's .files
:param file   FileObject on the record
:param pid    PersistentIdentifier of the record
:param metadata form metadata to be set up
"""


file_metadata_modified_before_flush = _signals.signal('file_metadata_modified_before_flush')
"""
A notification send before file's metadata are modified

:param sender file's record 
:param record file's record
:param files  record's .files
:param file   FileObject on the record
:param pid    PersistentIdentifier of the record
:param metadata form metadata to be set up
"""

file_metadata_modified_before_commit = _signals.signal('file_metadata_modified_before_commit')
"""
A notification send before file's metadata are modified

:param sender file's record 
:param record file's record
:param files  record's .files
:param file   FileObject on the record
:param pid    PersistentIdentifier of the record
:param metadata form metadata to be set up
"""

file_published = _signals.signal('file_published')
"""
A notification send when a file from draft is bound to a published file

:param sender file's draft record
:param draft_record draft record
:param published_record published_record
:param object_version the object version being published
:param tags dictionary of tag name => tag value

:return False if the file should be skipped, True/None if it should be included
Can modify ``tags`` dictionary (replace urls etc)
"""
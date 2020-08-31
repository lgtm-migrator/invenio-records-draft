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

:param  record: the record being published
:param  action: CollectAction
:return list of RecordContext instances of records that should be published
"""

check_can_publish = _signals.signal('check_publish')
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
:param record: RecordContext of the draft record
:param collected_records: All collected records
"""

after_publish = _signals.signal('after_publish')
"""
A notification called after the records have been published

:param records: a list of tuples (draft_record, published_record). The draft record
has already been invalidated.
"""

check_can_unpublish = _signals.signal('check_unpublish')
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

before_unpublish_record = _signals.signal('before_publish_record')
"""
A notification called before a record is published

:param metadata: metadata of the published record
:param record: RecordContext of the draft record
:param collected_records: All collected records
"""

after_unpublish = _signals.signal('after_unpublish')
"""
A notification called after the records have been unpublished

:param records: a list of tuples (published_record, draft_record). The published
record is marked as unpublished (PID suspended)
"""

check_can_edit = _signals.signal('check_edit')
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

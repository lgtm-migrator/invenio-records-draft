from invenio_indexer.api import RecordIndexer
from invenio_search import current_search_client


class RefreshingRecordIndexer(RecordIndexer):
    def index(self, record, arguments=None, **kwargs):
        ret = super().index(record, arguments, **kwargs)
        index, doc_type = self.record_to_index(record)
        index, doc_type = self._prepare_index(index, doc_type)
        current_search_client.indices.refresh(index)
        return ret

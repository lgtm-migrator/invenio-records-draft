from collections import namedtuple

RecordSchema = namedtuple("RecordSchema", "record, schema, index_name, draft_index_name")
RecordEndpoint = namedtuple("RecordEndpoint", "published_name, draft_name, published_endpoint, draft_endpoint")


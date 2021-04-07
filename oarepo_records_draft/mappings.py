import os
import json

from NamedAtomicLock import NamedAtomicLock

from oarepo_records_draft.types import DraftPublishedRecordConfiguration, DraftManagedRecords


def find_alias(aliases, key):
    for k, v in aliases.items():
        if key in v:
            return k
    raise ValueError('Alias for %s not found: %s' % (key, aliases))


def process(mappings, aliases, base_dir, mapping, draft_mapping):
    # load the file, convert its types and write it back into cache directory
    if not draft_mapping:
        return

    dest_file = os.path.join(base_dir, os.path.basename(draft_mapping))
    with open(mappings[mapping]) as f:
        mapping_data = json.load(f)

    if 'mappings' not in mapping_data:
        raise ValueError('No mappings found in %s' % mappings[mapping])

    mapping_data['mappings']['dynamic'] = False  # disable dynamic fields

    settings = mapping_data.setdefault('settings', {})
    settings["index.mapping.ignore_malformed"] = True  # allow malformed input on drafts

    properties = mapping_data['mappings'].setdefault('properties', {})
    properties.update(draft_validation_json)

    mapping_to_save = json.dumps(mapping_data, ensure_ascii=False, indent=4)

    do_save = True
    if os.path.exists(dest_file):
        with open(dest_file, 'r') as f:
            existing = f.read()
            if existing == mapping_to_save:
                do_save = False
    if do_save:
        with open(dest_file, 'w') as f:
            f.write(mapping_to_save)

    mappings[draft_mapping] = dest_file
    aliases['draft-' + find_alias(aliases, mapping)] = {
        draft_mapping: dest_file
    }


def setup_draft_mappings(managed_records: DraftManagedRecords, app):
    mappings = app.extensions['invenio-search'].mappings
    aliases = app.extensions['invenio-search'].aliases

    lock = NamedAtomicLock('oarepo-records-draft')
    lock.acquire()
    try:
        transformed_mappings_dir = os.path.join(app.instance_path, 'mappings')
        if not os.path.exists(transformed_mappings_dir):
            os.makedirs(transformed_mappings_dir)

        for rec in list(managed_records):
            for schema, index in rec.draft.schema_indices.items():
                if index not in mappings:
                    process(mappings, aliases, transformed_mappings_dir,
                            rec.published.get_index(schema),
                            index)
    finally:
        lock.release()

draft_validation_json = {
    "oarepo:draft": {
        "type": "boolean"
    },
    "oarepo:validity": {
        "type": "object",
        "properties": {
            "valid": {
                "type": "boolean"
            },
            "errors": {
                "type": "object",
                "properties": {
                    "marshmallow": {
                        "type": "object",
                        "properties": {
                            "field": {
                                "type": "keyword",
                                "copy_to": "oarepo:validity.errors.all.field"
                            },
                            "message": {
                                "type": "text",
                                "copy_to": "oarepo:validity.errors.all.message",
                                "fields": {
                                    "raw": {
                                        "type": "keyword"
                                    }
                                }
                            }
                        }
                    },
                    "jsonschema": {
                        "type": "object",
                        "properties": {
                            "field": {
                                "type": "keyword",
                                "copy_to": "oarepo:validity.errors.all.field"
                            },
                            "message": {
                                "type": "text",
                                "copy_to": "oarepo:validity.errors.all.message",
                                "fields": {
                                    "raw": {
                                        "type": "keyword"
                                    }
                                }
                            }
                        }
                    },
                    "other": {
                        "type": "text",
                        "copy_to": "oarepo:validity.errors.all.message",
                    },
                    "all": {
                        "type": "object",
                        "properties": {
                            "field": {
                                "type": "keyword"
                            },
                            "message": {
                                "type": "text",
                                "fields": {
                                    "raw": {
                                        "type": "keyword"
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

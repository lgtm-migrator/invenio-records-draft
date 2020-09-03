import os
import json

from oarepo_records_draft.types import DraftPublishedRecordConfiguration, DraftManagedRecords


def find_alias(aliases, key):
    for k, v in aliases.items():
        if key in v:
            return k
    raise ValueError('Alias for %s not found: %s' % (key, aliases))


def process(mappings, aliases, base_dir, mapping, draft_mapping):
    # load the file, convert its types and write it back into cache directory
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

    with open(dest_file, 'w') as f:
        json.dump(mapping_data, f, ensure_ascii=False, indent=4)

    mappings[draft_mapping] = dest_file
    aliases['draft-' + find_alias(aliases, mapping)] = {
        draft_mapping: dest_file
    }


def setup_draft_mappings(managed_records: DraftManagedRecords, app):
    mappings = app.extensions['invenio-search'].mappings
    aliases = app.extensions['invenio-search'].aliases

    transformed_mappings_dir = os.path.join(app.instance_path, 'mappings')
    if not os.path.exists(transformed_mappings_dir):
        os.makedirs(transformed_mappings_dir)

    for rec in list(managed_records):
        for schema, index in rec.draft.schema_indices.items():
            if index not in mappings:
                process(mappings, aliases, transformed_mappings_dir,
                        rec.published.get_index(schema),
                        index)


draft_validation_json = {
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
                                "type": "keyword"
                            },
                            "message": {
                                "type": "text",
                                "fields": {
                                    "keyword": {
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
                                "type": "keyword"
                            },
                            "message": {
                                "type": "text",
                                "fields": {
                                    "keyword": {
                                        "type": "keyword"
                                    }
                                }
                            }
                        }
                    },
                    "other": {
                        "type": "text"
                    }
                }
            }
        }
    }
}

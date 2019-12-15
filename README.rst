========================
Invenio Records Draft
========================

.. image:: https://img.shields.io/github/license/oarepo/invenio-records-draft.svg
        :target: https://github.com/oarepo/invenio-records-draft/blob/master/LICENSE

.. image:: https://img.shields.io/travis/oarepo/invenio-records-draft.svg
        :target: https://travis-ci.org/oarepo/invenio-records-draft

.. image:: https://img.shields.io/coveralls/oarepo/invenio-records-draft.svg
        :target: https://coveralls.io/r/oarepo/invenio-records-draft

.. image:: https://img.shields.io/pypi/v/oarepo-invenio-records-draft.svg
        :target: https://pypi.org/pypi/oarepo-invenio-records-draft



**Beta version, use at your own risk!!!**

This library helps to solve the situation where records in Invenio go through draft stage before they
are published.

Example:

.. code:: python

    # marshmallow and schema: property 'title' is required

    > draft_url = 'https://localhost:5000/api/drafts/records/'
    > published_url = 'https://localhost:5000/api/records/'

    > created_draft_url = post(draft_url,
        json={
            '$schema': current_jsonschemas.path_to_url('draft/records/record-v1.0.0.json')
        })[...]

    302, created_draft_url = 'https://localhost:5000/drafts/records/1'

    > resp = get(created_draft_url)

    > publish_link = resp.json['links']['publish']

    > resp.json['metadata']

    {
        "$schema": "https://localhost:5000/schemas/draft/records/record-v1.0.0.json",
        "id": "1",
        'invenio_draft_validation': {
            'errors': {
                'marshmallow': [
                    {'field': 'title',
                     'message': 'Missing data for required field.'
                     }
                ]
            },
            'valid': False
        }
    }

    > put(created_draft_url, json={
        "$schema": "https://localhost:5000/schemas/draft/records/record-v1.0.0.json",
        'title': 'def'})

    {
        "$schema": "https://localhost:5000/schemas/draft/records/record-v1.0.0.json",
        "id": "1",
        'invenio_draft_validation': {
            'valid': True
        }
    }

    > post(publish_link)

    302, headers['Location'] == 'https://localhost:5000/records/1'


Library principles:
===================

1. Draft records should follow the same json schema as published records with the exception
   that all/most properties are not required even though they are marked as such

2. Draft records should follow the same marshmallow schema as published records with
   some exceptions:

    a. all/most properties are not required even though they are marked as such
    b. for properties that have validators attached these validations will be ignored,
       unless they are explicitly marked with ``draft_allowed``.

3. If wished, draft records may be configured not follow the schema at all. In this case,
   the record is not indexed in elasticsearch at all.

4. "Draft" records live at a different endpoint and different ES index than published ones.
   The recommended URL is ``/api/records`` for the published records and
   ``/api/drafts/records`` for drafts

5. Draft and published records share the same value of pid but have two different pid types ✓

6. Published records can not be directly created/updated/patched. Draft records can be
   created/updated/patched.

7. Invenio record contains ``Link`` header and ``links`` section in the JSON payload.
   Links of a published record contain (apart from ``self``):

    a. ``draft`` - a url that links to the "draft" version of the record. This url is present
       only if the draft version of the record exists and the caller has the rights
       to edit the draft
    b. ``edit`` - URL to a handler that creates a draft version of the record and then
       returns HTTP 302 redirect to the draft version. This url is present only if the
       draft version does not exist
    c. ``unpublish`` - URL to a handler that creates a draft version of the record
       if it does not exist, deletes the published version and then returns HTTP 302 to the draft.


8. On a draft record the ``links`` contain (apart from ``self``):

    a. ``published`` - a url that links to the "published" version of the record. This url is present
       only if the published version of the record exists

    b. ``publish`` - a POST to this url publishes the record. The JSONSchema and marshmallow
       schema of the published record must pass. After the publishing the draft record is
       deleted. HTTP 302 is returned pointing to the published record.

9. The serialized representation of a draft record contains a section named ``invenio_draft_validation``.
   This section contains the result of marshmallow and JSONSchema validation against original
   schemas.

10. Deletion of a published record does not delete the draft record.

11. Deletion of a draft record does not delete the published record.


Usage
======================

.. code:: bash

    pip install oarepo-invenio-records-draft

JSON Schema
------------

Create json schema for the published record, no modifications are required for the
draft version.

In the configuration (invenio.cfg or your module's config) register the schema:


.. code:: python

    INVENIO_RECORD_DRAFT_SCHEMAS = [
        'records/record-v1.0.0.json',
    ]

    # or

    INVENIO_RECORD_DRAFT_SCHEMAS = [
        {
            'published_schema': 'records/record-v1.0.0.json',
            # ... other options (not yet used)
        }
    ]

Run in terminal

.. code:: bash

    invenio draft make-schemas

This command will create a draft schema in ``INVENIO_RECORD_DRAFT_SCHEMAS_DIR``, default value
is ``var/instance/draft_schemas/`` and will print out the created schema path:

.. code:: bash

    ...var/instance/draft_schemas/draft/records/record-v1.0.0.json

To check that the schemas are working, run

.. code:: bash

    invenio run <https etc>

    curl https://localhost:5000/schemas/records/record-v1.0.0.json
    curl https://localhost:5000/schemas/draft/records/record-v1.0.0.json

Note the extra prefix "/draft/".

Elasticsearch Mapping
----------------------

To create elasticsearch schemas and aliases for the draft records, run:

.. code:: bash

    invenio draft make-mappings
    invenio index init --force

The first command creates

.. code:: bash

    ...var/instance/draft_mappings/draft-records-record-v1.0.0.json

which is a patched version of the "published" records mapping with an extra section
for validation errors

.. code:: json

    {
      "invenio_draft_validation": {
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

The second deploys the schema to elasticsearch as ``draft-records-record-v1.0.0``
and creates alias ``draft-records``.

To check that the command worked GET http://localhost:9200/draft-records-record-v1.0.0

Marhsmallow Schema
----------------------

Inherit your marshmallow schema (and all nested schemas) from ``DraftEnabledSchema``.
If you use mixins that inherit from Schema (such as StrictKeysMixin) put them
after ``DraftEnabledSchema``.


.. code:: python

    from invenio_records_draft.marshmallow import \
        DraftEnabledSchema, always, published_only, draft_allowed

    class MetadataSchemaV1(DraftEnabledSchema, StrictKeysMixin):
        title = String(required=always, validate=[draft_allowed(Length(max=50))])
        abstract = String(required=published_only)
        # ...

    class RecordSchemaV1(DraftEnabledSchema, StrictKeysMixin):
        """Record schema."""

        metadata = fields.Nested(MetadataSchemaV1)
        # ...

Use ``required=always`` for properties that are required even in draft, ``required=published_only`` or
``required=True`` for props that are required only in published records.

Validators (validate=[xxx]) will be removed when validating draft records.
To enforce them for draft records wrap them with ``draft_allowed``.

Persistent identifiers
----------------------

This library supposes that draft and published records have the same value of their
persistent identifier and different ``pid_type`` s. This way the library is able to distinguish
them apart and at the same time keep link between them. If you create your own minters & loaders
for draft records, you have to honour this.

Record class
------------

To allow for schema validation on draft endpoint, create your own record classes:

.. code:: python

    class PublishedRecord(DraftEnabledRecordMixin, Record):
        def validate(self, **kwargs):
            self['$schema'] = current_jsonschemas.path_to_url('records/record-v1.0.0.json')
            return super().validate(**kwargs)


    class DraftRecord(DraftEnabledRecordMixin, Record):

        draft_validator = MarshmallowValidator(
            'sample.records.marshmallow:MetadataSchemaV1',  # marshmallow of the published version
            'records/record-v1.0.0.json'                    # json schema of the published version
        )

        def validate(self, **kwargs):
            self['$schema'] = current_jsonschemas.path_to_url('draft/records/record-v1.0.0.json')
            return super().validate(**kwargs)

When a draft record is validated, the ``draft_validator`` gets called and fills in property
``invenio_draft_validation`` that is stored both to invenio database and to elasticsearch:

.. code:: javascript

    {
        'id': 1,
        '$schema': '...',
        // ... other properties
        'invenio_draft_validation': {
            'valid': false,
            'errors': {
                'marshmallow': [
                    {
                        'field': 'title',
                        'message': 'Missing data for required field.'
                    }
                ]
            }
        }
    }

Endpoints, loaders and serializers
-----------------------------------

For common cases, use ``DRAFT_ENABLED_RECORDS_REST_ENDPOINTS`` that sets all the required
endpoint properties including marshmallow-assisted validation. See the sources of ``ext.py``
if you need small modifications. If you want to have more control on the created endpoints,
you can set up your own endpoints as usual, look at the following sections.

.. code:: python

    DRAFT_ENABLED_RECORDS_REST_ENDPOINTS = {
        'records': {
            'json_schemas': [
                'records/record-v1.0.0.json'
            ],
            'draft_pid_type': 'drecid',
            'draft_allow_patch': True,

            'record_marshmallow': RecordSchemaV1,
            'metadata_marshmallow': MetadataSchemaV1,

            'draft_record_class': DraftRecord,
            'published_record_class': PublishedRecord,

            'publish_permission_factory': allow_authenticated,
            'unpublish_permission_factory': allow_authenticated,
            'edit_permission_factory': allow_authenticated,
        }
    }


This configuration takes all the options that can be passed to
``RECORDS_REST_ENDPOINTS``. If an option is prefixed with ``draft_``, it will
be used only on the draft record endpoint. If it is prefixed with ``published_``,
it will be used only on published record endpoint. Unprefixed keys
will be used for both endpoints.

``draft_allow_patch`` will add an endpoint for JSON PATCH operation on draft.

The initial permissions are allow_all for drafts, allow_all for read on published,
allow_none for modifications on published, allow_all on delete operation. There are
two ways to modify these:


 * Use high-level options. ``read-permission-factory`` handles read operation
   (but not list that is always allow_all), ``modify_permission_factory``
   handles create/update/delete


.. code:: python

    RECORDS_REST_ENDPOINTS =
        draft_enabled_endpoint(
            # ... other options
            draft_read_permission_factory=check_elasticsearch,
            draft_modify_permission_factory=allow_role('editors'),
            published_read_permission_factory=allow_all
        )


Alternatively:

 * Use normal ``_imp`` options to set up permissions, but prefix them with ``draft_`` or ``published_``

Loaders
------------------

When registering schema to loader/serializer, wrap the schema that will be used on draft endpoint
with ``DraftSchemaWrapper``:

.. code:: python

    from invenio_records_draft.marshmallow import DraftSchemaWrapper

    # JSON loader using Marshmallow for data validation
    json_v1 = marshmallow_loader(DraftSchemaWrapper(MetadataSchemaV1))

Do not provide loader for published endpoint as create/update/patch will never be called on production
endpoint.

Serializers
-----------------

In serialization, you will need two serializers:

.. code:: python

    from invenio_records_draft.marshmallow import DraftSchemaWrapper

    json_v1 = JSONSerializer(RecordSchemaV1, replace_refs=True)
    draft_json_v1 = JSONSerializer(DraftSchemaWrapper(RecordSchemaV1), replace_refs=True)

    json_v1_response = record_responsify(json_v1, 'application/json')
    json_v1_search = search_responsify(json_v1, 'application/json')

    draft_json_v1_response = record_responsify(draft_json_v1, 'application/json')
    draft_json_v1_search = search_responsify(draft_json_v1, 'application/json')


REST Endpoints
-----------------

.. code:: python

    RECORDS_REST_ENDPOINTS = {
        'published_records': {
            'create_permission_factory_imp': '<function deny_all>',
            'default_endpoint_prefix': True,
            'delete_permission_factory_imp': '<function allow_all>',
            'item_route': '/records/<pid(recid,'
                          'record_class="sample.records.config:PublishedRecord"):pid_value>',
            'list_permission_factory_imp': '<function allow_all>',
            'list_route': '/records/',
            'pid_type': 'recid',
            'pid_fetcher': 'recid',
            'pid_minter': 'recid',
            'read_permission_factory_imp': '<function allow_all>',
            'record_class': "<class 'sample.records.config.PublishedRecord'>",
            'record_serializers': {
                'application/json': '<function record_responsify.<locals>.view>'
            },
            'search_index': 'records-record-v1.0.0',
            'search_serializers': {
                'application/json': '<function search_responsify.<locals>.view>'
            },
            'default_media_type': 'application/json',
            'links_factory_imp':
                '<invenio_records_draft.endpoints.PublishedLinksFactory object>',
            'update_permission_factory_imp': '<function deny_all>',
        },
        'draft_records': {
            'create_permission_factory_imp': '<function allow_all>',
            'default_endpoint_prefix': True,
            'delete_permission_factory_imp': '<function allow_all>',
            'item_route': 'drafts/records/<pid(drecid,'
                          'record_class="sample.records.config:DraftRecord"):pid_value>',
            'list_permission_factory_imp': '<function allow_all>',
            'list_route': 'drafts/records/',
            'pid_type': 'drecid',
            'pid_fetcher': 'drecid',
            'pid_minter': 'drecid',
            'read_permission_factory_imp': '<function allow_all>',
            'record_class': "<class 'sample.records.config.DraftRecord'>",
            'record_loaders': {
                'application/json': '<function marshmallow_loader.<locals>.json_loader>',
                'application/json-patch+json': '<function json_patch_loader>'
            },
            'record_serializers': {
                'application/json': '<function record_responsify.<locals>.view>'
            },
            'search_index': 'draft-records-record-v1.0.0',
            'search_serializers': {
                'application/json': '<function search_responsify.<locals>.view>'
            },
            'default_media_type': 'application/json',
            'update_permission_factory_imp': '<function allow_all>',
            'links_factory_imp':
                '<invenio_records_draft.endpoints.DraftLinksFactory object>',
        }
    }

Signals
=======

The following blinker signals are called prior/after to publishing/unpublishing/editing:

``collect_records(source,record,action)``

Called to collect all records that should be published/unpublished/made editable.
``record`` is an instance of ``RecordContext``, action is a ``CollectAction.PUBLISH``,
``CollectAction.UNPUBLISH``, ``CollectAction.EDIT``. Returns an iterator of extra
collected records.


``check_can_publish``, ``check_can_unpublish``, ``check_can_edit(source, record)``

Called on each collected record before the action. Can throw an exception to cancel
the process.

``before_publish``, ``before_unpublish``, ``before_edit(source, records)``

Called on list of ``RecordContext`` instances before the action

``before_publish_record``, ``before_unpublish_record(source, metadata, record, collected_records)``

Called before a single record is published/unpublished. ``record`` is the RecordContext
being published or unpublished. ``metadata`` are the metadata of the new (published/unpublished)
record that will be later on created/updated. ``collected_records`` is a list of all records
collected in the previous phases.

``after_publish``, ``after_unpublish``, ``after_edit(source, records)``

Called after the records have been published/unpublished/made editable.

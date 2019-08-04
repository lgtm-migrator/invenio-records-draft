========================
Invenio Records Draft
========================

.. image:: https://img.shields.io/github/license/oarepo/invenio-records-draft.svg
        :target: https://github.com/oarepo/invenio-records-draft/blob/master/LICENSE

.. image:: https://img.shields.io/travis/oarepo/invenio-records-draft.svg
        :target: https://travis-ci.org/oarepo/invenio-records-draft

.. image:: https://img.shields.io/coveralls/oarepo/invenio-records-draft.svg
        :target: https://coveralls.io/r/oarepo/invenio-records-draft

.. image:: https://img.shields.io/pypi/v/invenio-records-draft.svg
        :target: https://pypi.org/pypi/invenio-records-draft



**Not yet even alpha, do not use !!!**

This library helps to solve the situation where records in Invenio go through draft stage before they
are published. The following should hold:

    1. Draft records should follow the same json schema as published records with the exception
       that all/most properties are not required even though they are marked as such
    2. Draft records should follow the same marshmallow schema as published records with
       some exceptions:

        a. all/most properties are not required even though they are marked as such
        b. for properties that have validators attached these validations will be ignored,
           unless they are explicitly marked with `draft_allowed`.

    3. If wished, draft records may not follow the schema at all. In this case, the record
       metadata passed to elasticsearch must include only the valid properties according
       to the previous point.

    4. "Draft" records live at a different endpoint than published ones. The recommended URL
       is `/api/records` for the published records and `/api/draft-records` for drafts

    5. Draft and published records share the same `recid`.

    6. Published records can not be directly created/updated/patched. Draft records can be
       created/updated/patched.

    7. GET on a published record returns top-level section and HTTP header `links`.
       Apart from `self` the section contains:

        a. `draft` - a url that links to the "draft" version of the record. This url is present
           only if the draft version of the record exists
        b. `edit` - URL to a handler that creates a draft version of the record and then
           returns HTTP 302 redirect to the draft version. This url is present only if the
           draft version does not exist
        c. `unpublish` - URL to a handler that creates a draft version of the record
           if it does not exist, removes the published version and then returns HTTP 302 to the draft.

    8. On a draft record the `links` also contain:

        a. `published` - a url that links to the "published" version of the record. This url is present
           only if the published version of the record exists

        a. `publish` - a POST to this url publishes the record. The JSONSchema and marshmallow
           schema of the published record must pass. After the publishing the draft record is
           deleted. HTTP 302 is returned pointing to the published record.

    9. The serialized representation of a draft record contains a section named `validation`.
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

This command will create a draft schema in `INVENIO_RECORD_DRAFT_SCHEMAS_DIR`, default value
is `var/instance/draft_schemas/` and will print out the created schema path:

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
      "_draft_validation": {
        "type": "object",
        "properties": {
          "valid": {
            "type": "boolean"
          },
          "errors": {
            "type": "object",
            "enabled": false
          }
        }
      }
    }

The second deploys the schema to elasticsearch as `draft-records-record-v1.0.0`
and creates alias `draft-records`.

To check that the command worked GET http://localhost:9200/draft-records-record-v1.0.0

Marhsmallow Schema
----------------------

Inherit your marshmallow schema from `DraftEnabledSchema`. If you use mixins that
inherit from Schema (such as StrictKeysMixin) put them after `DraftEnabledSchema`.


.. code:: python

    from invenio_records_draft.marshmallow import DraftEnabledSchema, always, published_only, draft_allowed

    class MetadataSchemaV1(DraftEnabledSchema, StrictKeysMixin):
        title = String(required=always, validate=[draft_allowed(Length(max=50))])
        abstract = String(required=published_only)
        # ...

    class RecordSchemaV1(DraftEnabledSchema, StrictKeysMixin):
        """Record schema."""

        metadata = fields.Nested(MetadataSchemaV1)
        # ...

Use `required=always` for properties that are required even in draft, `required=published_only` or
`required=True` for props that are required only in published records.

Validators (validate=[xxx]) will be removed when validating draft records.
To enforce them for draft records wrap them with `draft_allowed`.

Loaders
------------------

When registering schema to loader/serializer, wrap the schema that will be used on draft endpoint
with `DraftSchemaWrapper`:

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
        'published': dict(
            default_endpoint_prefix=True,
            search_index='records',
            record_serializers={
                'application/json': ('my_site.records.serializers'
                                     ':json_v1_response'),
            },
            search_serializers={
                'application/json': ('my_site.records.serializers'
                                     ':json_v1_search'),
            },
            record_loaders={},
            list_route='/records/',
            item_route='/records/<pid(recid):pid_value>',
            create_permission_factory_imp=deny_all,
            update_permission_factory_imp=deny_all,
            delete_permission_factory_imp=deny_all,
        ),
        'draft': dict(
            default_endpoint_prefix=False,
            search_index='draft-records',
            record_serializers={
                'application/json': ('my_site.records.serializers'
                                     ':draft_json_v1_response'),
            },
            search_serializers={
                'application/json': ('my_site.records.serializers'
                                     ':draft_json_v1_search'),
            },
            record_loaders={
                'application/json': ('my_site.records.loaders'
                                     ':draft_json_v1'),
            },
            list_route='/draft-records/',
            item_route='/draft-records/<pid(recid):pid_value>',
            create_permission_factory_imp=allow_all,
            read_permission_factory_imp=check_elasticsearch,
            update_permission_factory_imp=allow_all,
            delete_permission_factory_imp=allow_all,
            list_permission_factory_imp=allow_all
        )
    }

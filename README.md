Invenio Records Draft
=====================

[![image][]][1] [![image][2]][3] [![image][4]][5] [![image][6]][7]

**Beta version, use at your own risk!!!**

  [image]: https://img.shields.io/github/license/oarepo/invenio-records-draft.svg
  [1]: https://github.com/oarepo/invenio-records-draft/blob/master/LICENSE
  [2]: https://img.shields.io/travis/oarepo/invenio-records-draft.svg
  [3]: https://travis-ci.org/oarepo/invenio-records-draft
  [4]: https://img.shields.io/coveralls/oarepo/invenio-records-draft.svg
  [5]: https://coveralls.io/r/oarepo/invenio-records-draft
  [6]: https://img.shields.io/pypi/v/oarepo-invenio-records-draft.svg
  [7]: https://pypi.org/pypi/oarepo-invenio-records-draft
  
## What the library does

Easily adds draft (a.k.a deposit) to all your invenio data models. REST API stays the same with extra operations
for publish, unpublish, edit published record. REST example (some links omitted for brevity):

```bash
$ curl --header "Content-Type: application/json" \
  --request POST \
  --data '{"title":"blah"}' \
  https://localhost:5000/api/draft/records/

returns:
    {
      "metadata": {
        "title": "blah",
        "oarepo:validity": {
          "valid": false,
          "marshmallow": [
            "field": "title",
            "message": "too short"
          ]
        }
      }
    }


$ curl --header "Content-Type: application/json" \
  --request PUT \
  --data '{"title":"longer blah"}' \
  https://localhost:5000/api/draft/records/1

returns:
    {
      "links": {
        "publish": "https://localhost:5000/api/draft/records/1/publish/"
      },
      "metadata": {
        "title": "longer blah",
        "oarepo:validity": {
          "valid": true
        }
      }
    }


$ curl --request POST \
  https://localhost:5000/api/draft/records/1/publish/

returns:
    302 Location https://localhost:5000/api/records/1
```

## Installation

```bash
pip install oarepo-records-draft oarepo-validate
```

## Configuration

To enable the library for your data model, you have to perform the following steps:

  * write the "published" version of your model, including marshmallow, mapping and json schemas.
  * Inherit the record from ``SchemaKeepingRecordMixin`` and ``MarshmallowValidatedRecordMixin``
    from ``oarepo-validate`` modules. See [oarepo-validate](https://github.com/oarepo/oarepo-validate)
    library for details on on-record validation vs. rest-access validation.  
    Have a look at [a sample record](sample/sample/record.py)
  * Drop marshmallow loader & serializer from loaders and serializers, see oarepo-validate for details
  * Move the configuration of rest endpoint from ``RECORDS_REST_ENDPOINTS`` to ``RECORDS_DRAFT_ENDPOINTS``.
    Add ``"draft": "<draftpid>"`` to the configuration, where ``draftpid`` is any unused pid type
    less or equal 6 chars in length.
```python
RECORDS_DRAFT_ENDPOINTS = {             # <--- moved here
    'recid': dict(
        draft='drecid',                 # <--- added here
        pid_type='recid',
        pid_minter='recid',
        pid_fetcher='recid',
        list_route='/records/',
        item_route='/records/<{0}:pid_value>'.format(RECORD_PID),
        # rest of the stuff here
    ),
}
RECORDS_REST_ENDPOINTS = {}             # <--- made empty 
```  
  * Do not forget to propagate this variable to the application's config (for example, in ext/init_config)
  * Add endpoint for draft to the same dict:
```python
RECORDS_DRAFT_ENDPOINTS = {        
    'recid': dict(
        draft='drecid',
        # as above
    ),
    'drecid': dict(                     # <--- added here
    
    )
}
```  
  * move create/update/delete permission factories from the published endpoint to the draft one
    - published record will automatically get ``deny_all`` for all modification operations
    - in the example below everyone can create/update/delete draft record, which is probably not what you want
```python
RECORDS_DRAFT_ENDPOINTS = {            
    'recid': dict(
        # as above                      
    ),
    'drecid': dict(                     # <--- moved here
        create_permission_factory_imp=allow_all,
        delete_permission_factory_imp=allow_all,
        update_permission_factory_imp=allow_all,
    )
}
```    
  * on published endpoint, add permission factories for publish/unpublish/edit
```python
RECORDS_DRAFT_ENDPOINTS = {            
    'recid': dict(
        # as above                      # <--- added here    
        publish_permission_factory_imp=allow_logged_in,
        unpublish_permission_factory_imp=allow_logged_in,
        edit_permission_factory_imp=allow_logged_in,
    ),
    'drecid': dict(                     
        create_permission_factory_imp=allow_all,
        delete_permission_factory_imp=allow_all,
        update_permission_factory_imp=allow_all,
    )
}
```    

Run ``invenio index init/create``, start server and you're done. A new endpoint has been created for you 
and is at ``/api/draft/records``. The whole configuration is in [sample app](sample/sample/)

## Library principles:

1.  Draft records follow the same json schema as published records with the exception 
    that:
    > 1.  invalid records are stored and indexed
    > 2.  all properties are not required even though they are marked as such. 
    > 3.  Extra properties not defined in marshmallow/json schema can be stored but are 
          marked invalid and the properties are not indexed in ES.

2.  "Draft" records live at a different endpoint and different ES index
    than published ones. The recommended URL is `/api/records` for the
    published records and `/api/draft/records` for drafts

3.  Draft and published records share the same value of pid but have two
    different pid types

4.  Published records can not be directly created/updated/patched. Draft
    records can be created/updated/patched.

5.  Invenio record contains `Link` header and `links` section in the
    JSON payload. Links of a published record contain (apart from
    `self`):

    > 1.  `draft` - a url that links to the "draft" version of the
         record. This url is present only if the draft version of the
         record exists and the caller has the rights to edit the draft
    > 2.  `edit` - URL to a handler that creates a draft version of the
         record and then returns HTTP 302 redirect to the draft
         version. This url is present only if the draft version does
         not exist
    > 3.  `unpublish` - URL to a handler that creates a draft version of
         the record if it does not exist, deletes the published version
         and then returns HTTP 302 to the draft.

6.  On a draft record the `links` contain (apart from `self`):

    > 1.  `published` - a url that links to the "published" version of
         the record. This url is present only if the published version
         of the record exists
    > 2.  `publish` - a POST to this url publishes the record. The
         JSONSchema and marshmallow schema of the published record must
         pass. After the publishing the draft record is deleted. HTTP
         302 is returned pointing to the published record.

7.  The serialized representation of a draft record contains a section
    named `oarepo:validity`. This section contains the result
    of marshmallow and JSONSchema validation against original schemas.

8. Deletion of a published record does not delete the draft record.

9. Deletion of a draft record does not delete the published record.

10. All properties on published RECORDS_REST_ENDPOINTS are propagated to the draft endpoint,
   some of those modified. For a complete list/algorithm, see 
   [setup_draft_endpoint method in endpoints.py](oarepo_records_draft/endpoints.py)

## REST API

Normal invenio-records-rest API is available both on ``draft`` and ``published`` endpoints,
with the exception that published endpoints have the implicit permissions of ``create/update/delete`` 
operations set to ``deny_all``. 

### Publishing draft record

Let's create a record (security not shown here):

```bash
$ curl --header "Content-Type: application/json" \
  --request POST \
  --data '{"title":"blah"}' \
  https://localhost:5000/api/draft/records/

201 Location https://localhost:5000/api/draft/records/1
```

And get it to see, if it is valid:

```bash
$ curl https://localhost:5000/api/draft/records/1

{
  links: {
    self: https://localhost:5000/api/draft/records/1,
    publish: https://localhost:5000/api/draft/records/1/publish/
  },
  metadata: {
    "title": "blah",
    "oarepo:validity": {
       "valid": true
     }
  }
}
```

As it is valid, we can publish the record (security not shown here):

```bash
$ curl --request POST \
  https://localhost:5000/api/draft/records/1/publish/

302 Location https://localhost:5000/api/records/1
```

And when retrieved, it does not contain the validation section:

```bash
$ curl https://localhost:5000/api/records/1

{
  links: {
    self: https://localhost:5000/api/records/1,
    unpublish: https://localhost:5000/api/records/1/unpublish/,
    edit: https://localhost:5000/api/records/1/edit/
  },
  metadata: {
    "title": "blah"
  }
}
```

### Editing published record

Published record can not be edited in place, at first a draft record should be created. See the links
section above for edit url:

```bash
$ curl --request POST \
  https://localhost:5000/api/records/1/edit/

302 Location https://localhost:5000/api/draft/records/1
```

Now the published record is still available (and not modified) and you have a url for the 
draft record for making your changes. When finished, run ``publish`` action above to publish
your changes.

### Unpublishing published record

To remove a published record and "move" it to draft, call unpublish:

```bash
$ curl --request POST \
  https://localhost:5000/api/records/1/unpublish/

302 Location https://localhost:5000/api/draft/records/1
```

After this action, the published record is deleted (and says 410 gone) and draft record is created.
You can delete the draft record if desired or update and publish it again.

## Python API

The entrypoint to python API is at ``oarepo_records_draft.current_drafts``. It has the following
public methods:

### ``publish(record: Record, record_pid: PersistentIdentifier)``

Publishes an instance of draft record with draft pid ``record_pid``. 
Raises InvalidRecordException if the record is not valid (according to jsonschema/marshmallow)
and can not be published. Returns a list of 
``(draft_record: Record, published_record_context: RecordContext)`` tuples.

#### What it does:

   1. invokes ``collect_records_for_action`` signal to collect all records that should be published
      (sometimes linked records should be published as well)
   2. calls ``check_can_publish`` signal for each collected record
   3. calls ``before_publish`` signal
   4. for each record in reversed collected records publishes the record and deletes draft one
   5. calls ``after_publish`` signal
   6. for each record removes draft record from elasticsearch and indexes published one
   7. refreshes affected ES indices
   
### ``unpublish(record: Record, record_pid: PersistentIdentifier)``

Removes published instance and creates a draft one. ``record`` is the published record being
unpublished, ``record_pid`` is its persistent identifier.

Returns a list of 
``(published_record: Record, draft_record_context: RecordContext)`` tuples.

#### What it does:

   1. invokes ``collect_records_for_action`` signal to collect all records that should be published
      (sometimes linked records should be published as well)
   2. calls ``check_can_unpublish`` signal for each collected record
   3. calls ``before_unpublish`` signal
   4. for each record in reversed collected records removes the published record and creates draft
   5. calls ``after_unpublish`` signal
   6. for each record removes published record from elasticsearch and indexes draft one
   7. refreshes affected ES indices
   
   
### ``edit(record: Record, record_pid: PersistentIdentifier)``

Keeps published instance and creates a draft one. ``record`` is the published record to be edited
, ``record_pid`` is its persistent identifier.

Returns a list of 
``(published_record: Record, draft_record_context: RecordContext)`` tuples.

#### What it does:

   1. invokes ``collect_records_for_action`` signal to collect all records that should be published
      (sometimes linked records should be published as well)
   2. calls ``check_can_edit`` signal for each collected record
   3. calls ``before_edit`` signal
   4. for each record in reversed collected records removes creates draft record
   5. calls ``after_edit`` signal
   6. Indexes each created draft record in ES
   7. refreshes affected ES indices

### Signals

See [signals.py](oarepo_records_draft/signals.py) for the exhaustive list of signals

## Q&A

### Can I provide my own record class for draft records?

Yes. The class has to inherit ``DraftRecordMixin``, ``SchemaKeepingRecordMixin`` and 
``MarshmallowValidatedRecordMixin``. ``DraftRecordMixin`` should be the first mixin.

Set ``record_class`` property in ``RECORDS_DRAFT_ENDPOINTS/<your draft endpoint>``

### Can I provide my own link factory for either draft or published record?

Yes. Provide ``links_factory_imp`` as usual and it will get called. URLs for 
publishing/unpublishing/editing will be added automatically

### Can I change XXX in rest config?

Yes, you can. Some of the values are automatically provided for drafts, please
consult [endpoints.py](oarepo_records_draft/endpoints.py) to see if the value
should be modified for draft record or not.

### I have my own ``record_to_index`` implementation. Is this library compatible?

Might be. See [record.py](oarepo_records_draft/record.py) to see which index must be used
for draft records.

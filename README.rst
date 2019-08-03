Invenio Records Draft
=====================

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

    7. The serialized represetation of a published record contains a section named `links`.
       Apart from `self` the section contains:

        a. `draft` - a url that links to the "draft" version of the record. This url is present
           only if the draft version of the record exists
        b. `edit` - URL to a handler that creates a draft version of the record and then
           returns HTTP 302 redirect to the draft version. This url is present only if the
           draft version does not exist
        c. `unpublish` - URL to a handler that creates a draft version of the record
           if it does not exist, removes the published version and then returns HTTP 302 to the draft.

    8. The serialized represetation of a draft record contains a section named `links`.
       Apart from `self` the section contains:

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


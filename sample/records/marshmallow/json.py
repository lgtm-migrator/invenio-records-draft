# -*- coding: utf-8 -*-
#
# Copyright (C) 2019 CERN.
#
# My site is free software; you can redistribute it and/or modify it under
# the terms of the MIT License; see LICENSE file for more details.

"""JSON Schemas."""

from __future__ import absolute_import, print_function

from invenio_records_rest.schemas import Nested, StrictKeysMixin
from invenio_records_rest.schemas.fields import (
    DateString,
    PersistentIdentifier,
    SanitizedUnicode,
)
from marshmallow import fields, missing, validate

from invenio_records_draft.marshmallow import (
    DraftEnabledSchema,
    DraftValidationSchemaV1Mixin,
)
from invenio_records_draft.utils import load_dump


class MetadataSchemaV1(DraftValidationSchemaV1Mixin, DraftEnabledSchema, StrictKeysMixin):
    """Schema for the record metadata."""

    id = PersistentIdentifier()
    title = SanitizedUnicode(required=True, validate=validate.Length(min=1, max=10))
    keywords = fields.List(SanitizedUnicode(), many=True)
    publication_date = DateString()
    schema = SanitizedUnicode(required=True, attribute='$schema',
                              **load_dump('$schema'))


class RecordSchemaV1(DraftEnabledSchema, StrictKeysMixin):
    """Record schema."""

    metadata = fields.Nested(MetadataSchemaV1)
    created = fields.Str(dump_only=True)
    revision = fields.Integer(dump_only=True)
    updated = fields.Str(dump_only=True)
    links = fields.Dict(dump_only=True)
    id = PersistentIdentifier()

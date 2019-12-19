from unittest.mock import Mock

import pytest
from marshmallow import Schema, ValidationError
from marshmallow.fields import Integer, Nested
from marshmallow.utils import missing as missing_

from invenio_records_draft.marshmallow import (
    DraftEnabledSchema,
    DraftField,
    DraftSchemaWrapper,
    always,
    draft_allowed,
    published_only,
)
from tests.helpers import marshmallow_load


def test_draft_field_required():
    schema = Mock()
    schema.context = {
        'draft': False
    }
    fld = DraftField(schema, Integer(required=True, validators=[], allow_none=False))
    assert fld.required
    assert not fld.allow_none

    assert fld.serialize('a', {'a': 1}) == 1
    assert fld.deserialize(1) == 1
    with pytest.raises(ValidationError):
        fld.deserialize(missing_)

    schema.context = {
        'draft': True
    }
    assert not fld.required
    assert fld.allow_none

    assert fld.serialize('a', {'a': 1}) == 1
    assert fld.deserialize(1) == 1
    assert fld.deserialize(None) is None


def test_draft_field_required_always():
    schema = Mock()
    schema.context = {
        'draft': False
    }
    fld = DraftField(schema, Integer(required=always, validators=[], allow_none=False))
    assert fld.required
    assert not fld.allow_none

    assert fld.serialize('a', {'a': 1}) == 1
    assert fld.deserialize(1) == 1
    with pytest.raises(ValidationError):
        fld.deserialize(missing_)

    schema.context = {
        'draft': True
    }
    assert fld.required
    assert fld.allow_none
    #
    # assert fld.serialize('a', {'a': 1}) == 1
    # assert fld.deserialize(1) == 1
    with pytest.raises(ValidationError):
        fld.deserialize(missing_)


def test_draft_field_required_published_only():
    schema = Mock()
    schema.context = {
        'draft': False
    }
    fld = DraftField(schema, Integer(required=published_only, validators=[], allow_none=False))
    assert fld.required
    assert not fld.allow_none

    assert fld.serialize('a', {'a': 1}) == 1
    assert fld.deserialize(1) == 1
    with pytest.raises(ValidationError):
        fld.deserialize(missing_)

    schema.context = {
        'draft': True
    }
    assert not fld.required
    assert fld.allow_none

    assert fld.serialize('a', {'a': 1}) == 1
    assert fld.deserialize(1) == 1
    assert fld.deserialize(None) is None


def test_dump():
    class TestSchema(DraftEnabledSchema):
        fld = Integer(required=True)

    class NormalSchema(Schema):
        fld = Integer(required=True)

    schema = TestSchema()
    normal = NormalSchema()
    assert schema.declared_fields['fld'].as_string == normal.declared_fields['fld'].as_string
    assert schema.dump({'fld': 1}) == normal.dump({'fld': 1})
    assert schema.dump({'fld': None}) == normal.dump({'fld': None})

    schema = DraftSchemaWrapper(TestSchema)()
    assert schema.dump({'fld': None}) == normal.dump({'fld': None})


def test_load():
    class TestSchema(DraftEnabledSchema):
        fld = Integer(required=True)

    schema = TestSchema()
    assert marshmallow_load(schema, {'fld': 1}) == {'fld': 1}

    with pytest.raises(ValidationError) as exc:
        marshmallow_load(schema, {'fld': None})
    assert exc.value.args[0] == {'fld': ['Field may not be null.']}

    schema = DraftSchemaWrapper(TestSchema)()
    assert marshmallow_load(schema, {'fld': None}) == {'fld': None}


def test_load_nested():
    class TestNestedSchema(DraftEnabledSchema):
        fld = Integer(required=True)

    class TestSchema(DraftEnabledSchema):
        nest = Nested(TestNestedSchema)

    class TestSchema2(DraftEnabledSchema):
        nest = Nested(TestNestedSchema())

    schema = TestSchema()
    schema2 = TestSchema2()
    assert marshmallow_load(schema, {'nest': {'fld': 1}}) == {'nest': {'fld': 1}}
    assert marshmallow_load(schema2, {'nest': {'fld': 1}}) == {'nest': {'fld': 1}}

    err = {'nest': {'fld': ['Field may not be null.']}}

    with pytest.raises(ValidationError) as exc:
        assert marshmallow_load(schema, {'nest': {'fld': None}}) == err
    assert exc.value.args[0] == err
    with pytest.raises(ValidationError) as exc:
        assert marshmallow_load(schema2, {'nest': {'fld': None}}) == err
    assert exc.value.args[0] == err

    schema = DraftSchemaWrapper(TestSchema)()
    assert marshmallow_load(schema, {'nest': {'fld': None}}) == {'nest': {'fld': None}}

    schema2 = DraftSchemaWrapper(TestSchema)()
    assert marshmallow_load(schema2, {'nest': {'fld': None}}) == {'nest': {'fld': None}}


def test_validators():
    class TestSchema(DraftEnabledSchema):
        fld = Integer(required=True, validate=[lambda x: x > 1])

    schema = TestSchema()
    assert marshmallow_load(schema, {'fld': 10}) == {'fld': 10}
    with pytest.raises(ValidationError) as exc:
        marshmallow_load(schema, {'fld': 1})
    assert exc.value.args[0] == {'fld': ['Invalid value.']}

    with pytest.raises(ValidationError) as exc:
        marshmallow_load(schema, {'fld': None})
    assert exc.value.args[0] == {'fld': ['Field may not be null.']}

    schema = DraftSchemaWrapper(TestSchema)()
    assert marshmallow_load(schema, {'fld': 10}) == {'fld': 10}
    assert marshmallow_load(schema, {'fld': 1}) == {'fld': 1}
    assert marshmallow_load(schema, {'fld': None}) == {'fld': None}


def test_validators_allowed():
    class TestSchema(DraftEnabledSchema):
        fld = Integer(required=True, validate=[draft_allowed(lambda x: x > 1)])

    schema = TestSchema()
    assert marshmallow_load(schema, {'fld': 10}) == {'fld': 10}

    with pytest.raises(ValidationError) as exc:
        marshmallow_load(schema, {'fld': 1})
    assert exc.value.args[0] == {'fld': ['Invalid value.']}

    with pytest.raises(ValidationError) as exc:
        marshmallow_load(schema, {'fld': None})
    assert exc.value.args[0] == {'fld': ['Field may not be null.']}

    schema = DraftSchemaWrapper(TestSchema)()
    assert marshmallow_load(schema, {'fld': 10}) == {'fld': 10}

    with pytest.raises(ValidationError) as exc:
        marshmallow_load(schema, {'fld': 1})
    assert exc.value.args[0] == {'fld': ['Invalid value.']}

    assert marshmallow_load(schema, {'fld': None}) == {'fld': None}

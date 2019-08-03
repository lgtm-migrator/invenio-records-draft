import copy

import wrapt
from marshmallow import Schema


class DraftField(wrapt.ObjectProxy):
    def __init__(self, schema, field):
        super().__init__(field)
        self._self_schema = schema

    @property
    def validators(self):
        if self._self_schema.context.get('draft', False):
            # TODO: possibility to say which validators are enabled
            return []
        return self.__wrapped__.validators

    @property
    def required(self):
        if self._self_schema.context.get('draft', False):
            # TODO: possibility to say if required in draft mode
            return False
        return self.__wrapped__.required

    @property
    def allow_none(self):
        if self._self_schema.context.get('draft', False):
            # TODO: possibility to say if none allowed in draft mode
            return True
        return self.__wrapped__.allow_none

    def serialize(self, attr, obj, accessor=None):
        return self.__wrapped__.__class__.serialize(self, attr, obj, accessor=accessor)

    def deserialize(self, value, attr=None, data=None):
        return self.__wrapped__.__class__.deserialize(self, value, attr=attr, data=data)

    def _validate_missing(self, value):
        return self.__wrapped__.__class__._validate_missing(self, value)

    def _validate(self, value):
        return self.__wrapped__.__class__._validate(self, value)

    @property
    def as_string(self):
        return self.__wrapped__.as_string

    def __deepcopy__(self, memodict={}):
        val = copy.deepcopy(self.__wrapped__, memo=memodict)
        return DraftField(self._self_schema, val)


class DraftEnabledSchema(Schema):
    def __init__(self, *args, **kwargs):
        self._declared_fields = {
            k: DraftField(self, v) for k, v in self._declared_fields.items()
        }
        super().__init__(*args, **kwargs)


def DraftSchemaWrapper(schema):
    assert issubclass(schema, DraftEnabledSchema)

    def wrapper(*args, **kwargs):
        kwargs['context'] = {
            'draft': True,
            **(kwargs.get('context', {}))
        }
        return schema(*args, **kwargs)

    return wrapper


__all__ = ('DraftSchemaWrapper', 'DraftEnabledSchema', 'DraftField')

from marshmallow import Schema, fields, validate, INCLUDE


class SampleSchemaV1(Schema):
    title = fields.String(validate=validate.Length(min=5), required=True)

    class Meta:
        unknown = INCLUDE

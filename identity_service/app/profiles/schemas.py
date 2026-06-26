from marshmallow import (
    Schema,
    ValidationError,
    fields,
    pre_load,
    validate,
    validates_schema,
)


class NormalizedSchema(Schema):
    @pre_load
    def trim_strings(self, data, **kwargs):
        if not isinstance(data, dict):
            return data

        return {
            key: value.strip() if isinstance(value, str) else value
            for key, value in data.items()
        }


class NonEmptySchema(NormalizedSchema):
    @validates_schema
    def require_at_least_one_field(self, data, **kwargs):
        if not data:
            raise ValidationError("Provide at least one field.")


class BasicProfileSchema(NonEmptySchema):
    bio = fields.String(
        allow_none=True,
        validate=validate.Length(max=500),
    )
    date_of_birth = fields.Date(allow_none=True)
    gender = fields.String(
        allow_none=True,
        validate=validate.Length(max=50),
    )
    occupation = fields.String(
        allow_none=True,
        validate=validate.Length(max=100),
    )
    website = fields.Url(allow_none=True)


class AddressCreateSchema(NormalizedSchema):
    address_line_1 = fields.String(
        required=True,
        validate=validate.Length(min=1, max=150),
    )
    address_line_2 = fields.String(
        allow_none=True,
        validate=validate.Length(max=150),
    )
    city = fields.String(
        required=True,
        validate=validate.Length(min=1, max=100),
    )
    state = fields.String(
        allow_none=True,
        validate=validate.Length(max=100),
    )
    postal_code = fields.String(
        allow_none=True,
        validate=validate.Length(max=20),
    )
    country = fields.String(
        required=True,
        validate=validate.Length(min=1, max=100),
    )


class AddressUpdateSchema(NonEmptySchema):
    address_line_1 = fields.String(
        validate=validate.Length(min=1, max=150),
    )
    address_line_2 = fields.String(
        allow_none=True,
        validate=validate.Length(max=150),
    )
    city = fields.String(
        validate=validate.Length(min=1, max=100),
    )
    state = fields.String(
        allow_none=True,
        validate=validate.Length(max=100),
    )
    postal_code = fields.String(
        allow_none=True,
        validate=validate.Length(max=20),
    )
    country = fields.String(
        validate=validate.Length(min=1, max=100),
    )


class EventCreateSchema(NormalizedSchema):
    event_name = fields.String(
        required=True,
        validate=validate.Length(min=1, max=80),
    )
    event_date = fields.Date(required=True)
    description = fields.String(
        allow_none=True,
        validate=validate.Length(max=300),
    )
    recurring = fields.Boolean(load_default=True)


class EventUpdateSchema(NonEmptySchema):
    event_name = fields.String(
        validate=validate.Length(min=1, max=80),
    )
    event_date = fields.Date()
    description = fields.String(
        allow_none=True,
        validate=validate.Length(max=300),
    )
    recurring = fields.Boolean()

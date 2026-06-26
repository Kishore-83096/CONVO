from marshmallow import EXCLUDE, Schema, fields, pre_load, validate


class SearchContactSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    contact_number = fields.Raw(required=True)


class AddContactSchema(SearchContactSchema):
    saved_name = fields.String(
        required=True,
        validate=validate.Length(min=1, max=100),
    )

    @pre_load
    def normalize_saved_name(self, data, **kwargs):
        if not isinstance(data, dict):
            return data

        normalized = dict(data)
        if isinstance(normalized.get("saved_name"), str):
            normalized["saved_name"] = normalized["saved_name"].strip()
        return normalized


class RenameContactSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    saved_name = fields.String(
        required=True,
        validate=validate.Length(min=1, max=100),
    )

    @pre_load
    def normalize_saved_name(self, data, **kwargs):
        if not isinstance(data, dict):
            return data

        normalized = dict(data)
        if isinstance(normalized.get("saved_name"), str):
            normalized["saved_name"] = normalized["saved_name"].strip()
        return normalized

from marshmallow import (
    EXCLUDE,
    Schema,
    ValidationError,
    fields,
    pre_load,
    validate,
    validates_schema,
)


USERNAME_PATTERN = r"^[a-z0-9_]+$"


class RegisterSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    full_name = fields.String(
        required=True,
        validate=validate.Length(min=2, max=100),
    )
    username = fields.String(
        required=True,
        validate=[
            validate.Length(min=3, max=30),
            validate.Regexp(
                USERNAME_PATTERN,
                error=(
                    "Username may contain only lowercase letters, "
                    "numbers, and underscores."
                ),
            ),
        ],
    )
    password = fields.String(
        required=True,
        load_only=True,
        validate=validate.Length(min=8, max=128),
    )
    confirm_password = fields.String(
        required=True,
        load_only=True,
        validate=validate.Length(max=128),
    )

    @pre_load
    def normalize_input(self, data, **kwargs):
        if not isinstance(data, dict):
            return data

        normalized = dict(data)

        if isinstance(normalized.get("full_name"), str):
            normalized["full_name"] = " ".join(
                normalized["full_name"].split()
            )

        if isinstance(normalized.get("username"), str):
            username = normalized["username"].strip().lower()
            normalized["username"] = username.removeprefix("@")

        return normalized

    @validates_schema
    def validate_password_confirmation(self, data, **kwargs):
        password = data.get("password")
        confirmation = data.get("confirm_password")

        if password is not None and confirmation != password:
            raise ValidationError(
                "Passwords do not match.",
                field_name="confirm_password",
            )


class LoginSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    method = fields.String(
        required=True,
        validate=validate.OneOf(
            ["email", "contact_number", "username"]
        ),
    )
    identifier = fields.Raw(required=True)
    password = fields.String(
        required=True,
        load_only=True,
        validate=validate.Length(min=1, max=128),
    )

    @pre_load
    def normalize_method(self, data, **kwargs):
        if not isinstance(data, dict):
            return data

        normalized = dict(data)
        if isinstance(normalized.get("method"), str):
            normalized["method"] = (
                normalized["method"].strip().lower()
            )
        return normalized


class AccountCredentialsSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    username = fields.String(
        required=True,
        validate=validate.Length(min=1, max=30),
    )
    email = fields.Email(required=True)
    contact_number = fields.Raw(required=True)
    current_password = fields.String(
        required=True,
        load_only=True,
        validate=validate.Length(min=1, max=128),
    )

    @pre_load
    def normalize_identifiers(self, data, **kwargs):
        if not isinstance(data, dict):
            return data

        normalized = dict(data)

        if isinstance(normalized.get("username"), str):
            normalized["username"] = (
                normalized["username"]
                .strip()
                .lower()
                .removeprefix("@")
            )

        if isinstance(normalized.get("email"), str):
            normalized["email"] = normalized["email"].strip().lower()

        return normalized


class ResetPasswordSchema(AccountCredentialsSchema):
    new_password = fields.String(
        required=True,
        load_only=True,
        validate=validate.Length(min=8, max=128),
    )
    confirm_new_password = fields.String(
        required=True,
        load_only=True,
        validate=validate.Length(max=128),
    )


class DeleteAccountSchema(AccountCredentialsSchema):
    pass

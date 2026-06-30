from flask import Blueprint, request
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required

from app.auth.schemas import (
    DeleteAccountSchema,
    LoginSchema,
    RegisterSchema,
    ResetPasswordSchema,
    ValidateUsersSchema
)
from app.auth.services import (
    delete_user_account,
    login_user,
    logout_session,
    register_user,
    reset_user_password,
    user_details,
    validate_user_ids,
)
from app.extensions import limiter
from app.shared.exceptions import ApiError
from app.shared.responses import api_response


auth_blueprint = Blueprint("auth", __name__)
register_schema = RegisterSchema()
login_schema = LoginSchema()
reset_password_schema = ResetPasswordSchema()
delete_account_schema = DeleteAccountSchema()
validate_users_schema = ValidateUsersSchema()

def json_request_body() -> dict:
    payload = request.get_json(silent=True)

    if not isinstance(payload, dict):
        raise ApiError("Request body must be a JSON object.")

    return payload


@auth_blueprint.post("/register")
@limiter.limit("5 per minute")
def register():
    payload = register_schema.load(json_request_body())
    user = register_user(payload)

    return api_response(
        success=True,
        message="Account created.",
        data=user_details(user, include_username=True),
        status_code=201,
    )


@auth_blueprint.post("/login")
@limiter.limit("10 per minute")
def login():
    payload = login_schema.load(json_request_body())
    user, access_token, expires_at = login_user(payload)

    return api_response(
        success=True,
        message="User logged in.",
        data={
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_at": expires_at.isoformat(),
            "user": user_details(user,include_username=True),
        },
        status_code=200,
    )


@auth_blueprint.post("/reset-password")
@limiter.limit("5 per minute")
@jwt_required()
def reset_password():
    payload = reset_password_schema.load(json_request_body())
    reset_user_password(int(get_jwt_identity()), payload)

    return api_response(
        success=True,
        message="Password has been changed successfully. Log in again.",
        status_code=200,
    )


@auth_blueprint.delete("/delete-account")
@limiter.limit("3 per minute")
@jwt_required()
def delete_account():
    payload = delete_account_schema.load(json_request_body())
    delete_user_account(int(get_jwt_identity()), payload)

    return api_response(
        success=True,
        message="Account and all associated data deleted permanently.",
        status_code=200,
    )


@auth_blueprint.post("/logout")
@jwt_required()
def logout():
    logout_session(get_jwt()["jti"])

    return api_response(
        success=True,
        message="User logged out.",
        status_code=200,
    )




@auth_blueprint.post("/users/validate")
def validate_users():
    payload = validate_users_schema.load(
        json_request_body()
    )

    result = validate_user_ids(
        payload["user_ids"]
    )

    return api_response(
        success=True,
        message="User validation completed.",
        data=result,
        status_code=200,
    )
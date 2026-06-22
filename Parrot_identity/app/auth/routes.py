from flask import Blueprint, request
from flask_jwt_extended import get_jwt, jwt_required

from app.auth.schemas import LoginSchema, RegisterSchema
from app.auth.services import (
    login_user,
    logout_session,
    register_user,
    user_details,
)
from app.extensions import limiter
from app.shared.exceptions import ApiError
from app.shared.responses import api_response


auth_blueprint = Blueprint("auth", __name__)
register_schema = RegisterSchema()
login_schema = LoginSchema()


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
            "user": user_details(user),
        },
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

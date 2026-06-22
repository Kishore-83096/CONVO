from sqlalchemy import select

from app.auth.models import AuthSession
from app.auth.routes import auth_blueprint
from app.extensions import db, jwt
from app.shared.responses import api_response


def configure_jwt() -> None:
    @jwt.token_in_blocklist_loader
    def token_is_revoked(jwt_header, jwt_payload):
        statement = select(AuthSession.id).where(
            AuthSession.jti == jwt_payload["jti"]
        )
        return db.session.scalar(statement) is None

    @jwt.unauthorized_loader
    def missing_token(reason):
        return api_response(
            success=False,
            message="Authorization token is required.",
            status_code=401,
        )

    @jwt.invalid_token_loader
    def invalid_token(reason):
        return api_response(
            success=False,
            message="Invalid authorization token.",
            status_code=401,
        )

    @jwt.expired_token_loader
    def expired_token(jwt_header, jwt_payload):
        return api_response(
            success=False,
            message="Session expired. Log in again.",
            status_code=401,
        )

    @jwt.revoked_token_loader
    def revoked_token(jwt_header, jwt_payload):
        return api_response(
            success=False,
            message="Session is no longer active.",
            status_code=401,
        )


__all__ = ["auth_blueprint", "configure_jwt"]

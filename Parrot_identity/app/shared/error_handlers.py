from flask import Flask, current_app
from marshmallow import ValidationError
from werkzeug.exceptions import HTTPException

from app.extensions import db
from app.shared.exceptions import ApiError
from app.shared.responses import api_response


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ApiError)
    def handle_api_error(error: ApiError):
        return api_response(
            success=False,
            message=error.message,
            errors=error.errors,
            status_code=error.status_code,
        )

    @app.errorhandler(ValidationError)
    def handle_validation_error(error: ValidationError):
        return api_response(
            success=False,
            message="Validation failed.",
            errors=error.messages,
            status_code=400,
        )

    @app.errorhandler(HTTPException)
    def handle_http_error(error: HTTPException):
        return api_response(
            success=False,
            message=error.description,
            status_code=error.code or 500,
        )

    @app.errorhandler(Exception)
    def handle_unexpected_error(error: Exception):
        db.session.rollback()
        current_app.logger.exception(
            "Unhandled application error.",
            exc_info=error,
        )
        return api_response(
            success=False,
            message="An unexpected error occurred.",
            status_code=500,
        )

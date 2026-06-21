from flask import Blueprint

from app.health.services import (
    check_all_dependencies,
    check_cloudinary,
    check_database,
    check_service,
)
from app.shared.responses import api_response


health_blueprint = Blueprint("health", __name__)


def component_response(result: dict):
    is_up = result["status"] == "up"

    return api_response(
        success=is_up,
        message=result["message"],
        data=result,
        status_code=200 if is_up else 503,
    )


@health_blueprint.get("/", strict_slashes=False)
def service_health():
    return component_response(check_service())


@health_blueprint.get("/database")
def database_health():
    return component_response(check_database())


@health_blueprint.get("/cloudinary")
def cloudinary_health():
    return component_response(check_cloudinary())


@health_blueprint.get("/all")
def complete_health():
    result = check_all_dependencies()
    is_healthy = result["status"] == "healthy"

    return api_response(
        success=is_healthy,
        message=(
            "All service dependencies are available."
            if is_healthy
            else "One or more dependencies are unavailable."
        ),
        data=result,
        status_code=200 if is_healthy else 503,
    )
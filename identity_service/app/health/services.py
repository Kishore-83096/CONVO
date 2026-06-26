from time import perf_counter

import cloudinary.api
from flask import current_app
from sqlalchemy import text

from app.extensions import db


def latency_ms(start_time: float) -> float:
    return round((perf_counter() - start_time) * 1000, 2)


def check_service() -> dict:
    start_time = perf_counter()

    return {
        "component": "service",
        "status": "up",
        "message": "Identity Service service is running.",
        "latency_ms": latency_ms(start_time),
    }


def check_database() -> dict:
    start_time = perf_counter()

    try:
        result = db.session.execute(text("SELECT 1")).scalar_one()

        if result != 1:
            raise RuntimeError("Unexpected database response.")

        return {
            "component": "database",
            "status": "up",
            "message": "Database connection is available.",
            "latency_ms": latency_ms(start_time),
            "details": {
                "database_engine": db.engine.dialect.name,
            },
        }

    except Exception:
        db.session.rollback()
        current_app.logger.exception("Database health check failed.")

        return {
            "component": "database",
            "status": "down",
            "message": "Database connection is unavailable.",
            "latency_ms": latency_ms(start_time),
        }


def check_cloudinary() -> dict:
    start_time = perf_counter()

    try:
        result = cloudinary.api.ping()

        if str(result.get("status", "")).lower() != "ok":
            raise RuntimeError("Unexpected Cloudinary response.")

        return {
            "component": "cloudinary",
            "status": "up",
            "message": "Cloudinary API is reachable.",
            "latency_ms": latency_ms(start_time),
        }

    except Exception:
        current_app.logger.exception("Cloudinary health check failed.")

        return {
            "component": "cloudinary",
            "status": "down",
            "message": "Cloudinary API is unavailable.",
            "latency_ms": latency_ms(start_time),
        }


def check_all_dependencies() -> dict:
    checks = {
        "service": check_service(),
        "database": check_database(),
        "cloudinary": check_cloudinary(),
    }

    is_healthy = all(
        result["status"] == "up"
        for result in checks.values()
    )

    return {
        "service": "identity-service",
        "environment": current_app.config.get("APP_ENV", "unknown"),
        "status": "healthy" if is_healthy else "degraded",
        "checks": checks,
    }
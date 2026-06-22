from urllib.parse import unquote, urlparse

import cloudinary
from flask import Flask

from app.config import Config
from app.extensions import (
    cors,
    db,
    jwt,
    limiter,
    migrate,
)
from app.health import health_blueprint
from app.shared.error_handlers import register_error_handlers


def create_app(config_overrides: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)

    if config_overrides:
        app.config.update(config_overrides)

    validate_configuration(app)

    initialize_extensions(app)
    configure_cloudinary(app)
    register_blueprints(app)
    import_models()
    register_error_handlers(app)

    return app


def initialize_extensions(app: Flask) -> None:
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    limiter.init_app(app)

    cors.init_app(
        app,
        resources={
            r"/api/*": {
                "origins": [
                    app.config["FRONTEND_ORIGIN"]
                ],
            }
        },
    )


def configure_cloudinary(app: Flask) -> None:
    cloudinary_url = app.config.get("CLOUDINARY_URL")

    if not cloudinary_url:
        return

    parsed_url = urlparse(cloudinary_url)

    if (
        parsed_url.scheme != "cloudinary"
        or not parsed_url.hostname
        or not parsed_url.username
        or not parsed_url.password
    ):
        raise RuntimeError(
            "CLOUDINARY_URL must use the format "
            "cloudinary://API_KEY:API_SECRET@CLOUD_NAME"
        )

    cloudinary.config(
        cloud_name=parsed_url.hostname,
        api_key=unquote(parsed_url.username),
        api_secret=unquote(parsed_url.password),
        secure=True,
    )


def register_blueprints(app: Flask) -> None:
    from app.auth import auth_blueprint, configure_jwt

    configure_jwt()

    app.register_blueprint(
        health_blueprint,
        url_prefix="/api/v1/health",
    )

    app.register_blueprint(
        auth_blueprint,
        url_prefix="/api/v1/auth",
    )

    # Register these after their blueprints are created:
    # app.register_blueprint(
    #     profiles_blueprint,
    #     url_prefix="/api/v1/profiles",
    # )
    #
    # app.register_blueprint(
    #     contacts_blueprint,
    #     url_prefix="/api/v1/contacts",
    # )


def import_models() -> None:
    # These imports allow Flask-Migrate to discover models.
    from app.auth import models as auth_models  # noqa: F401
    from app.contacts import models as contact_models  # noqa: F401
    from app.profiles import models as profile_models  # noqa: F401


def validate_configuration(app: Flask) -> None:
    required_settings = {
        "DATABASE_URL": app.config.get(
            "SQLALCHEMY_DATABASE_URI"
        ),
        "SECRET_KEY": app.config.get("SECRET_KEY"),
        "JWT_SECRET_KEY": app.config.get(
            "JWT_SECRET_KEY"
        ),
    }

    missing_settings = [
        name
        for name, value in required_settings.items()
        if not value
    ]

    if missing_settings:
        raise RuntimeError(
            "Missing required environment variables: "
            + ", ".join(missing_settings)
        )

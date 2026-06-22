import pytest

from app import create_app
from app.extensions import db


@pytest.fixture()
def app():
    application = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SECRET_KEY": "test-secret-key",
            "JWT_SECRET_KEY": (
                "test-jwt-secret-key-at-least-thirty-two-bytes"
            ),
            "RATELIMIT_ENABLED": False,
            "CLOUDINARY_URL": None,
        }
    )

    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()

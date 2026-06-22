from datetime import datetime, timedelta, timezone

import pytest

from app.auth.models import User
from app.extensions import db


REGISTER_PAYLOAD = {
    "full_name": "Ada Lovelace",
    "username": "@ada_lovelace",
    "password": "correct-password",
    "confirm_password": "correct-password",
}


def register_user(client):
    return client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)


def test_registration_creates_account_with_generated_details(client):
    response = register_user(client)
    body = response.get_json()

    assert response.status_code == 201
    assert body["message"] == "Account created."
    assert body["data"]["full_name"] == "Ada Lovelace"
    assert body["data"]["username"] == "ada_lovelace"
    assert body["data"]["email"] == "ada_lovelace@parrot.com"
    assert isinstance(body["data"]["contact_number"], int)
    assert len(str(body["data"]["contact_number"])) == 10

    user = db.session.scalar(db.select(User))
    assert user.password_hash != REGISTER_PAYLOAD["password"]
    assert user.check_password(REGISTER_PAYLOAD["password"])


def test_registration_rejects_duplicate_username_case_insensitively(client):
    assert register_user(client).status_code == 201
    duplicate = dict(REGISTER_PAYLOAD, username="ADA_LOVELACE")

    response = client.post("/api/v1/auth/register", json=duplicate)

    assert response.status_code == 409
    assert response.get_json()["success"] is False


def test_registration_rejects_password_mismatch(client):
    payload = dict(REGISTER_PAYLOAD, confirm_password="wrong-password")

    response = client.post("/api/v1/auth/register", json=payload)

    assert response.status_code == 400
    assert "confirm_password" in response.get_json()["errors"]


@pytest.mark.parametrize("method", ["username", "email", "contact_number"])
def test_login_accepts_each_unique_identifier(client, method):
    registration = register_user(client).get_json()["data"]
    identifiers = {
        "username": "@ADA_LOVELACE",
        "email": registration["email"].upper(),
        "contact_number": registration["contact_number"],
    }

    response = client.post(
        "/api/v1/auth/login",
        json={
            "method": method,
            "identifier": identifiers[method],
            "password": REGISTER_PAYLOAD["password"],
        },
    )
    body = response.get_json()

    assert response.status_code == 200
    assert body["message"] == "User logged in."
    assert body["data"]["access_token"]
    expires_at = datetime.fromisoformat(body["data"]["expires_at"])
    expected_expiry = datetime.now(timezone.utc) + timedelta(days=1)
    assert abs(expires_at - expected_expiry) < timedelta(seconds=5)
    assert body["data"]["user"] == {
        "full_name": registration["full_name"],
        "email": registration["email"],
        "contact_number": registration["contact_number"],
    }


def test_login_returns_one_message_for_wrong_identifier_or_password(client):
    register_user(client)
    payload = {
        "method": "username",
        "identifier": "ada_lovelace",
        "password": "wrong-password",
    }

    response = client.post("/api/v1/auth/login", json=payload)

    assert response.status_code == 401
    assert response.get_json()["message"] == (
        "Invalid credentials. Try again."
    )


def test_logout_deletes_session_and_revokes_token(client):
    register_user(client)
    login = client.post(
        "/api/v1/auth/login",
        json={
            "method": "username",
            "identifier": "ada_lovelace",
            "password": REGISTER_PAYLOAD["password"],
        },
    )
    token = login.get_json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    logout = client.post("/api/v1/auth/logout", headers=headers)
    repeated_logout = client.post(
        "/api/v1/auth/logout",
        headers=headers,
    )

    assert logout.status_code == 200
    assert logout.get_json()["message"] == "User logged out."
    assert repeated_logout.status_code == 401
    assert repeated_logout.get_json()["message"] == (
        "Session is no longer active."
    )

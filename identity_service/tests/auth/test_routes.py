from datetime import date, datetime, timedelta, timezone

import pytest
from flask_jwt_extended import decode_token

from app.auth.models import AuthSession, User
from app.extensions import db
from app.profiles.models import (
    ProfileAddress,
    ProfileBasic,
    ProfileEvent,
    ProfilePicture,
)
from app.shared.exceptions import ApiError


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
    assert body["data"]["email"] == "ada_lovelace@Myna.com"
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
    decoded_token = decode_token(body["data"]["access_token"])
    assert decoded_token["iss"] == "myna-identity-service"
    assert decoded_token["sub"]
    assert decoded_token["type"] == "access"
    assert decoded_token["jti"]
    expires_at = datetime.fromisoformat(body["data"]["expires_at"])
    expected_expiry = datetime.now(timezone.utc) + timedelta(days=1)
    assert abs(expires_at - expected_expiry) < timedelta(seconds=5)
    assert body["data"]["user"] == {
        "username": registration["username"],
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


def test_logout_deletes_all_user_sessions_and_revokes_every_token(client):
    register_user(client)
    login_payload = {
        "method": "username",
        "identifier": "ada_lovelace",
        "password": REGISTER_PAYLOAD["password"],
    }
    first_login = client.post("/api/v1/auth/login", json=login_payload)
    second_login = client.post("/api/v1/auth/login", json=login_payload)
    first_headers = {
        "Authorization": (
            f"Bearer {first_login.get_json()['data']['access_token']}"
        )
    }
    second_headers = {
        "Authorization": (
            f"Bearer {second_login.get_json()['data']['access_token']}"
        )
    }
    assert len(db.session.scalars(db.select(AuthSession)).all()) == 2

    logout = client.post("/api/v1/auth/logout", headers=first_headers)
    first_repeated_logout = client.post(
        "/api/v1/auth/logout",
        headers=first_headers,
    )
    second_session_logout = client.post(
        "/api/v1/auth/logout",
        headers=second_headers,
    )

    assert logout.status_code == 200
    assert logout.get_json()["message"] == "User logged out."
    assert db.session.scalar(db.select(AuthSession)) is None
    assert first_repeated_logout.status_code == 401
    assert second_session_logout.status_code == 401
    assert second_session_logout.get_json()["message"] == (
        "Session is no longer active."
    )


def login_registered_user(client):
    registration = register_user(client).get_json()["data"]
    login = client.post(
        "/api/v1/auth/login",
        json={
            "method": "username",
            "identifier": registration["username"],
            "password": REGISTER_PAYLOAD["password"],
        },
    )
    token = login.get_json()["data"]["access_token"]
    return registration, {"Authorization": f"Bearer {token}"}


def reset_password_payload(registration, **overrides):
    payload = {
        "username": registration["username"],
        "email": registration["email"],
        "contact_number": registration["contact_number"],
        "current_password": REGISTER_PAYLOAD["password"],
        "new_password": "new-secure-password",
        "confirm_new_password": "new-secure-password",
    }
    payload.update(overrides)
    return payload


def test_reset_password_changes_password_and_revokes_all_sessions(client):
    registration, first_headers = login_registered_user(client)
    second_login = client.post(
        "/api/v1/auth/login",
        json={
            "method": "username",
            "identifier": registration["username"],
            "password": REGISTER_PAYLOAD["password"],
        },
    )
    second_headers = {
        "Authorization": (
            f"Bearer {second_login.get_json()['data']['access_token']}"
        )
    }

    response = client.post(
        "/api/v1/auth/reset-password",
        headers=first_headers,
        json=reset_password_payload(
            registration,
            username="@ADA_LOVELACE",
            email=registration["email"].upper(),
            contact_number=str(registration["contact_number"]),
        ),
    )

    assert response.status_code == 200
    assert response.get_json()["message"] == (
        "Password has been changed successfully. Log in again."
    )
    assert client.post(
        "/api/v1/auth/logout",
        headers=first_headers,
    ).status_code == 401
    assert client.post(
        "/api/v1/auth/logout",
        headers=second_headers,
    ).status_code == 401

    old_password_login = client.post(
        "/api/v1/auth/login",
        json={
            "method": "username",
            "identifier": registration["username"],
            "password": REGISTER_PAYLOAD["password"],
        },
    )
    new_password_login = client.post(
        "/api/v1/auth/login",
        json={
            "method": "username",
            "identifier": registration["username"],
            "password": "new-secure-password",
        },
    )

    assert old_password_login.status_code == 401
    assert new_password_login.status_code == 200


@pytest.mark.parametrize(
    "overrides",
    [
        {"username": "wrong_username"},
        {"email": "wrong_email@Myna.com"},
        {"contact_number": 1_234_567_890},
        {"current_password": "wrong-password"},
        {"confirm_new_password": "different-password"},
    ],
)
def test_reset_password_rejects_invalid_account_data(client, overrides):
    registration, headers = login_registered_user(client)

    response = client.post(
        "/api/v1/auth/reset-password",
        headers=headers,
        json=reset_password_payload(registration, **overrides),
    )

    assert response.status_code == 400
    assert response.get_json()["message"] == (
        "Password could not be changed because the provided data "
        "is invalid."
    )
    assert client.post(
        "/api/v1/auth/logout",
        headers=headers,
    ).status_code == 200


def test_reset_password_requires_an_active_session(client):
    registration = register_user(client).get_json()["data"]

    response = client.post(
        "/api/v1/auth/reset-password",
        json=reset_password_payload(registration),
    )

    assert response.status_code == 401
    assert response.get_json()["message"] == (
        "Authorization token is required."
    )


def delete_account_payload(registration, **overrides):
    payload = {
        "username": registration["username"],
        "email": registration["email"],
        "contact_number": registration["contact_number"],
        "current_password": REGISTER_PAYLOAD["password"],
    }
    payload.update(overrides)
    return payload


def test_delete_account_removes_cloudinary_asset_and_all_records(
    client,
    monkeypatch,
):
    registration, headers = login_registered_user(client)
    user = db.session.scalar(
        db.select(User).where(User.username == registration["username"])
    )
    public_id = f"Myna-profile-pictures/{user.username}"
    db.session.add_all(
        [
            ProfileBasic(user_id=user.id, bio="Test bio"),
            ProfileAddress(
                user_id=user.id,
                address_line_1="1 Test Street",
                city="London",
                country="United Kingdom",
            ),
            ProfileEvent(
                user_id=user.id,
                event_name="Test event",
                event_date=date(2030, 1, 1),
            ),
            ProfilePicture(user_id=user.id, public_id=public_id),
        ]
    )
    db.session.commit()
    deleted_assets = []
    monkeypatch.setattr(
        "app.auth.services.destroy_cloudinary_asset",
        deleted_assets.append,
    )

    response = client.delete(
        "/api/v1/auth/delete-account",
        headers=headers,
        json=delete_account_payload(registration),
    )

    assert response.status_code == 200
    assert response.get_json()["message"] == (
        "Account and all associated data deleted permanently."
    )
    assert deleted_assets == [public_id]
    for model in (
        AuthSession,
        ProfileBasic,
        ProfileAddress,
        ProfileEvent,
        ProfilePicture,
        User,
    ):
        assert db.session.scalar(db.select(model)) is None
    assert client.post(
        "/api/v1/auth/logout",
        headers=headers,
    ).status_code == 401


@pytest.mark.parametrize(
    "overrides",
    [
        {"username": "wrong_username"},
        {"email": "wrong_email@Myna.com"},
        {"contact_number": 999},
        {"current_password": "wrong-password"},
    ],
)
def test_delete_account_rejects_invalid_account_data(client, overrides):
    registration, headers = login_registered_user(client)

    response = client.delete(
        "/api/v1/auth/delete-account",
        headers=headers,
        json=delete_account_payload(registration, **overrides),
    )

    assert response.status_code == 400
    assert response.get_json()["message"] == (
        "Account could not be deleted because the provided data "
        "is invalid."
    )
    assert db.session.scalar(db.select(User)) is not None
    assert client.post(
        "/api/v1/auth/logout",
        headers=headers,
    ).status_code == 200


def test_delete_account_keeps_database_data_when_cloudinary_fails(
    client,
    monkeypatch,
):
    registration, headers = login_registered_user(client)
    user = db.session.scalar(db.select(User))
    db.session.add(
        ProfilePicture(user_id=user.id, public_id="profiles/test-user")
    )
    db.session.commit()

    def fail_cloudinary_deletion(public_id):
        raise ApiError("Profile image deletion failed.", status_code=502)

    monkeypatch.setattr(
        "app.auth.services.destroy_cloudinary_asset",
        fail_cloudinary_deletion,
    )

    response = client.delete(
        "/api/v1/auth/delete-account",
        headers=headers,
        json=delete_account_payload(registration),
    )

    assert response.status_code == 502
    assert db.session.scalar(db.select(User)) is not None
    assert db.session.scalar(db.select(ProfilePicture)) is not None


def test_delete_account_requires_an_active_session(client):
    registration = register_user(client).get_json()["data"]

    response = client.delete(
        "/api/v1/auth/delete-account",
        json=delete_account_payload(registration),
    )

    assert response.status_code == 401
    assert response.get_json()["message"] == (
        "Authorization token is required."
    )

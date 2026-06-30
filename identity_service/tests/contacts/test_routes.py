import pytest

from app.auth.models import User
from app.contacts.models import Contact
from app.extensions import db
from app.profiles.models import ProfilePicture


OWNER_PAYLOAD = {
    "full_name": "Grace Hopper",
    "username": "grace_hopper",
    "password": "owner-password",
    "confirm_password": "owner-password",
}
TARGET_PAYLOAD = {
    "full_name": "Alan Turing",
    "username": "alan_turing",
    "password": "target-password",
    "confirm_password": "target-password",
}


def register(client, payload):
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    return response.get_json()["data"]


def login_headers(client, username, password):
    response = client.post(
        "/api/v1/auth/login",
        json={
            "method": "username",
            "identifier": username,
            "password": password,
        },
    )
    assert response.status_code == 200
    token = response.get_json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def contact_users(client, app):
    owner = register(client, OWNER_PAYLOAD)
    target = register(client, TARGET_PAYLOAD)
    owner_headers = login_headers(
        client,
        owner["username"],
        OWNER_PAYLOAD["password"],
    )
    target_headers = login_headers(
        client,
        target["username"],
        TARGET_PAYLOAD["password"],
    )

    target_user = db.session.scalar(
        db.select(User).where(User.username == target["username"])
    )
    db.session.add(
        ProfilePicture(
            user_id=target_user.id,
            public_id="Mynav2/local/profiles/alan_turing",
            version=7,
            image_format="png",
            width=256,
            height=256,
            file_size=4096,
        )
    )
    db.session.commit()
    app.config["CLOUDINARY_URL"] = "cloudinary://configured"

    return {
        "owner": owner,
        "target": target,
        "owner_headers": owner_headers,
        "target_headers": target_headers,
    }


def test_contact_routes_require_an_active_session(client):
    response = client.get("/api/v1/contacts")

    assert response.status_code == 401
    assert response.get_json()["message"] == (
        "Authorization token is required."
    )


def test_search_contact_returns_limited_identity_and_profile_picture(
    client,
    contact_users,
):
    response = client.post(
        "/api/v1/contacts/search",
        headers=contact_users["owner_headers"],
        json={
            "contact_number": str(
                contact_users["target"]["contact_number"]
            )
        },
    )
    body = response.get_json()

    assert response.status_code == 200
    assert body["message"] == "Contact found."
    assert set(body["data"]) == {
        "full_name",
        "username",
        "profile_picture",
    }
    assert body["data"]["full_name"] == TARGET_PAYLOAD["full_name"]
    assert body["data"]["username"] == TARGET_PAYLOAD["username"]
    assert body["data"]["profile_picture"]["url"] == (
        "https://res.cloudinary.com/configured/image/upload/"
        "v7/Mynav2/local/profiles/alan_turing.png"
    )


def test_search_identifies_the_logged_in_users_own_contact(
    client,
    contact_users,
):
    response = client.post(
        "/api/v1/contacts/search",
        headers=contact_users["owner_headers"],
        json={
            "contact_number": contact_users["owner"]["contact_number"]
        },
    )

    assert response.status_code == 200
    assert response.get_json()["message"] == "This is your own contact."
    assert response.get_json()["data"]["username"] == (
        OWNER_PAYLOAD["username"]
    )


def test_search_rejects_invalid_or_unknown_contact_numbers(
    client,
    contact_users,
):
    invalid = client.post(
        "/api/v1/contacts/search",
        headers=contact_users["owner_headers"],
        json={"contact_number": "123"},
    )
    used_numbers = {
        contact_users["owner"]["contact_number"],
        contact_users["target"]["contact_number"],
    }
    unknown_number = next(
        number for number in range(1_000_000_000, 1_000_000_010)
        if number not in used_numbers
    )
    unknown = client.post(
        "/api/v1/contacts/search",
        headers=contact_users["owner_headers"],
        json={"contact_number": unknown_number},
    )

    assert invalid.status_code == 400
    assert unknown.status_code == 404


def add_target_contact(client, contact_users, saved_name="Alan"):
    return client.post(
        "/api/v1/contacts",
        headers=contact_users["owner_headers"],
        json={
            "contact_number": contact_users["target"]["contact_number"],
            "saved_name": saved_name,
        },
    )


def test_contact_add_list_detail_rename_and_delete_workflow(
    client,
    contact_users,
):
    added = add_target_contact(client, contact_users, "Professor Turing")
    added_data = added.get_json()["data"]
    contact_id = added_data["id"]

    assert added.status_code == 201
    assert set(added_data) == {
        "id",
        "saved_name",
        "contact_number",
        "username",
        "full_name",
        "profile_picture",
    }

    contact_list = client.get(
        "/api/v1/contacts",
        headers=contact_users["owner_headers"],
    )
    summaries = contact_list.get_json()["data"]

    assert contact_list.status_code == 200
    assert len(summaries) == 1
    assert set(summaries[0]) == {"id", "saved_name", "profile_picture"}
    assert summaries[0]["saved_name"] == "Professor Turing"

    detail = client.get(
        f"/api/v1/contacts/{contact_id}",
        headers=contact_users["owner_headers"],
    )
    detail_data = detail.get_json()["data"]
    assert detail.status_code == 200
    default_policy = detail_data["delivery_policy"]

    assert default_policy["owner_user_id"] > 0
    assert default_policy["target_user_id"] > 0
    assert default_policy["is_blocked"] is False
    assert default_policy["blocked_at"] is None
    assert default_policy["is_ghosted"] is False
    assert default_policy["ghost_until"] is None
    assert default_policy["ghost_permanent"] is False
    assert default_policy["ghost_duration_option"] is None
    assert default_policy["policy_version"] == 0
    assert default_policy["updated_at"] is None
    detail_data_without_policy = dict(detail_data)
    detail_data_without_policy.pop("delivery_policy")
    assert detail_data_without_policy == added_data

    renamed = client.patch(
        f"/api/v1/contacts/{contact_id}",
        headers=contact_users["owner_headers"],
        json={
            "saved_name": "  Alan  ",
            "contact_number": contact_users["owner"]["contact_number"],
            "username": "cannot_be_changed",
        },
    )
    renamed_data = renamed.get_json()["data"]

    assert renamed.status_code == 200
    assert renamed_data["saved_name"] == "Alan"
    assert renamed_data["contact_number"] == (
        contact_users["target"]["contact_number"]
    )
    assert renamed_data["username"] == TARGET_PAYLOAD["username"]

    deleted = client.delete(
        f"/api/v1/contacts/{contact_id}",
        headers=contact_users["owner_headers"],
    )
    missing = client.get(
        f"/api/v1/contacts/{contact_id}",
        headers=contact_users["owner_headers"],
    )

    assert deleted.status_code == 200
    assert missing.status_code == 404


def test_add_contact_rejects_own_and_duplicate_contacts(
    client,
    contact_users,
):
    own_contact = client.post(
        "/api/v1/contacts",
        headers=contact_users["owner_headers"],
        json={
            "contact_number": contact_users["owner"]["contact_number"],
            "saved_name": "Me",
        },
    )
    first = add_target_contact(client, contact_users)
    duplicate = add_target_contact(client, contact_users, "Another name")

    assert own_contact.status_code == 400
    assert own_contact.get_json()["message"] == (
        "You cannot add your own contact."
    )
    assert first.status_code == 201
    assert duplicate.status_code == 409


def test_contacts_are_private_to_the_owner(client, contact_users):
    added = add_target_contact(client, contact_users)
    contact_id = added.get_json()["data"]["id"]
    target_headers = contact_users["target_headers"]

    responses = [
        client.get(
            f"/api/v1/contacts/{contact_id}",
            headers=target_headers,
        ),
        client.patch(
            f"/api/v1/contacts/{contact_id}",
            headers=target_headers,
            json={"saved_name": "Not allowed"},
        ),
        client.delete(
            f"/api/v1/contacts/{contact_id}",
            headers=target_headers,
        ),
    ]

    assert all(response.status_code == 404 for response in responses)
    assert db.session.get(Contact, contact_id) is not None


def test_account_deletion_removes_owned_and_referenced_contacts(
    client,
    contact_users,
):
    assert add_target_contact(client, contact_users).status_code == 201
    reverse_contact = client.post(
        "/api/v1/contacts",
        headers=contact_users["target_headers"],
        json={
            "contact_number": contact_users["owner"]["contact_number"],
            "saved_name": "Grace",
        },
    )
    assert reverse_contact.status_code == 201

    deleted = client.delete(
        "/api/v1/auth/delete-account",
        headers=contact_users["owner_headers"],
        json={
            "username": contact_users["owner"]["username"],
            "email": contact_users["owner"]["email"],
            "contact_number": contact_users["owner"]["contact_number"],
            "current_password": OWNER_PAYLOAD["password"],
        },
    )

    assert deleted.status_code == 200
    assert db.session.scalar(db.select(Contact)) is None
    assert db.session.scalar(
        db.select(User).where(User.username == TARGET_PAYLOAD["username"])
    ) is not None

def test_contact_ghost_default_duration_and_unghost(
    client,
    contact_users,
):
    added = add_target_contact(client, contact_users)
    contact_id = added.get_json()["data"]["id"]

    ghosted = client.patch(
        f"/api/v1/contacts/{contact_id}/ghost",
        headers=contact_users["owner_headers"],
        json={
            "is_ghosted": True,
        },
    )

    assert ghosted.status_code == 200
    ghost_data = ghosted.get_json()["data"]
    ghost_policy = ghost_data["delivery_policy"]

    assert ghosted.get_json()["message"] == "Contact ghosted."
    assert ghost_policy["is_ghosted"] is True
    assert ghost_policy["ghost_until"] is not None
    assert ghost_policy["ghost_permanent"] is False
    assert ghost_policy["ghost_duration_option"] == "24h"
    assert ghost_policy["policy_version"] >= 2

    unghosted = client.patch(
        f"/api/v1/contacts/{contact_id}/ghost",
        headers=contact_users["owner_headers"],
        json={
            "is_ghosted": False,
        },
    )

    assert unghosted.status_code == 200
    unghost_policy = unghosted.get_json()["data"]["delivery_policy"]

    assert unghosted.get_json()["message"] == "Contact unghosted."
    assert unghost_policy["is_ghosted"] is False
    assert unghost_policy["ghost_until"] is None
    assert unghost_policy["ghost_permanent"] is False
    assert unghost_policy["ghost_duration_option"] is None


def test_contact_detail_returns_current_delivery_policy_after_block(
    client,
    contact_users,
):
    added = add_target_contact(client, contact_users)
    contact_id = added.get_json()["data"]["id"]

    blocked = client.patch(
        f"/api/v1/contacts/{contact_id}/block",
        headers=contact_users["owner_headers"],
        json={
            "is_blocked": True,
        },
    )
    detail = client.get(
        f"/api/v1/contacts/{contact_id}",
        headers=contact_users["owner_headers"],
    )

    assert blocked.status_code == 200
    assert detail.status_code == 200

    policy = detail.get_json()["data"]["delivery_policy"]

    assert policy["is_blocked"] is True
    assert policy["blocked_at"] is not None
    assert policy["is_ghosted"] is False
    assert policy["policy_version"] >= 2

from io import BytesIO

import pytest
from cloudinary.exceptions import Error as CloudinaryError

from app.extensions import db
from app.profiles.models import ProfilePicture
from app.profiles import services as profile_services


REGISTER_PAYLOAD = {
    "full_name": "Grace Hopper",
    "username": "@grace_hopper",
    "password": "correct-password",
    "confirm_password": "correct-password",
}


@pytest.fixture()
def authenticated(client):
    registration = client.post(
        "/api/v1/auth/register",
        json=REGISTER_PAYLOAD,
    )
    assert registration.status_code == 201
    login = client.post(
        "/api/v1/auth/login",
        json={
            "method": "username",
            "identifier": "grace_hopper",
            "password": REGISTER_PAYLOAD["password"],
        },
    )
    assert login.status_code == 200
    token = login.get_json()["data"]["access_token"]
    return {
        "headers": {"Authorization": f"Bearer {token}"},
        "registration": registration.get_json()["data"],
    }


def image_data(
    filename="profile.png",
    content=b"fake-image-data",
    mimetype="image/png",
):
    return {"image": (BytesIO(content), filename, mimetype)}


def test_profile_routes_require_an_active_jwt(client):
    response = client.get("/api/v1/profiles/me")

    assert response.status_code == 401
    assert response.get_json()["message"] == (
        "Authorization token is required."
    )


def test_empty_aggregate_profile_contains_immutable_identity(
    client,
    authenticated,
):
    response = client.get(
        "/api/v1/profiles/me",
        headers=authenticated["headers"],
    )
    data = response.get_json()["data"]

    assert response.status_code == 200
    assert data["identity"] == {
        "full_name": "Grace Hopper",
        "username": "grace_hopper",
        "email": "grace_hopper@parrot.com",
        "contact_number": authenticated["registration"][
            "contact_number"
        ],
    }
    assert data["profile_picture"] is None
    assert data["basic_data"] is None
    assert data["address"] is None
    assert data["events"] == []


def test_basic_profile_crud_and_immutable_identity(
    client,
    authenticated,
):
    path = "/api/v1/profiles/me/basic"
    headers = authenticated["headers"]
    created = client.post(
        path,
        headers=headers,
        json={
            "bio": "Compiler pioneer",
            "date_of_birth": "1906-12-09",
            "gender": "Female",
            "occupation": "Computer scientist",
            "website": "https://example.com/grace",
        },
    )
    fetched = client.get(path, headers=headers)
    updated = client.patch(
        path,
        headers=headers,
        json={"bio": "US Navy rear admiral and computing pioneer"},
    )
    immutable_update = client.patch(
        path,
        headers=headers,
        json={"full_name": "Changed Name"},
    )
    aggregate = client.get(
        "/api/v1/profiles/me",
        headers=headers,
    )
    deleted = client.delete(path, headers=headers)
    missing = client.get(path, headers=headers)

    assert created.status_code == 201
    assert fetched.status_code == 200
    assert updated.status_code == 200
    assert updated.get_json()["data"]["bio"].startswith("US Navy")
    assert immutable_update.status_code == 400
    assert aggregate.get_json()["data"]["identity"]["full_name"] == (
        "Grace Hopper"
    )
    assert deleted.status_code == 200
    assert missing.status_code == 404


def test_address_crud(client, authenticated):
    path = "/api/v1/profiles/me/address"
    headers = authenticated["headers"]
    created = client.post(
        path,
        headers=headers,
        json={
            "address_line_1": "123 Navy Street",
            "address_line_2": "Apartment 4",
            "city": "Arlington",
            "state": "Virginia",
            "postal_code": "22201",
            "country": "United States",
        },
    )
    updated = client.patch(
        path,
        headers=headers,
        json={"city": "New York", "state": "New York"},
    )
    fetched = client.get(path, headers=headers)
    deleted = client.delete(path, headers=headers)

    assert created.status_code == 201
    assert updated.status_code == 200
    assert fetched.get_json()["data"]["city"] == "New York"
    assert deleted.status_code == 200


def test_event_crud_enforces_five_event_limit(client, authenticated):
    collection_path = "/api/v1/profiles/me/events"
    headers = authenticated["headers"]
    created_events = []

    for index in range(5):
        response = client.post(
            collection_path,
            headers=headers,
            json={
                "event_name": f"Custom event {index + 1}",
                "event_date": f"2026-01-{index + 1:02d}",
                "description": "User-defined event",
                "recurring": True,
            },
        )
        assert response.status_code == 201
        created_events.append(response.get_json()["data"])

    rejected = client.post(
        collection_path,
        headers=headers,
        json={
            "event_name": "Sixth event",
            "event_date": "2026-02-01",
        },
    )
    event_id = created_events[0]["id"]
    updated = client.patch(
        f"{collection_path}/{event_id}",
        headers=headers,
        json={"event_name": "Wedding anniversary"},
    )
    fetched = client.get(
        f"{collection_path}/{event_id}",
        headers=headers,
    )
    listed = client.get(collection_path, headers=headers)
    deleted = client.delete(
        f"{collection_path}/{event_id}",
        headers=headers,
    )
    replacement = client.post(
        collection_path,
        headers=headers,
        json={
            "event_name": "Replacement event",
            "event_date": "2026-02-02",
        },
    )

    assert rejected.status_code == 409
    assert updated.get_json()["data"]["event_name"] == (
        "Wedding anniversary"
    )
    assert fetched.status_code == 200
    assert len(listed.get_json()["data"]) == 5
    assert deleted.status_code == 200
    assert replacement.status_code == 201


def test_picture_crud_updates_cloudinary_directly(
    app,
    client,
    authenticated,
    monkeypatch,
):
    app.config["CLOUDINARY_URL"] = "cloudinary://configured"
    path = "/api/v1/profiles/me/picture"
    headers = authenticated["headers"]
    upload_calls = []
    destroy_calls = []

    def fake_upload(stream, **options):
        upload_calls.append(options)
        version = len(upload_calls)
        image_format = "png" if version == 1 else "jpg"
        return {
            "public_id": (
                f"{options['asset_folder']}/{options['public_id']}"
            ),
            "version": version,
            "format": image_format,
            "width": 256,
            "height": 256,
            "bytes": 1024,
        }

    def fake_destroy(public_id, **options):
        destroy_calls.append((public_id, options))
        return {"result": "ok"}

    monkeypatch.setattr(
        profile_services.cloudinary.uploader,
        "upload",
        fake_upload,
    )
    monkeypatch.setattr(
        profile_services.cloudinary.uploader,
        "destroy",
        fake_destroy,
    )

    created = client.post(
        path,
        headers=headers,
        data=image_data(),
        content_type="multipart/form-data",
    )
    updated = client.patch(
        path,
        headers=headers,
        data=image_data(
            "replacement.jpg",
            b"new-image",
            "image/jpeg",
        ),
        content_type="multipart/form-data",
    )
    fetched = client.get(path, headers=headers)
    deleted = client.delete(path, headers=headers)
    missing = client.get(path, headers=headers)

    assert created.status_code == 201
    assert updated.status_code == 200
    assert updated.get_json()["data"]["url"].endswith(
        "parrotv2/local/profiles/grace_hopper.jpg"
    )
    assert fetched.status_code == 200
    assert len(upload_calls) == 2
    assert upload_calls[0]["public_id"] == "grace_hopper"
    assert upload_calls[0]["asset_folder"] == (
        "parrotv2/local/profiles"
    )
    assert upload_calls[0][
        "use_asset_folder_as_public_id_prefix"
    ] is True
    assert upload_calls[0]["filename_override"] == "grace_hopper.png"
    assert upload_calls[1]["filename_override"] == "grace_hopper.jpg"
    assert upload_calls[0]["public_id"] == upload_calls[1]["public_id"]
    assert upload_calls[1]["overwrite"] is True
    assert len(destroy_calls) == 1
    assert destroy_calls[0][0] == (
        "parrotv2/local/profiles/grace_hopper"
    )
    assert destroy_calls[0][1]["invalidate"] is True
    assert deleted.status_code == 200
    assert missing.status_code == 404


def test_failed_cloudinary_delete_preserves_picture_record(
    app,
    client,
    authenticated,
    monkeypatch,
):
    app.config["CLOUDINARY_URL"] = "cloudinary://configured"
    path = "/api/v1/profiles/me/picture"
    headers = authenticated["headers"]

    monkeypatch.setattr(
        profile_services.cloudinary.uploader,
        "upload",
        lambda stream, **options: {
            "public_id": (
                f"{options['asset_folder']}/{options['public_id']}"
            ),
        },
    )

    def failed_destroy(public_id, **options):
        raise CloudinaryError("Cloudinary unavailable")

    monkeypatch.setattr(
        profile_services.cloudinary.uploader,
        "destroy",
        failed_destroy,
    )

    created = client.post(
        path,
        headers=headers,
        data=image_data(),
        content_type="multipart/form-data",
    )
    deleted = client.delete(path, headers=headers)
    retained = client.get(path, headers=headers)

    assert created.status_code == 201
    assert deleted.status_code == 502
    assert retained.status_code == 200


def test_picture_update_moves_legacy_asset_to_username_path(
    app,
    client,
    authenticated,
    monkeypatch,
):
    app.config["CLOUDINARY_URL"] = "cloudinary://configured"
    headers = authenticated["headers"]
    uploaded_public_ids = []
    deleted_public_ids = []

    def fake_upload(stream, **options):
        public_id = f"{options['asset_folder']}/{options['public_id']}"
        uploaded_public_ids.append(public_id)
        return {
            "public_id": public_id,
        }

    def fake_destroy(public_id, **options):
        deleted_public_ids.append(public_id)
        return {"result": "ok"}

    monkeypatch.setattr(
        profile_services.cloudinary.uploader,
        "upload",
        fake_upload,
    )
    monkeypatch.setattr(
        profile_services.cloudinary.uploader,
        "destroy",
        fake_destroy,
    )
    path = "/api/v1/profiles/me/picture"
    assert client.post(
        path,
        headers=headers,
        data=image_data(),
        content_type="multipart/form-data",
    ).status_code == 201

    picture = db.session.scalar(db.select(ProfilePicture))
    legacy_public_id = "parrotv2/local/profiles/user_1/profile"
    picture.public_id = legacy_public_id
    db.session.commit()

    response = client.patch(
        path,
        headers=headers,
        data=image_data("replacement.jpg", mimetype="image/jpeg"),
        content_type="multipart/form-data",
    )

    expected_public_id = "parrotv2/local/profiles/grace_hopper"
    assert response.status_code == 200
    assert uploaded_public_ids[-1] == expected_public_id
    assert deleted_public_ids == [legacy_public_id]
    assert picture.public_id == expected_public_id


def test_aggregate_profile_returns_all_profile_resources(
    app,
    client,
    authenticated,
    monkeypatch,
):
    app.config["CLOUDINARY_URL"] = "cloudinary://configured"
    headers = authenticated["headers"]
    monkeypatch.setattr(
        profile_services.cloudinary.uploader,
        "upload",
        lambda stream, **options: {
            "public_id": (
                f"{options['asset_folder']}/{options['public_id']}"
            ),
            "format": "png",
        },
    )

    assert client.post(
        "/api/v1/profiles/me/basic",
        headers=headers,
        json={"bio": "Profile biography"},
    ).status_code == 201
    assert client.post(
        "/api/v1/profiles/me/address",
        headers=headers,
        json={
            "address_line_1": "123 Main Street",
            "city": "New York",
            "country": "United States",
        },
    ).status_code == 201
    assert client.post(
        "/api/v1/profiles/me/events",
        headers=headers,
        json={
            "event_name": "Birthday",
            "event_date": "1906-12-09",
        },
    ).status_code == 201
    assert client.post(
        "/api/v1/profiles/me/picture",
        headers=headers,
        data=image_data(),
        content_type="multipart/form-data",
    ).status_code == 201

    response = client.get(
        "/api/v1/profiles/me",
        headers=headers,
    )
    data = response.get_json()["data"]

    assert response.status_code == 200
    assert data["identity"]["username"] == "grace_hopper"
    assert data["basic_data"]["bio"] == "Profile biography"
    assert data["address"]["city"] == "New York"
    assert data["events"][0]["event_name"] == "Birthday"
    assert data["profile_picture"]["url"] == (
        "https://res.cloudinary.com/configured/image/upload/"
        "v1/parrotv2/local/profiles/grace_hopper.png"
    )

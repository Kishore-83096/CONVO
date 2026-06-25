from typing import Any
from urllib.parse import urlparse

import cloudinary.uploader
from cloudinary.exceptions import Error as CloudinaryError
from cloudinary.utils import cloudinary_url
from flask import current_app
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.datastructures import FileStorage

from app.auth.models import User
from app.extensions import db
from app.profiles.models import (
    ProfileAddress,
    ProfileBasic,
    ProfileEvent,
    ProfilePicture,
)
from app.shared.exceptions import ApiError


MAX_EVENTS_PER_USER = 5
ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
}


def get_user(user_id: int, *, for_update: bool = False) -> User:
    statement = select(User).where(
        User.id == user_id,
        User.is_active.is_(True),
    )

    if for_update:
        statement = statement.with_for_update()

    user = db.session.scalar(statement)
    if user is None:
        raise ApiError("User account was not found.", status_code=404)
    return user


def get_owned_record(model, user_id: int, message: str):
    record = db.session.scalar(
        select(model).where(model.user_id == user_id)
    )
    if record is None:
        raise ApiError(message, status_code=404)
    return record


def apply_fields(record, payload: dict) -> None:
    for field, value in payload.items():
        setattr(record, field, value)


def timestamp(value) -> str | None:
    return value.isoformat() if value else None


def serialize_basic(record: ProfileBasic | None) -> dict | None:
    if record is None:
        return None
    return {
        "bio": record.bio,
        "date_of_birth": timestamp(record.date_of_birth),
        "gender": record.gender,
        "occupation": record.occupation,
        "website": record.website,
        "created_at": timestamp(record.created_at),
        "updated_at": timestamp(record.updated_at),
    }


def serialize_address(record: ProfileAddress | None) -> dict | None:
    if record is None:
        return None
    return {
        "address_line_1": record.address_line_1,
        "address_line_2": record.address_line_2,
        "city": record.city,
        "state": record.state,
        "postal_code": record.postal_code,
        "country": record.country,
        "created_at": timestamp(record.created_at),
        "updated_at": timestamp(record.updated_at),
    }


def serialize_picture(record: ProfilePicture | None) -> dict | None:
    if record is None:
        return None
    return {
        "url": profile_picture_url(record),
        "format": record.image_format,
        "width": record.width,
        "height": record.height,
        "bytes": record.file_size,
        "created_at": timestamp(record.created_at),
        "updated_at": timestamp(record.updated_at),
    }


def serialize_event(record: ProfileEvent) -> dict:
    return {
        "id": record.id,
        "event_name": record.event_name,
        "event_date": timestamp(record.event_date),
        "description": record.description,
        "recurring": record.recurring,
        "created_at": timestamp(record.created_at),
        "updated_at": timestamp(record.updated_at),
    }


def get_complete_profile(user_id: int) -> dict:
    user = get_user(user_id)
    events = db.session.scalars(
        select(ProfileEvent)
        .where(ProfileEvent.user_id == user_id)
        .order_by(ProfileEvent.event_date, ProfileEvent.id)
    ).all()
    return {
        "identity": {
            "full_name": user.full_name,
            "username": user.username,
            "email": user.email,
            "contact_number": user.contact_number,
        },
        "profile_picture": serialize_picture(user.profile_picture),
        "basic_data": serialize_basic(user.profile_basic),
        "address": serialize_address(user.profile_address),
        "events": [serialize_event(event) for event in events],
    }


def create_basic(user_id: int, payload: dict) -> ProfileBasic:
    get_user(user_id)
    if db.session.scalar(
        select(ProfileBasic.id).where(ProfileBasic.user_id == user_id)
    ):
        raise ApiError(
            "Basic profile data already exists.",
            status_code=409,
        )
    record = ProfileBasic(user_id=user_id, **payload)
    db.session.add(record)
    db.session.commit()
    return record


def update_basic(user_id: int, payload: dict) -> ProfileBasic:
    record = get_owned_record(
        ProfileBasic,
        user_id,
        "Basic profile data was not found.",
    )
    apply_fields(record, payload)
    db.session.commit()
    return record


def delete_basic(user_id: int) -> None:
    record = get_owned_record(
        ProfileBasic,
        user_id,
        "Basic profile data was not found.",
    )
    db.session.delete(record)
    db.session.commit()


def create_address(user_id: int, payload: dict) -> ProfileAddress:
    get_user(user_id)
    if db.session.scalar(
        select(ProfileAddress.id).where(
            ProfileAddress.user_id == user_id
        )
    ):
        raise ApiError("Address already exists.", status_code=409)
    record = ProfileAddress(user_id=user_id, **payload)
    db.session.add(record)
    db.session.commit()
    return record


def update_address(user_id: int, payload: dict) -> ProfileAddress:
    record = get_owned_record(
        ProfileAddress,
        user_id,
        "Address was not found.",
    )
    apply_fields(record, payload)
    db.session.commit()
    return record


def delete_address(user_id: int) -> None:
    record = get_owned_record(
        ProfileAddress,
        user_id,
        "Address was not found.",
    )
    db.session.delete(record)
    db.session.commit()


def get_events(user_id: int) -> list[ProfileEvent]:
    get_user(user_id)
    return list(
        db.session.scalars(
            select(ProfileEvent)
            .where(ProfileEvent.user_id == user_id)
            .order_by(ProfileEvent.event_date, ProfileEvent.id)
        ).all()
    )


def get_event(user_id: int, event_id: int) -> ProfileEvent:
    record = db.session.scalar(
        select(ProfileEvent).where(
            ProfileEvent.id == event_id,
            ProfileEvent.user_id == user_id,
        )
    )
    if record is None:
        raise ApiError("Event was not found.", status_code=404)
    return record


def create_event(user_id: int, payload: dict) -> ProfileEvent:
    get_user(user_id, for_update=True)
    event_count = db.session.scalar(
        select(func.count(ProfileEvent.id)).where(
            ProfileEvent.user_id == user_id
        )
    )
    if event_count >= MAX_EVENTS_PER_USER:
        raise ApiError(
            "A profile can contain at most 5 events.",
            status_code=409,
        )
    record = ProfileEvent(user_id=user_id, **payload)
    db.session.add(record)
    db.session.commit()
    return record


def update_event(
    user_id: int,
    event_id: int,
    payload: dict,
) -> ProfileEvent:
    record = get_event(user_id, event_id)
    apply_fields(record, payload)
    db.session.commit()
    return record


def delete_event(user_id: int, event_id: int) -> None:
    record = get_event(user_id, event_id)
    db.session.delete(record)
    db.session.commit()


def validate_image(image: FileStorage | None) -> FileStorage:
    if image is None or not image.filename:
        raise ApiError(
            "An image file is required.",
            errors={"image": ["Attach an image file."]},
        )
    if image.mimetype not in ALLOWED_IMAGE_TYPES:
        raise ApiError(
            "Unsupported image type.",
            errors={
                "image": ["Use a JPEG or PNG image."]
            },
        )

    stream = image.stream
    current_position = stream.tell()
    stream.seek(0, 2)
    image_size = stream.tell()
    stream.seek(current_position)
    maximum_size = current_app.config["PROFILE_IMAGE_MAX_BYTES"]
    if image_size > maximum_size:
        raise ApiError(
            "Profile image is too large.",
            status_code=413,
            errors={
                "image": [
                    f"Maximum allowed size is {maximum_size} bytes."
                ]
            },
        )
    stream.seek(0)
    return image


def upload_to_cloudinary(
    image: FileStorage,
    user: User,
) -> dict[str, Any]:
    if not current_app.config.get("CLOUDINARY_URL"):
        raise ApiError(
            "Profile image service is not configured.",
            status_code=503,
        )
    asset_folder = current_app.config["CLOUDINARY_FOLDER"].strip("/")
    image_format = "jpg" if image.mimetype == "image/jpeg" else "png"
    try:
        result = cloudinary.uploader.upload(
            image.stream,
            public_id=user.username,
            asset_folder=asset_folder,
            use_asset_folder_as_public_id_prefix=True,
            display_name=user.username,
            filename_override=f"{user.username}.{image_format}",
            format=image_format,
            resource_type="image",
            overwrite=True,
            invalidate=True,
        )
    except CloudinaryError as error:
        current_app.logger.exception("Cloudinary image upload failed.")
        raise ApiError(
            "Profile image upload failed.",
            status_code=502,
        ) from error

    expected_public_id = profile_picture_public_id(user)
    if (
        result.get("error")
        or result.get("public_id") != expected_public_id
    ):
        raise ApiError(
            "Profile image upload failed.",
            status_code=502,
        )
    return result


def profile_picture_public_id(user: User) -> str:
    folder = current_app.config["CLOUDINARY_FOLDER"].strip("/")
    return f"{folder}/{user.username}"


def profile_picture_url(picture: ProfilePicture) -> str:
    configured_url = current_app.config.get("CLOUDINARY_URL")
    cloud_name = urlparse(configured_url).hostname if configured_url else None
    if not cloud_name:
        raise ApiError(
            "Profile image service is not configured.",
            status_code=503,
        )
    url, _ = cloudinary_url(
        picture.public_id,
        cloud_name=cloud_name,
        secure=True,
        resource_type="image",
        version=picture.version,
        format=picture.image_format,
    )
    return url


def destroy_cloudinary_asset(public_id: str) -> None:
    if not current_app.config.get("CLOUDINARY_URL"):
        raise ApiError(
            "Profile image service is not configured.",
            status_code=503,
        )
    try:
        result = cloudinary.uploader.destroy(
            public_id,
            resource_type="image",
            invalidate=True,
        )
    except CloudinaryError as error:
        current_app.logger.exception("Cloudinary image deletion failed.")
        raise ApiError(
            "Profile image deletion failed.",
            status_code=502,
        ) from error

    if result.get("result") not in {"ok", "not found"}:
        raise ApiError(
            "Profile image deletion failed.",
            status_code=502,
        )


def apply_cloudinary_result(
    picture: ProfilePicture,
    result: dict[str, Any],
) -> None:
    picture.public_id = result["public_id"]
    picture.version = result.get("version")
    picture.image_format = result.get("format")
    picture.width = result.get("width")
    picture.height = result.get("height")
    picture.file_size = result.get("bytes")


def create_picture(
    user_id: int,
    image: FileStorage | None,
) -> ProfilePicture:
    user = get_user(user_id)
    image = validate_image(image)
    if db.session.scalar(
        select(ProfilePicture.id).where(
            ProfilePicture.user_id == user_id
        )
    ):
        raise ApiError(
            "Profile picture already exists.",
            status_code=409,
        )
    result = upload_to_cloudinary(image, user)
    picture = ProfilePicture(user_id=user_id)
    apply_cloudinary_result(picture, result)
    db.session.add(picture)
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        try:
            destroy_cloudinary_asset(picture.public_id)
        except ApiError:
            current_app.logger.exception(
                "Cloudinary upload compensation failed."
            )
        raise
    return picture


def update_picture(
    user_id: int,
    image: FileStorage | None,
) -> ProfilePicture:
    user = get_user(user_id)
    picture = get_owned_record(
        ProfilePicture,
        user_id,
        "Profile picture was not found.",
    )
    image = validate_image(image)
    previous_public_id = picture.public_id
    result = upload_to_cloudinary(image, user)
    apply_cloudinary_result(picture, result)
    db.session.commit()

    if previous_public_id != picture.public_id:
        try:
            destroy_cloudinary_asset(previous_public_id)
        except ApiError:
            current_app.logger.exception(
                "Old Cloudinary profile image cleanup failed."
            )
    return picture


def delete_picture(user_id: int) -> None:
    picture = get_owned_record(
        ProfilePicture,
        user_id,
        "Profile picture was not found.",
    )
    destroy_cloudinary_asset(picture.public_id)
    db.session.delete(picture)
    db.session.commit()

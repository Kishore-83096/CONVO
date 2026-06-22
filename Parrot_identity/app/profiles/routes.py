from flask import Blueprint, request
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

from app.profiles.schemas import (
    AddressCreateSchema,
    AddressUpdateSchema,
    BasicProfileSchema,
    EventCreateSchema,
    EventUpdateSchema,
)
from app.profiles.services import (
    create_address,
    create_basic,
    create_event,
    create_picture,
    delete_address,
    delete_basic,
    delete_event,
    delete_picture,
    get_complete_profile,
    get_event,
    get_events,
    get_owned_record,
    serialize_address,
    serialize_basic,
    serialize_event,
    serialize_picture,
    update_address,
    update_basic,
    update_event,
    update_picture,
)
from app.profiles.models import (
    ProfileAddress,
    ProfileBasic,
    ProfilePicture,
)
from app.shared.exceptions import ApiError
from app.shared.responses import api_response


profiles_blueprint = Blueprint("profiles", __name__)
basic_schema = BasicProfileSchema()
address_create_schema = AddressCreateSchema()
address_update_schema = AddressUpdateSchema()
event_create_schema = EventCreateSchema()
event_update_schema = EventUpdateSchema()


@profiles_blueprint.before_request
def require_authentication():
    verify_jwt_in_request()


def current_user_id() -> int:
    return int(get_jwt_identity())


def json_request_body() -> dict:
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise ApiError("Request body must be a JSON object.")
    return payload


@profiles_blueprint.get("/me")
def get_profile():
    return api_response(
        success=True,
        message="Profile retrieved.",
        data=get_complete_profile(current_user_id()),
        status_code=200,
    )


@profiles_blueprint.get("/me/basic")
def get_basic_profile():
    record = get_owned_record(
        ProfileBasic,
        current_user_id(),
        "Basic profile data was not found.",
    )
    return api_response(
        success=True,
        message="Basic profile data retrieved.",
        data=serialize_basic(record),
        status_code=200,
    )


@profiles_blueprint.post("/me/basic")
def create_basic_profile():
    record = create_basic(
        current_user_id(),
        basic_schema.load(json_request_body()),
    )
    return api_response(
        success=True,
        message="Basic profile data created.",
        data=serialize_basic(record),
        status_code=201,
    )


@profiles_blueprint.patch("/me/basic")
@profiles_blueprint.put("/me/basic")
def update_basic_profile():
    record = update_basic(
        current_user_id(),
        basic_schema.load(json_request_body()),
    )
    return api_response(
        success=True,
        message="Basic profile data updated.",
        data=serialize_basic(record),
        status_code=200,
    )


@profiles_blueprint.delete("/me/basic")
def remove_basic_profile():
    delete_basic(current_user_id())
    return api_response(
        success=True,
        message="Basic profile data deleted.",
        status_code=200,
    )


@profiles_blueprint.get("/me/address")
def get_profile_address():
    record = get_owned_record(
        ProfileAddress,
        current_user_id(),
        "Address was not found.",
    )
    return api_response(
        success=True,
        message="Address retrieved.",
        data=serialize_address(record),
        status_code=200,
    )


@profiles_blueprint.post("/me/address")
def create_profile_address():
    record = create_address(
        current_user_id(),
        address_create_schema.load(json_request_body()),
    )
    return api_response(
        success=True,
        message="Address created.",
        data=serialize_address(record),
        status_code=201,
    )


@profiles_blueprint.patch("/me/address")
@profiles_blueprint.put("/me/address")
def update_profile_address():
    record = update_address(
        current_user_id(),
        address_update_schema.load(json_request_body()),
    )
    return api_response(
        success=True,
        message="Address updated.",
        data=serialize_address(record),
        status_code=200,
    )


@profiles_blueprint.delete("/me/address")
def remove_profile_address():
    delete_address(current_user_id())
    return api_response(
        success=True,
        message="Address deleted.",
        status_code=200,
    )


@profiles_blueprint.get("/me/events")
def list_profile_events():
    events = get_events(current_user_id())
    return api_response(
        success=True,
        message="Events retrieved.",
        data=[serialize_event(event) for event in events],
        status_code=200,
    )


@profiles_blueprint.post("/me/events")
def create_profile_event():
    record = create_event(
        current_user_id(),
        event_create_schema.load(json_request_body()),
    )
    return api_response(
        success=True,
        message="Event created.",
        data=serialize_event(record),
        status_code=201,
    )


@profiles_blueprint.get("/me/events/<int:event_id>")
def get_profile_event(event_id: int):
    record = get_event(current_user_id(), event_id)
    return api_response(
        success=True,
        message="Event retrieved.",
        data=serialize_event(record),
        status_code=200,
    )


@profiles_blueprint.patch("/me/events/<int:event_id>")
@profiles_blueprint.put("/me/events/<int:event_id>")
def update_profile_event(event_id: int):
    record = update_event(
        current_user_id(),
        event_id,
        event_update_schema.load(json_request_body()),
    )
    return api_response(
        success=True,
        message="Event updated.",
        data=serialize_event(record),
        status_code=200,
    )


@profiles_blueprint.delete("/me/events/<int:event_id>")
def remove_profile_event(event_id: int):
    delete_event(current_user_id(), event_id)
    return api_response(
        success=True,
        message="Event deleted.",
        status_code=200,
    )


@profiles_blueprint.get("/me/picture")
def get_profile_picture():
    record = get_owned_record(
        ProfilePicture,
        current_user_id(),
        "Profile picture was not found.",
    )
    return api_response(
        success=True,
        message="Profile picture retrieved.",
        data=serialize_picture(record),
        status_code=200,
    )


@profiles_blueprint.post("/me/picture")
def create_profile_picture():
    record = create_picture(
        current_user_id(),
        request.files.get("image"),
    )
    return api_response(
        success=True,
        message="Profile picture created.",
        data=serialize_picture(record),
        status_code=201,
    )


@profiles_blueprint.patch("/me/picture")
@profiles_blueprint.put("/me/picture")
def update_profile_picture():
    record = update_picture(
        current_user_id(),
        request.files.get("image"),
    )
    return api_response(
        success=True,
        message="Profile picture updated.",
        data=serialize_picture(record),
        status_code=200,
    )


@profiles_blueprint.delete("/me/picture")
def remove_profile_picture():
    delete_picture(current_user_id())
    return api_response(
        success=True,
        message="Profile picture deleted.",
        status_code=200,
    )

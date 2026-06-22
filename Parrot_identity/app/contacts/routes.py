from flask import Blueprint, request
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

from app.contacts.schemas import (
    AddContactSchema,
    RenameContactSchema,
    SearchContactSchema,
)
from app.contacts.services import (
    add_contact,
    delete_contact,
    get_contact,
    list_contacts,
    rename_contact,
    search_contact,
    serialize_contact_detail,
    serialize_contact_summary,
    serialize_search_result,
)
from app.extensions import limiter
from app.shared.exceptions import ApiError
from app.shared.responses import api_response


contacts_blueprint = Blueprint("contacts", __name__)
search_schema = SearchContactSchema()
add_schema = AddContactSchema()
rename_schema = RenameContactSchema()


@contacts_blueprint.before_request
def require_authentication():
    verify_jwt_in_request()


def current_user_id() -> int:
    return int(get_jwt_identity())


def json_request_body() -> dict:
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise ApiError("Request body must be a JSON object.")
    return payload


@contacts_blueprint.post("/search")
@limiter.limit("20 per minute")
def search():
    payload = search_schema.load(json_request_body())
    user, is_own_contact = search_contact(current_user_id(), payload)

    return api_response(
        success=True,
        message=(
            "This is your own contact."
            if is_own_contact
            else "Contact found."
        ),
        data=serialize_search_result(user),
        status_code=200,
    )


@contacts_blueprint.post("")
@limiter.limit("20 per minute")
def create():
    payload = add_schema.load(json_request_body())
    contact = add_contact(current_user_id(), payload)

    return api_response(
        success=True,
        message="Contact added.",
        data=serialize_contact_detail(contact),
        status_code=201,
    )


@contacts_blueprint.get("")
def get_contact_list():
    contacts = list_contacts(current_user_id())
    return api_response(
        success=True,
        message="Contact list retrieved.",
        data=[serialize_contact_summary(contact) for contact in contacts],
        status_code=200,
    )


@contacts_blueprint.get("/<int:contact_id>")
def get_one(contact_id: int):
    contact = get_contact(current_user_id(), contact_id)
    return api_response(
        success=True,
        message="Contact retrieved.",
        data=serialize_contact_detail(contact),
        status_code=200,
    )


@contacts_blueprint.patch("/<int:contact_id>")
def update(contact_id: int):
    payload = rename_schema.load(json_request_body())
    contact = rename_contact(current_user_id(), contact_id, payload)
    return api_response(
        success=True,
        message="Contact name updated.",
        data=serialize_contact_detail(contact),
        status_code=200,
    )


@contacts_blueprint.delete("/<int:contact_id>")
def delete(contact_id: int):
    delete_contact(current_user_id(), contact_id)
    return api_response(
        success=True,
        message="Contact deleted.",
        status_code=200,
    )

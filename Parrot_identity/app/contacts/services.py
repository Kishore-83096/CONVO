from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from app.auth.models import User
from app.contacts.models import Contact
from app.extensions import db
from app.profiles.services import serialize_picture
from app.shared.exceptions import ApiError


def normalize_contact_number(value) -> int:
    normalized = str(value).strip()
    if not normalized.isdigit() or len(normalized) != 10:
        raise ApiError(
            "Contact number must contain exactly 10 digits.",
            status_code=400,
        )
    return int(normalized)


def get_active_user(user_id: int) -> User:
    user = db.session.scalar(
        select(User).where(
            User.id == user_id,
            User.is_active.is_(True),
        )
    )
    if user is None:
        raise ApiError("User account was not found.", status_code=404)
    return user


def find_user_by_contact_number(value) -> User:
    contact_number = normalize_contact_number(value)
    user = db.session.scalar(
        select(User).where(
            User.contact_number == contact_number,
            User.is_active.is_(True),
        )
    )
    if user is None:
        raise ApiError("Contact number was not found.", status_code=404)
    return user


def serialize_search_result(user: User) -> dict:
    return {
        "full_name": user.full_name,
        "username": user.username,
        "profile_picture": serialize_picture(user.profile_picture),
    }


def serialize_contact_summary(contact: Contact) -> dict:
    return {
        "id": contact.id,
        "saved_name": contact.saved_name,
        "profile_picture": serialize_picture(
            contact.contact_user.profile_picture
        ),
    }


def serialize_contact_detail(contact: Contact) -> dict:
    user = contact.contact_user
    return {
        "id": contact.id,
        "saved_name": contact.saved_name,
        "contact_number": user.contact_number,
        "username": user.username,
        "full_name": user.full_name,
        "profile_picture": serialize_picture(user.profile_picture),
    }


def search_contact(user_id: int, payload: dict) -> tuple[User, bool]:
    current_user = get_active_user(user_id)
    found_user = find_user_by_contact_number(payload["contact_number"])
    return found_user, found_user.id == current_user.id


def add_contact(user_id: int, payload: dict) -> Contact:
    owner = get_active_user(user_id)
    contact_user = find_user_by_contact_number(payload["contact_number"])

    if contact_user.id == owner.id:
        raise ApiError(
            "You cannot add your own contact.",
            status_code=400,
        )

    existing_contact = db.session.scalar(
        select(Contact.id).where(
            Contact.owner_id == owner.id,
            Contact.contact_user_id == contact_user.id,
        )
    )
    if existing_contact is not None:
        raise ApiError(
            "Contact is already in your contact list.",
            status_code=409,
        )

    contact = Contact(
        owner=owner,
        contact_user=contact_user,
        saved_name=payload["saved_name"],
    )
    db.session.add(contact)
    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise ApiError(
            "Contact is already in your contact list.",
            status_code=409,
        ) from error
    return contact


def contact_query(user_id: int):
    return (
        select(Contact)
        .where(Contact.owner_id == user_id)
        .options(
            joinedload(Contact.contact_user).joinedload(
                User.profile_picture
            )
        )
    )


def list_contacts(user_id: int) -> list[Contact]:
    get_active_user(user_id)
    statement = contact_query(user_id).order_by(
        func.lower(Contact.saved_name),
        Contact.id,
    )
    return list(db.session.scalars(statement).all())


def get_contact(user_id: int, contact_id: int) -> Contact:
    get_active_user(user_id)
    contact = db.session.scalar(
        contact_query(user_id).where(Contact.id == contact_id)
    )
    if contact is None:
        raise ApiError("Contact was not found.", status_code=404)
    return contact


def rename_contact(
    user_id: int,
    contact_id: int,
    payload: dict,
) -> Contact:
    contact = get_contact(user_id, contact_id)
    contact.saved_name = payload["saved_name"]
    db.session.commit()
    return contact


def delete_contact(user_id: int, contact_id: int) -> None:
    contact = get_contact(user_id, contact_id)
    db.session.delete(contact)
    db.session.commit()

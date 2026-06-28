import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from datetime import timedelta, timezone
from flask import current_app
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from app.auth.models import User, utc_now
from app.contacts.models import Contact, ContactDeliveryPolicy
from app.extensions import db
from app.profiles.services import serialize_picture
from app.shared.exceptions import ApiError

DEFAULT_GHOST_DURATION_OPTION = "24h"

GHOST_DURATION_DELTAS = {
    "1h": timedelta(hours=1),
    "6h": timedelta(hours=6),
    "12h": timedelta(hours=12),
    "24h": timedelta(hours=24),
}


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

def _as_aware_utc(value):
    if value is None:
        return None

    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def _dt(value):
    aware_value = _as_aware_utc(value)
    return aware_value.isoformat() if aware_value else None


def _policy_is_ghost_active(
    policy: ContactDeliveryPolicy,
) -> bool:
    if policy.ghost_permanent:
        return True

    ghost_until = _as_aware_utc(policy.ghost_until)

    if ghost_until is None:
        return False

    return ghost_until > _as_aware_utc(utc_now())

def _dt(value):
    return value.isoformat() if value else None


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


def serialize_contact_delivery_policy(policy: ContactDeliveryPolicy) -> dict:
    return {
        "owner_user_id": policy.owner_id,
        "target_user_id": policy.target_user_id,
        "is_blocked": policy.is_blocked,
        "blocked_at": _dt(policy.blocked_at),
        "is_ghosted": _policy_is_ghost_active(policy),
        "ghost_until": _dt(policy.ghost_until),
        "ghost_permanent": bool(policy.ghost_permanent),
        "ghost_duration_option": policy.ghost_duration_option,
        "policy_version": policy.policy_version,
        "updated_at": _dt(policy.updated_at),
    }

def serialize_contact_with_delivery_policy(
    contact: Contact,
    policy: ContactDeliveryPolicy,
) -> dict:
    data = serialize_contact_detail(contact)
    data["delivery_policy"] = serialize_contact_delivery_policy(policy)
    return data


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


def _get_or_create_delivery_policy(
    *,
    owner_id: int,
    target_user_id: int,
) -> ContactDeliveryPolicy:
    policy = db.session.scalar(
        select(ContactDeliveryPolicy).where(
            ContactDeliveryPolicy.owner_id == owner_id,
            ContactDeliveryPolicy.target_user_id == target_user_id,
        )
    )

    if policy is not None:
        return policy

    policy = ContactDeliveryPolicy(
        owner_id=owner_id,
        target_user_id=target_user_id,
        is_blocked=False,
        ghost_until=None,
        ghost_permanent=False,
        ghost_duration_option=None,
        policy_version=1,
    )
    db.session.add(policy)
    return policy


def _sync_delivery_policy_to_messenger(
    policy: ContactDeliveryPolicy,
) -> None:
    base_url = current_app.config.get(
        "MESSENGER_SERVICE_BASE_URL",
        "",
    )
    internal_secret = current_app.config.get(
        "MESSENGER_INTERNAL_SECRET",
        "",
    )
    sync_required = current_app.config.get(
        "MESSENGER_POLICY_SYNC_REQUIRED",
        False,
    )

    if not base_url or not internal_secret:
        if sync_required:
            raise ApiError(
                "Messenger policy sync is not configured.",
                status_code=500,
            )
        return

    payload = {
        "owner_user_id": str(policy.owner_id),
        "target_user_id": str(policy.target_user_id),
        "is_blocked": bool(policy.is_blocked),
        "ghost_until": _dt(policy.ghost_until),
        "ghost_permanent": bool(policy.ghost_permanent),
        "ghost_duration_option": policy.ghost_duration_option or "",
        "policy_version": int(policy.policy_version),
        "source_updated_at": (
            policy.updated_at.isoformat()
            if policy.updated_at
            else None
        ),
    }

    url = f"{base_url.rstrip('/')}/api/v1/internal/contact-policies/"
    body = json.dumps(payload).encode("utf-8")

    request = Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-Myna-Internal-Secret": internal_secret,
        },
        method="POST",
    )

    timeout_seconds = current_app.config.get(
        "MESSENGER_POLICY_SYNC_TIMEOUT_SECONDS",
        3,
    )

    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            if response.status >= 400:
                raise ApiError(
                    "Messenger policy sync failed.",
                    status_code=502,
                )
    except HTTPError as error:
        raise ApiError(
            "Messenger policy sync failed.",
            status_code=502,
        ) from error
    except (URLError, TimeoutError, OSError) as error:
        raise ApiError(
            "Messenger policy sync is unavailable.",
            status_code=502,
        ) from error


def set_contact_block_status(
    user_id: int,
    contact_id: int,
    payload: dict,
) -> tuple[Contact, ContactDeliveryPolicy]:
    contact = get_contact(user_id, contact_id)
    desired_blocked = bool(payload["is_blocked"])

    policy = _get_or_create_delivery_policy(
        owner_id=contact.owner_id,
        target_user_id=contact.contact_user_id,
    )

    try:
        changed = policy.is_blocked != desired_blocked

        if changed:
            policy.is_blocked = desired_blocked
            policy.blocked_at = utc_now() if desired_blocked else None
            policy.policy_version = (policy.policy_version or 0) + 1

        db.session.flush()

        if changed:
            policy.updated_at = utc_now()
            db.session.flush()

        _sync_delivery_policy_to_messenger(policy)

        db.session.commit()

    except ApiError:
        db.session.rollback()
        raise

    except IntegrityError as error:
        db.session.rollback()
        raise ApiError(
            "Could not update contact block status.",
            status_code=409,
        ) from error

    return contact, policy




def _calculate_ghost_values(
    *,
    is_ghosted: bool,
    duration: str | None,
) -> tuple[object | None, bool, str | None]:
    if not is_ghosted:
        return None, False, None

    normalized_duration = (
        duration or DEFAULT_GHOST_DURATION_OPTION
    ).strip()

    if normalized_duration == "permanent":
        return None, True, "permanent"

    delta = GHOST_DURATION_DELTAS.get(normalized_duration)

    if delta is None:
        raise ApiError(
            "Ghost duration must be one of: 1h, 6h, 12h, 24h, permanent.",
            status_code=400,
        )

    return utc_now() + delta, False, normalized_duration


def set_contact_ghost_status(
    user_id: int,
    contact_id: int,
    payload: dict,
) -> tuple[Contact, ContactDeliveryPolicy]:
    contact = get_contact(user_id, contact_id)

    desired_ghosted = bool(payload["is_ghosted"])
    duration = payload.get(
        "duration",
        DEFAULT_GHOST_DURATION_OPTION,
    )

    ghost_until, ghost_permanent, ghost_duration_option = (
        _calculate_ghost_values(
            is_ghosted=desired_ghosted,
            duration=duration,
        )
    )

    policy = _get_or_create_delivery_policy(
        owner_id=contact.owner_id,
        target_user_id=contact.contact_user_id,
    )

    changed = (
        policy.ghost_until != ghost_until
        or bool(policy.ghost_permanent) != ghost_permanent
        or policy.ghost_duration_option != ghost_duration_option
    )

    if changed:
        policy.ghost_until = ghost_until
        policy.ghost_permanent = ghost_permanent
        policy.ghost_duration_option = ghost_duration_option
        policy.policy_version = (policy.policy_version or 0) + 1

    db.session.flush()

    if changed:
        policy.updated_at = utc_now()
        db.session.flush()

    _sync_delivery_policy_to_messenger(policy)

    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise ApiError(
            "Could not update contact ghost status.",
            status_code=409,
        ) from error

    return contact, policy
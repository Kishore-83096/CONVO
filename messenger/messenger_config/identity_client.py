import json
from dataclasses import dataclass
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings


class IdentityClientError(Exception):
    """Raised when the Identity service cannot validate users."""

class SavedContactResolutionError(IdentityClientError):
    """Raised when a saved contact cannot be resolved for messaging."""


class SavedContactForbiddenError(SavedContactResolutionError):
    """Raised when the user is not allowed to message this contact."""


@dataclass(frozen=True, slots=True)
class UnknownIdentityUsersError(IdentityClientError):
    unknown_user_ids: list[str]

    def __str__(self) -> str:
        return "Unknown Identity user IDs: " + ", ".join(
            self.unknown_user_ids
        )
    

@dataclass(frozen=True, slots=True)
class ResolvedMessageRecipient:
    contact_id: str
    contact_user_id: str
    saved_name: str = ""
    contact_number: str = ""

def _normalize_user_ids(user_ids: Iterable[str]) -> list[str]:
    normalized = [
        str(user_id).strip()
        for user_id in user_ids
        if str(user_id).strip()
    ]

    return list(dict.fromkeys(normalized))


def _extract_unknown_user_ids(
    *,
    requested_user_ids: list[str],
    payload: dict,
) -> list[str]:
    data = payload.get("data", payload)

    for key in (
        "unknown_user_ids",
        "missing_user_ids",
        "invalid_user_ids",
    ):
        value = data.get(key)
        if isinstance(value, list):
            return [
                str(item).strip()
                for item in value
                if str(item).strip()
            ]

    valid_user_ids = data.get("valid_user_ids")
    if isinstance(valid_user_ids, list):
        valid = {
            str(item).strip()
            for item in valid_user_ids
        }
        return [
            user_id
            for user_id in requested_user_ids
            if user_id not in valid
        ]

    users = data.get("users")
    if isinstance(users, list):
        valid = {
            str(item.get("id") or item.get("user_id") or "").strip()
            for item in users
            if isinstance(item, dict)
        }
        return [
            user_id
            for user_id in requested_user_ids
            if user_id not in valid
        ]

    return []


def validate_identity_user_ids(
    *,
    user_ids: Iterable[str],
    authorization_header: str | None = None,
) -> None:
    """Validate external Identity-service user IDs.

    Expected Identity endpoint, configurable by setting
    IDENTITY_SERVICE_USER_VALIDATE_PATH:

        POST <IDENTITY_SERVICE_BASE_URL>/users/validate/
        {"user_ids": ["1", "2"]}

    The parser also accepts common response variants such as valid_user_ids,
    unknown_user_ids, or users with id/user_id fields.
    """

    normalized_user_ids = _normalize_user_ids(user_ids)
    if not normalized_user_ids:
        return

    base_url = str(settings.IDENTITY_SERVICE_BASE_URL).strip().rstrip("/")
    path = str(
        getattr(
            settings,
            "IDENTITY_SERVICE_USER_VALIDATE_PATH",
            "/users/validate/",
        )
    ).strip()

    if not base_url:
        raise IdentityClientError(
            "IDENTITY_SERVICE_BASE_URL is not configured."
        )

    if not path.startswith("/"):
        path = f"/{path}"

    url = f"{base_url}{path}"
    request_body = json.dumps(
        {
            "user_ids": normalized_user_ids,
        }
    ).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if authorization_header:
        headers["Authorization"] = authorization_header

    request = Request(
        url,
        data=request_body,
        headers=headers,
        method="POST",
    )

    try:
        with urlopen(request, timeout=5) as response:
            raw_response = response.read().decode("utf-8")
            status_code = response.status
    except HTTPError as error:
        if error.code == 404:
            raise UnknownIdentityUsersError(normalized_user_ids) from error
        raise IdentityClientError(
            "Identity service user validation failed."
        ) from error
    except URLError as error:
        raise IdentityClientError(
            "Identity service is unavailable for user validation."
        ) from error

    if status_code < 200 or status_code >= 300:
        raise IdentityClientError(
            "Identity service user validation failed."
        )

    try:
        payload = json.loads(raw_response or "{}")
    except json.JSONDecodeError as error:
        raise IdentityClientError(
            "Identity service returned invalid JSON."
        ) from error

    if isinstance(payload, dict) and payload.get("success") is False:
        unknown_user_ids = _extract_unknown_user_ids(
            requested_user_ids=normalized_user_ids,
            payload=payload,
        )
        if unknown_user_ids:
            raise UnknownIdentityUsersError(unknown_user_ids)
        raise IdentityClientError(
            str(payload.get("message") or "Identity user validation failed.")
        )

    unknown_user_ids = _extract_unknown_user_ids(
        requested_user_ids=normalized_user_ids,
        payload=payload if isinstance(payload, dict) else {},
    )
    if unknown_user_ids:
        raise UnknownIdentityUsersError(unknown_user_ids)
    

def resolve_saved_contact_recipient(
    *,
    contact_id: int,
    authorization_header: str | None = None,
) -> ResolvedMessageRecipient:
    """
    Resolve recipient_contact_id through Identity service.

    Messenger must call this before:
    - claiming direct-chat prekey bundles
    - sending direct encrypted messages

    The same Bearer token is forwarded to Identity, so Identity can verify:
    Contact.owner_id == authenticated sender.
    """

    if not authorization_header:
        raise SavedContactForbiddenError(
            "Authorization header is required to resolve saved contact."
        )

    try:
        normalized_contact_id = int(contact_id)
    except (TypeError, ValueError) as error:
        raise SavedContactResolutionError(
            "recipient_contact_id must be a valid integer."
        ) from error

    if normalized_contact_id < 1:
        raise SavedContactResolutionError(
            "recipient_contact_id must be greater than zero."
        )

    base_url = str(settings.IDENTITY_SERVICE_BASE_URL).strip().rstrip("/")
    path = str(
        getattr(
            settings,
            "IDENTITY_SERVICE_CONTACT_RESOLVE_PATH",
            "/contacts/resolve-message-recipient",
        )
    ).strip()

    if not base_url:
        raise IdentityClientError(
            "IDENTITY_SERVICE_BASE_URL is not configured."
        )

    if not path.startswith("/"):
        path = f"/{path}"

    url = f"{base_url}{path}"

    request_body = json.dumps(
        {
            "contact_id": normalized_contact_id,
        }
    ).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": authorization_header,
    }

    request = Request(
        url,
        data=request_body,
        headers=headers,
        method="POST",
    )

    try:
        with urlopen(request, timeout=5) as response:
            raw_response = response.read().decode("utf-8")
            status_code = response.status

    except HTTPError as error:
        try:
            error_payload = json.loads(
                error.read().decode("utf-8") or "{}"
            )
        except json.JSONDecodeError:
            error_payload = {}

        message = (
            error_payload.get("message")
            if isinstance(error_payload, dict)
            else None
        ) or "Saved contact could not be resolved."

        if error.code in (401, 403, 404):
            raise SavedContactForbiddenError(message) from error

        raise IdentityClientError(
            "Identity service failed to resolve saved contact."
        ) from error

    except URLError as error:
        raise IdentityClientError(
            "Identity service is unavailable for saved-contact resolution."
        ) from error

    if status_code < 200 or status_code >= 300:
        raise IdentityClientError(
            "Identity service failed to resolve saved contact."
        )

    try:
        payload = json.loads(raw_response or "{}")
    except json.JSONDecodeError as error:
        raise IdentityClientError(
            "Identity service returned invalid JSON."
        ) from error

    if not isinstance(payload, dict):
        raise IdentityClientError(
            "Identity service returned an invalid response."
        )

    if payload.get("success") is False:
        raise SavedContactForbiddenError(
            str(
                payload.get("message")
                or "Saved contact could not be resolved."
            )
        )

    data = payload.get("data")
    if not isinstance(data, dict):
        raise IdentityClientError(
            "Identity service response is missing recipient data."
        )

    contact_user_id = str(
        data.get("contact_user_id") or ""
    ).strip()

    if not contact_user_id:
        raise IdentityClientError(
            "Identity service response is missing contact_user_id."
        )

    return ResolvedMessageRecipient(
        contact_id=str(data.get("contact_id") or normalized_contact_id),
        contact_user_id=contact_user_id,
        saved_name=str(data.get("saved_name") or ""),
        contact_number=str(data.get("contact_number") or ""),
    )
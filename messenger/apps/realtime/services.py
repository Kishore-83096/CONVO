from dataclasses import dataclass
from hashlib import sha256
from secrets import token_urlsafe
from typing import Any
from channels.db import database_sync_to_async
from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone
from .policies import can_view_presence
from .presence import get_user_presence_snapshot
from apps.e2ee_devices.models import Device

from .models import RealtimeTicket


class RealtimeTicketServiceError(Exception):
    """Base error for realtime ticket operations."""


class RealtimeTicketDeviceNotFoundError(RealtimeTicketServiceError):
    """Raised when the requested device does not exist."""


class RealtimeTicketDeviceOwnershipError(RealtimeTicketServiceError):
    """Raised when the requested device belongs to another user."""


class RealtimeTicketInactiveDeviceError(RealtimeTicketServiceError):
    """Raised when the requested device is inactive."""


@dataclass(frozen=True, slots=True)
class RealtimeTicketCreateResult:
    ticket: str
    ticket_record: RealtimeTicket


def normalize_user_id(user_id: Any) -> str:
    normalized = str(user_id).strip()

    if not normalized:
        raise RealtimeTicketServiceError(
            "A valid authenticated user ID is required."
        )

    return normalized


def hash_realtime_ticket(raw_ticket: str) -> str:
    """
    Hash a raw realtime ticket for database storage and later lookup.

    The raw ticket must never be stored.
    """

    return sha256(
        raw_ticket.encode("utf-8"),
    ).hexdigest()


def create_realtime_ticket(
    *,
    authenticated_user_id: Any,
    device_id: Any,
    ip_address: str | None = None,
    user_agent: str = "",
) -> RealtimeTicketCreateResult:
    user_id = normalize_user_id(authenticated_user_id)

    device = (
        Device.objects
        .filter(id=device_id)
        .first()
    )

    if device is None:
        raise RealtimeTicketDeviceNotFoundError(
            "Device not found."
        )

    if device.user_id != user_id:
        raise RealtimeTicketDeviceOwnershipError(
            "This device does not belong to the authenticated user."
        )

    if not device.is_active:
        raise RealtimeTicketInactiveDeviceError(
            "This device is inactive."
        )

    ttl_seconds = int(settings.REALTIME_TICKET_TTL_SECONDS)
    expires_at = timezone.now() + timezone.timedelta(
        seconds=ttl_seconds,
    )

    cleaned_user_agent = str(user_agent or "").strip()[:1000]

    for _ in range(3):
        raw_ticket = token_urlsafe(48)
        ticket_hash = hash_realtime_ticket(raw_ticket)

        try:
            with transaction.atomic():
                ticket_record = RealtimeTicket.objects.create(
                    ticket_hash=ticket_hash,
                    user_id=user_id,
                    device=device,
                    expires_at=expires_at,
                    ip_address=ip_address,
                    user_agent=cleaned_user_agent,
                )

            return RealtimeTicketCreateResult(
                ticket=raw_ticket,
                ticket_record=ticket_record,
            )

        except IntegrityError:
            continue

    raise RealtimeTicketServiceError(
        "Could not create realtime ticket."
    )



UNAVAILABLE_PRESENCE_STATUS = "unavailable"


def build_unavailable_presence_snapshot(
    *,
    subject_user_id: Any,
) -> dict[str, Any]:
    """
    Generic hidden/unavailable presence response.

    Never reveal whether the reason is:
    - blocked
    - ghosted
    - no relationship
    - privacy policy

    This is safe to return to restricted viewers.
    """

    return {
        "user_id": str(subject_user_id).strip(),
        "status": UNAVAILABLE_PRESENCE_STATUS,
        "online_device_ids": [],
        "last_seen_at": None,
    }


@database_sync_to_async
def can_view_presence_for_realtime(
    *,
    viewer_user_id: Any,
    subject_user_id: Any,
) -> bool:
    """
    Async-safe wrapper around the central directional policy helper.

    The central helper touches the database, so realtime async code must
    call it through database_sync_to_async.
    """

    return can_view_presence(
        viewer_user_id=viewer_user_id,
        subject_user_id=subject_user_id,
    )


async def get_presence_snapshot_for_viewer(
    *,
    viewer_user_id: Any,
    subject_user_id: Any,
) -> dict[str, Any]:
    """
    Return a presence snapshot that is already filtered for the viewer.

    Allowed viewer:
        returns actual online/offline/last_seen presence.

    Restricted viewer:
        returns generic unavailable state.

    Important:
        This function must never reveal block/ghost reason.
    """

    normalized_viewer_user_id = str(viewer_user_id).strip()
    normalized_subject_user_id = str(subject_user_id).strip()

    if not normalized_viewer_user_id or not normalized_subject_user_id:
        return build_unavailable_presence_snapshot(
            subject_user_id=normalized_subject_user_id,
        )

    allowed = await can_view_presence_for_realtime(
        viewer_user_id=normalized_viewer_user_id,
        subject_user_id=normalized_subject_user_id,
    )

    if not allowed:
        return build_unavailable_presence_snapshot(
            subject_user_id=normalized_subject_user_id,
        )

    return await get_user_presence_snapshot(
        user_id=normalized_subject_user_id,
    )
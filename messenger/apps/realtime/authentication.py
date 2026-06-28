from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from django.db import transaction
from django.utils import timezone

from .models import RealtimeTicket
from .services import hash_realtime_ticket


WEBSOCKET_AUTH_CLOSE_CODE = 4401


@dataclass(frozen=True, slots=True)
class AuthenticatedRealtimeTicket:
    ticket: RealtimeTicket
    user_id: str
    device_id: str
    device: Any


def get_ticket_from_scope(scope: dict[str, Any]) -> str:
    """
    Extract raw ticket from WebSocket query string.

    Expected URL:
        /ws/messenger/?ticket=<short-lived-ticket>
    """

    raw_query_string = scope.get("query_string", b"")

    if isinstance(raw_query_string, bytes):
        query_string = raw_query_string.decode("utf-8", errors="ignore")
    else:
        query_string = str(raw_query_string)

    parsed_query = parse_qs(
        query_string,
        keep_blank_values=False,
    )

    values = parsed_query.get("ticket", [])

    if not values:
        return ""

    return str(values[0]).strip()


@database_sync_to_async
def authenticate_realtime_ticket(
    raw_ticket: str,
) -> AuthenticatedRealtimeTicket | None:
    """
    Validate and consume a realtime ticket.

    Important:
        The ticket is one-use. A valid ticket is marked used during
        authentication, before the socket is accepted by the consumer.

    Returns:
        AuthenticatedRealtimeTicket when valid.
        None when invalid, expired, used, or inactive.
    """

    cleaned_ticket = str(raw_ticket or "").strip()

    if not cleaned_ticket:
        return None

    ticket_hash = hash_realtime_ticket(cleaned_ticket)
    now = timezone.now()

    with transaction.atomic():
        ticket = (
            RealtimeTicket.objects
            .select_for_update()
            .select_related("device")
            .filter(ticket_hash=ticket_hash)
            .first()
        )

        if ticket is None:
            return None

        if ticket.used_at is not None:
            return None

        if ticket.expires_at <= now:
            return None

        if not ticket.device.is_active:
            return None

        if ticket.device.user_id != ticket.user_id:
            return None

        ticket.used_at = now
        ticket.save(
            update_fields=[
                "used_at",
            ]
        )

        return AuthenticatedRealtimeTicket(
            ticket=ticket,
            user_id=ticket.user_id,
            device_id=str(ticket.device_id),
            device=ticket.device,
        )


class RealtimeTicketAuthMiddleware:
    """
    Channels ASGI middleware for WebSocket ticket authentication.

    This middleware does not accept the socket itself.
    It only authenticates the ticket and enriches scope.

    The actual consumer decides when to accept the socket.
    """

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        scope = dict(scope)

        raw_ticket = get_ticket_from_scope(scope)
        auth_result = await authenticate_realtime_ticket(raw_ticket)

        if auth_result is None:
            await send(
                {
                    "type": "websocket.close",
                    "code": WEBSOCKET_AUTH_CLOSE_CODE,
                }
            )
            return

        scope["myna_user_id"] = auth_result.user_id
        scope["myna_device_id"] = auth_result.device_id
        scope["myna_device"] = auth_result.device
        scope["realtime_ticket"] = auth_result.ticket

        return await self.inner(
            scope,
            receive,
            send,
        )
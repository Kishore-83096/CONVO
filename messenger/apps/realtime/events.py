import uuid
from typing import Any

from django.utils import timezone


CONNECTION_ACCEPTED = "connection.accepted"
HEARTBEAT_ACK = "heartbeat.ack"

MESSAGE_STORED = "message.stored"
GROUP_MESSAGE_STORED = "group.message.stored"
MESSAGE_DELIVERED = "message.delivered"
MESSAGE_READ = "message.read"

PRESENCE_CHANGED = "presence.changed"
PRESENCE_HIDDEN = "presence.hidden"

RECONCILIATION_REQUIRED = "reconciliation.required"

TYPING_STARTED = "typing.started"
TYPING_STOPPED = "typing.stopped"

CLIENT_ERROR = "client.error"


def build_event(
    event_type: str,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Build one consistent realtime event envelope.

    Do not put plaintext message content, decrypted attachment names,
    private keys, message keys, or recovery secrets in data.
    """

    return {
        "type": event_type,
        "event_id": str(uuid.uuid4()),
        "created_at": timezone.now().isoformat(),
        "data": data or {},
    }


def build_client_error_event(
    *,
    code: str,
    message: str,
) -> dict[str, Any]:
    return build_event(
        CLIENT_ERROR,
        {
            "code": code,
            "message": message,
        },
    )
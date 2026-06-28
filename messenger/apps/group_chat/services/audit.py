from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError

from apps.rooms.models import Room

from ..models import GroupAuditEvent


def record_group_audit_event(
    *,
    room: Room,
    actor_user_id: str,
    event_type: str,
    target_user_id: str = "",
    metadata: dict[str, Any] | None = None,
) -> GroupAuditEvent:
    event = GroupAuditEvent(
        group_room=room,
        actor_user_id=str(actor_user_id).strip(),
        event_type=str(event_type).strip(),
        target_user_id=str(target_user_id or "").strip(),
        metadata=metadata or {},
    )

    try:
        event.full_clean()
    except DjangoValidationError as error:
        raise ValueError(error.message_dict) from error

    event.save(force_insert=True)

    return event
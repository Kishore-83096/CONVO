from django.db import transaction

from apps.group_chat.constants import (
    GROUP_SECURITY_TRANSITION_REASON_DEVICE_ADDED,
    GROUP_SECURITY_TRANSITION_REASON_DEVICE_DEACTIVATED,
)
from apps.group_chat.services.security_transitions import (
    create_device_security_transitions_for_user,
)


def schedule_group_security_for_device_added(
    *,
    device,
    actor_user_id: str | None = None,
) -> None:
    """Schedule group epoch rotation after an active member device is added.

    The actual work is explicit and durable. This hook intentionally uses
    transaction.on_commit so group rotations do not run for rolled-back
    device registrations.
    """

    if not device.is_active:
        return

    actor = actor_user_id or device.user_id

    def _run():
        create_device_security_transitions_for_user(
            user_id=device.user_id,
            device=device,
            reason=GROUP_SECURITY_TRANSITION_REASON_DEVICE_ADDED,
            actor_user_id=actor,
        )

    transaction.on_commit(_run)


def schedule_group_security_for_device_deactivated(
    *,
    device,
    actor_user_id: str | None = None,
) -> None:
    """Schedule group epoch rotation after an active member device is removed."""

    actor = actor_user_id or device.user_id

    def _run():
        create_device_security_transitions_for_user(
            user_id=device.user_id,
            device=device,
            reason=GROUP_SECURITY_TRANSITION_REASON_DEVICE_DEACTIVATED,
            actor_user_id=actor,
        )

    transaction.on_commit(_run)
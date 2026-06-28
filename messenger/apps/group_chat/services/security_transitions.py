from dataclasses import dataclass
from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone

from apps.e2ee_devices.models import Device
from apps.rooms.models import Room, RoomMember

from ..constants import (
    EPOCH_ROTATION_REASON_MANUAL,
    EPOCH_ROTATION_REASON_MEMBER_ADDED,
    EPOCH_ROTATION_REASON_MEMBER_BANNED,
    EPOCH_ROTATION_REASON_MEMBER_LEFT,
    EPOCH_ROTATION_REASON_MEMBER_REMOVED,
    EPOCH_ROTATION_REASON_SECURITY_INCIDENT,
    GROUP_AUDIT_SECURITY_TRANSITION_APPLIED,
    GROUP_AUDIT_SECURITY_TRANSITION_CREATED,
    GROUP_AUDIT_SECURITY_TRANSITION_FAILED,
    GROUP_SECURITY_TRANSITION_REASON_DEVICE_ADDED,
    GROUP_SECURITY_TRANSITION_REASON_DEVICE_DEACTIVATED,
    GROUP_SECURITY_TRANSITION_REASON_MANUAL_SECURITY_ROTATION,
    GROUP_SECURITY_TRANSITION_REASON_MEMBER_ADDED,
    GROUP_SECURITY_TRANSITION_REASON_MEMBER_BANNED,
    GROUP_SECURITY_TRANSITION_REASON_MEMBER_LEFT,
    GROUP_SECURITY_TRANSITION_REASON_MEMBER_REACTIVATED,
    GROUP_SECURITY_TRANSITION_REASON_MEMBER_REMOVED,
    GROUP_SECURITY_TRANSITION_REASON_MEMBER_UNBANNED,
    GROUP_SECURITY_TRANSITION_STATUS_APPLIED,
    GROUP_SECURITY_TRANSITION_STATUS_FAILED,
    GROUP_SECURITY_TRANSITION_STATUS_PENDING,
    ROOM_TYPE_GROUP,
)
from ..models import GroupEncryptionEpoch, GroupSecurityTransition
from .audit import record_group_audit_event
from .epochs import rotate_group_epoch_system


class GroupSecurityTransitionServiceError(Exception):
    """Base exception for group security transition operations."""


class GroupSecurityTransitionValidationError(
    GroupSecurityTransitionServiceError
):
    """Raised when transition input is invalid."""


class GroupSecurityTransitionNotFoundError(
    GroupSecurityTransitionServiceError
):
    """Raised when transition or group does not exist."""


class GroupSecurityTransitionConflictError(
    GroupSecurityTransitionServiceError
):
    """Raised when transition state conflicts."""


@dataclass(frozen=True, slots=True)
class TransitionApplyResult:
    transition: GroupSecurityTransition
    old_epoch_number: int | None
    new_epoch_number: int | None
    applied: bool


TRANSITION_TO_EPOCH_REASON = {
    GROUP_SECURITY_TRANSITION_REASON_MEMBER_ADDED: (
        EPOCH_ROTATION_REASON_MEMBER_ADDED
    ),
    GROUP_SECURITY_TRANSITION_REASON_MEMBER_REMOVED: (
        EPOCH_ROTATION_REASON_MEMBER_REMOVED
    ),
    GROUP_SECURITY_TRANSITION_REASON_MEMBER_LEFT: (
        EPOCH_ROTATION_REASON_MEMBER_LEFT
    ),
    GROUP_SECURITY_TRANSITION_REASON_MEMBER_BANNED: (
        EPOCH_ROTATION_REASON_MEMBER_BANNED
    ),
    GROUP_SECURITY_TRANSITION_REASON_MEMBER_UNBANNED: (
        EPOCH_ROTATION_REASON_MEMBER_ADDED
    ),
    GROUP_SECURITY_TRANSITION_REASON_MEMBER_REACTIVATED: (
        EPOCH_ROTATION_REASON_MEMBER_ADDED
    ),
    GROUP_SECURITY_TRANSITION_REASON_DEVICE_ADDED: (
        EPOCH_ROTATION_REASON_SECURITY_INCIDENT
    ),
    GROUP_SECURITY_TRANSITION_REASON_DEVICE_DEACTIVATED: (
        EPOCH_ROTATION_REASON_SECURITY_INCIDENT
    ),
    GROUP_SECURITY_TRANSITION_REASON_MANUAL_SECURITY_ROTATION: (
        EPOCH_ROTATION_REASON_MANUAL
    ),
}


def _normalize_user_id(
    value: Any,
    *,
    field_name: str,
) -> str:
    user_id = str(value).strip()

    if not user_id:
        raise GroupSecurityTransitionValidationError(
            f"{field_name} is required."
        )

    return user_id


def _run_transition_validation(
    transition: GroupSecurityTransition,
) -> None:
    try:
        transition.full_clean()
    except DjangoValidationError as error:
        raise GroupSecurityTransitionValidationError(
            error.message_dict
            if hasattr(error, "message_dict")
            else str(error)
        ) from error


def _active_epoch_number(
    *,
    group_room: Room,
) -> int | None:
    epoch = (
        GroupEncryptionEpoch.objects.filter(
            group_room=group_room,
            status=GroupEncryptionEpoch.Status.ACTIVE,
        )
        .order_by("-epoch_number")
        .first()
    )

    if epoch is None:
        return None

    return epoch.epoch_number


def _create_transition(
    *,
    group_room: Room,
    reason: str,
    actor_user_id: Any,
    target_user_id: Any = "",
    target_device: Device | None = None,
) -> GroupSecurityTransition:
    actor_user_id = _normalize_user_id(
        actor_user_id,
        field_name="actor_user_id",
    )

    if group_room.room_type != ROOM_TYPE_GROUP:
        raise GroupSecurityTransitionValidationError(
            "Security transitions can only be created for group rooms."
        )

    transition = GroupSecurityTransition(
        group_room=group_room,
        reason=reason,
        actor_user_id=actor_user_id,
        target_user_id=str(target_user_id or "").strip(),
        target_device=target_device,
        status=GROUP_SECURITY_TRANSITION_STATUS_PENDING,
        attempt_count=0,
        last_error_code="",
    )

    _run_transition_validation(transition)
    transition.save(force_insert=True)

    record_group_audit_event(
        room=group_room,
        actor_user_id=actor_user_id,
        event_type=GROUP_AUDIT_SECURITY_TRANSITION_CREATED,
        target_user_id=transition.target_user_id,
        metadata={
            "transition_id": str(transition.id),
            "reason": transition.reason,
            "target_device_id": (
                str(target_device.id)
                if target_device is not None
                else ""
            ),
        },
    )

    return transition


def apply_security_transition(
    *,
    transition_id,
) -> TransitionApplyResult:
    transition_for_failure = None

    try:
        with transaction.atomic():
            transition = (
                GroupSecurityTransition.objects.select_for_update()
                .select_related(
                    "group_room",
                    "target_device",
                )
                .filter(id=transition_id)
                .first()
            )

            if transition is None:
                raise GroupSecurityTransitionNotFoundError(
                    "Security transition was not found."
                )

            transition_for_failure = transition

            if transition.status == GROUP_SECURITY_TRANSITION_STATUS_APPLIED:
                return TransitionApplyResult(
                    transition=transition,
                    old_epoch_number=transition.old_epoch_number,
                    new_epoch_number=transition.new_epoch_number,
                    applied=False,
                )

            if transition.status == GROUP_SECURITY_TRANSITION_STATUS_FAILED:
                raise GroupSecurityTransitionConflictError(
                    "Failed transitions must be retried explicitly."
                )

            old_epoch_number = _active_epoch_number(
                group_room=transition.group_room,
            )

            new_epoch = rotate_group_epoch_system(
                group_room=transition.group_room,
                actor_user_id=transition.actor_user_id,
                reason=TRANSITION_TO_EPOCH_REASON[transition.reason],
            )

            transition.status = GROUP_SECURITY_TRANSITION_STATUS_APPLIED
            transition.attempt_count += 1
            transition.old_epoch_number = old_epoch_number
            transition.new_epoch_number = new_epoch.epoch_number
            transition.applied_at = timezone.now()
            transition.last_error_code = ""

            _run_transition_validation(transition)
            transition.save(
                update_fields=[
                    "status",
                    "attempt_count",
                    "old_epoch_number",
                    "new_epoch_number",
                    "applied_at",
                    "last_error_code",
                ]
            )

            record_group_audit_event(
                room=transition.group_room,
                actor_user_id=transition.actor_user_id,
                event_type=GROUP_AUDIT_SECURITY_TRANSITION_APPLIED,
                target_user_id=transition.target_user_id,
                metadata={
                    "transition_id": str(transition.id),
                    "reason": transition.reason,
                    "old_epoch_number": old_epoch_number,
                    "new_epoch_number": new_epoch.epoch_number,
                },
            )

            return TransitionApplyResult(
                transition=transition,
                old_epoch_number=old_epoch_number,
                new_epoch_number=new_epoch.epoch_number,
                applied=True,
            )

    except (
        GroupSecurityTransitionNotFoundError,
        GroupSecurityTransitionConflictError,
    ):
        raise
    except Exception as error:
        if transition_for_failure is not None:
            with transaction.atomic():
                failed_transition = (
                    GroupSecurityTransition.objects.select_for_update()
                    .select_related("group_room")
                    .get(id=transition_for_failure.id)
                )

                failed_transition.status = (
                    GROUP_SECURITY_TRANSITION_STATUS_FAILED
                )
                failed_transition.attempt_count += 1
                failed_transition.last_error_code = error.__class__.__name__
                failed_transition.save(
                    update_fields=[
                        "status",
                        "attempt_count",
                        "last_error_code",
                    ]
                )

                record_group_audit_event(
                    room=failed_transition.group_room,
                    actor_user_id=failed_transition.actor_user_id,
                    event_type=GROUP_AUDIT_SECURITY_TRANSITION_FAILED,
                    target_user_id=failed_transition.target_user_id,
                    metadata={
                        "transition_id": str(failed_transition.id),
                        "reason": failed_transition.reason,
                        "error_code": failed_transition.last_error_code,
                    },
                )

        raise

    transition.status = GROUP_SECURITY_TRANSITION_STATUS_APPLIED
    transition.attempt_count += 1
    transition.old_epoch_number = old_epoch_number
    transition.new_epoch_number = new_epoch.epoch_number
    transition.applied_at = timezone.now()
    transition.last_error_code = ""

    _run_transition_validation(transition)
    transition.save(
        update_fields=[
            "status",
            "attempt_count",
            "old_epoch_number",
            "new_epoch_number",
            "applied_at",
            "last_error_code",
        ]
    )

    record_group_audit_event(
        room=transition.group_room,
        actor_user_id=transition.actor_user_id,
        event_type=GROUP_AUDIT_SECURITY_TRANSITION_APPLIED,
        target_user_id=transition.target_user_id,
        metadata={
            "transition_id": str(transition.id),
            "reason": transition.reason,
            "old_epoch_number": old_epoch_number,
            "new_epoch_number": new_epoch.epoch_number,
        },
    )

    return TransitionApplyResult(
        transition=transition,
        old_epoch_number=old_epoch_number,
        new_epoch_number=new_epoch.epoch_number,
        applied=True,
    )


@transaction.atomic
def create_and_apply_security_transition(
    *,
    group_room: Room,
    reason: str,
    actor_user_id: Any,
    target_user_id: Any = "",
    target_device: Device | None = None,
) -> TransitionApplyResult:
    transition = _create_transition(
        group_room=group_room,
        reason=reason,
        actor_user_id=actor_user_id,
        target_user_id=target_user_id,
        target_device=target_device,
    )

    return apply_security_transition(
        transition_id=transition.id,
    )


def retry_failed_security_transition(
    *,
    transition_id,
) -> TransitionApplyResult:
    transition = (
        GroupSecurityTransition.objects.filter(id=transition_id)
        .first()
    )

    if transition is None:
        raise GroupSecurityTransitionNotFoundError(
            "Security transition was not found."
        )

    if transition.status != GROUP_SECURITY_TRANSITION_STATUS_FAILED:
        return apply_security_transition(
            transition_id=transition.id,
        )

    transition.status = GROUP_SECURITY_TRANSITION_STATUS_PENDING
    transition.last_error_code = ""
    transition.save(
        update_fields=[
            "status",
            "last_error_code",
        ]
    )

    return apply_security_transition(
        transition_id=transition.id,
    )


def create_member_security_transition(
    *,
    group_room: Room,
    reason: str,
    actor_user_id: Any,
    target_user_id: Any,
) -> TransitionApplyResult:
    return create_and_apply_security_transition(
        group_room=group_room,
        reason=reason,
        actor_user_id=actor_user_id,
        target_user_id=target_user_id,
    )


def create_device_security_transitions_for_user(
    *,
    user_id: Any,
    device: Device,
    reason: str,
    actor_user_id: Any,
) -> list[TransitionApplyResult]:
    user_id = _normalize_user_id(
        user_id,
        field_name="user_id",
    )
    actor_user_id = _normalize_user_id(
        actor_user_id,
        field_name="actor_user_id",
    )

    active_group_memberships = (
        RoomMember.objects.select_related("room")
        .filter(
            user_id=user_id,
            is_active=True,
            room__room_type=ROOM_TYPE_GROUP,
            room__is_active=True,
        )
        .order_by("room_id")
    )

    results = []

    for membership in active_group_memberships:
        results.append(
            create_and_apply_security_transition(
                group_room=membership.room,
                reason=reason,
                actor_user_id=actor_user_id,
                target_user_id=user_id,
                target_device=device,
            )
        )

    return results
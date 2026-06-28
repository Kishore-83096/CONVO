from dataclasses import dataclass
from typing import Any
from uuid import UUID

from apps.e2ee_devices.models import RecoveryBundle
from apps.rooms.models import Room, RoomMember

from ..models import GroupEncryptionEpoch, GroupProfile


class GroupRecoveryServiceError(Exception):
    """Base exception for group recovery operations."""


class GroupRecoveryValidationError(GroupRecoveryServiceError):
    """Raised when group recovery input is invalid."""


class GroupRecoveryNotFoundError(GroupRecoveryServiceError):
    """Raised when group or epoch is missing."""


class GroupRecoveryPermissionError(GroupRecoveryServiceError):
    """Raised when caller cannot access group recovery data."""


@dataclass(frozen=True, slots=True)
class GroupRecoveryRecipient:
    user_id: str
    recovery_public_key: str
    recovery_version: int


@dataclass(frozen=True, slots=True)
class GroupRecoveryRecipientsResult:
    group_id: UUID
    epoch_number: int
    recipients: list[GroupRecoveryRecipient]


def _normalize_user_id(
    value: Any,
    *,
    field_name: str,
) -> str:
    user_id = str(value).strip()

    if not user_id:
        raise GroupRecoveryValidationError(
            f"{field_name} is required."
        )

    return user_id


def _get_authorized_group(
    *,
    group_id,
    actor_user_id: str,
) -> tuple[GroupProfile, GroupEncryptionEpoch]:
    profile = (
        GroupProfile.objects.select_related("room")
        .filter(
            room_id=group_id,
            room__room_type=Room.RoomType.GROUP,
            room__is_active=True,
        )
        .first()
    )

    if profile is None:
        raise GroupRecoveryNotFoundError("Group was not found.")

    is_member = RoomMember.objects.filter(
        room=profile.room,
        user_id=actor_user_id,
        is_active=True,
    ).exists()

    if not is_member:
        raise GroupRecoveryNotFoundError("Group was not found.")

    epoch = (
        GroupEncryptionEpoch.objects.filter(
            group_room=profile.room,
            status=GroupEncryptionEpoch.Status.ACTIVE,
        )
        .order_by("-epoch_number")
        .first()
    )

    if epoch is None:
        raise GroupRecoveryNotFoundError(
            "Active group epoch was not found."
        )

    return profile, epoch


def list_group_recovery_recipients(
    *,
    group_id,
    authenticated_user_id: Any,
) -> GroupRecoveryRecipientsResult:
    actor_user_id = _normalize_user_id(
        authenticated_user_id,
        field_name="authenticated_user_id",
    )

    profile, epoch = _get_authorized_group(
        group_id=group_id,
        actor_user_id=actor_user_id,
    )

    active_user_ids = list(
        RoomMember.objects.filter(
            room=profile.room,
            is_active=True,
        )
        .order_by("user_id")
        .values_list("user_id", flat=True)
    )

    bundles = (
        RecoveryBundle.objects.filter(
            user_id__in=active_user_ids,
            is_active=True,
        )
        .order_by("user_id")
    )

    recipients = [
        GroupRecoveryRecipient(
            user_id=bundle.user_id,
            recovery_public_key=bundle.recovery_public_key,
            recovery_version=bundle.recovery_version,
        )
        for bundle in bundles
    ]

    return GroupRecoveryRecipientsResult(
        group_id=profile.room_id,
        epoch_number=epoch.epoch_number,
        recipients=recipients,
    )
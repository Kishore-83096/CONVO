import hashlib
import json
from dataclasses import dataclass
from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import Max
from django.utils import timezone

from apps.rooms.models import Room, RoomMember

from ..constants import (
    EPOCH_ROTATION_REASON_INITIAL,
    EPOCH_ROTATION_REASON_MANUAL,
    GROUP_AUDIT_EPOCH_ROTATED,
    ROOM_TYPE_GROUP,
)
from ..models import GroupEncryptionEpoch, GroupProfile
from ..permissions import is_owner_or_admin
from .audit import record_group_audit_event
def _revoke_sender_keys_for_epoch(
    *,
    epoch,
    actor_user_id,
    reason,
) -> int:
    from .sender_keys import revoke_active_sender_keys_for_epoch

    return revoke_active_sender_keys_for_epoch(
        epoch=epoch,
        actor_user_id=actor_user_id,
        reason=reason,
    )

class GroupEpochServiceError(Exception):
    """Base exception for group epoch operations."""


class GroupEpochValidationError(GroupEpochServiceError):
    """Raised when epoch input is invalid."""


class GroupEpochNotFoundError(GroupEpochServiceError):
    """Raised when group or epoch does not exist."""


class GroupEpochPermissionError(GroupEpochServiceError):
    """Raised when caller cannot rotate epoch."""


class GroupEpochConflictError(GroupEpochServiceError):
    """Raised when epoch state conflicts."""


@dataclass(frozen=True, slots=True)
class EpochAccessContext:
    profile: GroupProfile
    room: Room
    actor_membership: RoomMember


def _normalize_user_id(
    value: Any,
    *,
    field_name: str,
) -> str:
    user_id = str(value).strip()

    if not user_id:
        raise GroupEpochValidationError(f"{field_name} is required.")

    return user_id


def _membership_snapshot_hash(
    *,
    room: Room,
) -> str:
    rows = list(
        RoomMember.objects.filter(
            room=room,
            is_active=True,
        )
        .order_by("user_id")
        .values_list(
            "user_id",
            "membership_version",
        )
    )

    canonical = [
        {
            "user_id": str(user_id),
            "membership_version": int(membership_version or 1),
        }
        for user_id, membership_version in rows
    ]
    canonical.sort(key=lambda item: item["user_id"])

    payload = json.dumps(
        canonical,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")

    return hashlib.sha256(payload).hexdigest()


def _run_epoch_validation(epoch: GroupEncryptionEpoch) -> None:
    try:
        epoch.full_clean()
    except DjangoValidationError as error:
        raise GroupEpochValidationError(
            error.message_dict
            if hasattr(error, "message_dict")
            else str(error)
        ) from error


def _get_context_for_update(
    *,
    group_id: Any,
    actor_user_id: Any,
) -> EpochAccessContext:
    actor_user_id = _normalize_user_id(
        actor_user_id,
        field_name="authenticated_user_id",
    )

    profile = (
        GroupProfile.objects.select_for_update()
        .select_related("room")
        .filter(
            room_id=group_id,
            room__room_type=ROOM_TYPE_GROUP,
            room__is_active=True,
        )
        .first()
    )

    if profile is None:
        raise GroupEpochNotFoundError("Group was not found.")

    room = (
        Room.objects.select_for_update()
        .filter(
            id=profile.room_id,
            room_type=ROOM_TYPE_GROUP,
            is_active=True,
        )
        .first()
    )

    if room is None:
        raise GroupEpochNotFoundError("Group was not found.")

    actor_membership = (
        RoomMember.objects.select_for_update()
        .filter(
            room=room,
            user_id=actor_user_id,
            is_active=True,
        )
        .first()
    )

    if actor_membership is None:
        raise GroupEpochNotFoundError("Group was not found.")

    return EpochAccessContext(
        profile=profile,
        room=room,
        actor_membership=actor_membership,
    )


def _get_context_for_read(
    *,
    group_id: Any,
    actor_user_id: Any,
) -> EpochAccessContext:
    actor_user_id = _normalize_user_id(
        actor_user_id,
        field_name="authenticated_user_id",
    )

    profile = (
        GroupProfile.objects.select_related("room")
        .filter(
            room_id=group_id,
            room__room_type=ROOM_TYPE_GROUP,
            room__is_active=True,
        )
        .first()
    )

    if profile is None:
        raise GroupEpochNotFoundError("Group was not found.")

    actor_membership = (
        RoomMember.objects.filter(
            room=profile.room,
            user_id=actor_user_id,
            is_active=True,
        )
        .first()
    )

    if actor_membership is None:
        raise GroupEpochNotFoundError("Group was not found.")

    return EpochAccessContext(
        profile=profile,
        room=profile.room,
        actor_membership=actor_membership,
    )


def _create_epoch(
    *,
    room: Room,
    epoch_number: int,
    actor_user_id: str,
    rotation_reason: str,
) -> GroupEncryptionEpoch:
    epoch = GroupEncryptionEpoch(
        group_room=room,
        epoch_number=epoch_number,
        status=GroupEncryptionEpoch.Status.ACTIVE,
        rotation_reason=rotation_reason,
        created_by_user_id=actor_user_id,
        membership_snapshot_hash=_membership_snapshot_hash(room=room),
        closed_at=None,
    )

    _run_epoch_validation(epoch)

    try:
        epoch.save(force_insert=True)
    except IntegrityError as error:
        raise GroupEpochConflictError(
            "Could not create group encryption epoch because of a conflict."
        ) from error

    return epoch


def create_initial_epoch_for_group(
    *,
    room: Room,
    actor_user_id: Any,
) -> GroupEncryptionEpoch:
    actor_user_id = _normalize_user_id(
        actor_user_id,
        field_name="actor_user_id",
    )

    if room.room_type != ROOM_TYPE_GROUP:
        raise GroupEpochValidationError(
            "Initial epoch can only be created for group rooms."
        )

    existing = (
        GroupEncryptionEpoch.objects.filter(
            group_room=room,
        )
        .order_by("-epoch_number")
        .first()
    )

    if existing is not None:
        return existing

    return _create_epoch(
        room=room,
        epoch_number=1,
        actor_user_id=actor_user_id,
        rotation_reason=EPOCH_ROTATION_REASON_INITIAL,
    )


def get_current_group_epoch(
    *,
    authenticated_user_id: Any,
    group_id: Any,
) -> GroupEncryptionEpoch:
    context = _get_context_for_read(
        group_id=group_id,
        actor_user_id=authenticated_user_id,
    )

    epoch = (
        GroupEncryptionEpoch.objects.filter(
            group_room=context.room,
            status=GroupEncryptionEpoch.Status.ACTIVE,
        )
        .order_by("-epoch_number")
        .first()
    )

    if epoch is None:
        raise GroupEpochNotFoundError("Current group epoch was not found.")

    return epoch


def list_group_epochs(
    *,
    authenticated_user_id: Any,
    group_id: Any,
) -> list[GroupEncryptionEpoch]:
    context = _get_context_for_read(
        group_id=group_id,
        actor_user_id=authenticated_user_id,
    )

    return list(
        GroupEncryptionEpoch.objects.filter(
            group_room=context.room,
        ).order_by(
            "-epoch_number",
            "-created_at",
        )
    )


@transaction.atomic
def rotate_group_epoch(
    *,
    authenticated_user_id: Any,
    group_id: Any,
    reason: str = EPOCH_ROTATION_REASON_MANUAL,
) -> GroupEncryptionEpoch:
    actor_user_id = _normalize_user_id(
        authenticated_user_id,
        field_name="authenticated_user_id",
    )

    context = _get_context_for_update(
        group_id=group_id,
        actor_user_id=actor_user_id,
    )

    if not is_owner_or_admin(context.actor_membership):
        raise GroupEpochPermissionError(
            "Only the group owner or an admin can rotate group epochs."
        )

    current_epoch = (
        GroupEncryptionEpoch.objects.select_for_update()
        .filter(
            group_room=context.room,
            status=GroupEncryptionEpoch.Status.ACTIVE,
        )
        .order_by("-epoch_number")
        .first()
    )

    if current_epoch is None:
        return create_initial_epoch_for_group(
            room=context.room,
            actor_user_id=actor_user_id,
        )

    now = timezone.now()

    old_epoch_number = current_epoch.epoch_number

    _revoke_sender_keys_for_epoch(
        epoch=current_epoch,
        actor_user_id=actor_user_id,
        reason=reason,
    )

    current_epoch.status = GroupEncryptionEpoch.Status.CLOSED

    current_epoch.closed_at = now
    _run_epoch_validation(current_epoch)
    current_epoch.save(
        update_fields=[
            "status",
            "closed_at",
            "active_epoch_key",
        ]
    )

    next_epoch = _create_epoch(
        room=context.room,
        epoch_number=old_epoch_number + 1,
        actor_user_id=actor_user_id,
        rotation_reason=reason,
    )

    record_group_audit_event(
        room=context.room,
        actor_user_id=actor_user_id,
        event_type=GROUP_AUDIT_EPOCH_ROTATED,
        metadata={
            "old_epoch_number": old_epoch_number,
            "new_epoch_number": next_epoch.epoch_number,
            "rotation_reason": reason,
        },
    )

    context.room.save(update_fields=["updated_at"])

    return next_epoch


@transaction.atomic
def rotate_epoch_after_membership_change(
    *,
    room: Room,
    actor_user_id: Any,
    rotation_reason: str,
) -> GroupEncryptionEpoch:
    actor_user_id = _normalize_user_id(
        actor_user_id,
        field_name="actor_user_id",
    )

    if room.room_type != ROOM_TYPE_GROUP:
        raise GroupEpochValidationError(
            "Epoch rotation can only run for group rooms."
        )

    current_epoch = (
        GroupEncryptionEpoch.objects.select_for_update()
        .filter(
            group_room=room,
            status=GroupEncryptionEpoch.Status.ACTIVE,
        )
        .order_by("-epoch_number")
        .first()
    )

    if current_epoch is None:
        return create_initial_epoch_for_group(
            room=room,
            actor_user_id=actor_user_id,
        )

    now = timezone.now()
    old_epoch_number = current_epoch.epoch_number

    _revoke_sender_keys_for_epoch(
        epoch=current_epoch,
        actor_user_id=actor_user_id,
        reason=rotation_reason,
    )

    current_epoch.status = GroupEncryptionEpoch.Status.CLOSED
    
    current_epoch.closed_at = now
    _run_epoch_validation(current_epoch)
    current_epoch.save(
        update_fields=[
            "status",
            "closed_at",
            "active_epoch_key",
        ]
    )

    next_epoch = _create_epoch(
        room=room,
        epoch_number=old_epoch_number + 1,
        actor_user_id=actor_user_id,
        rotation_reason=rotation_reason,
    )

    record_group_audit_event(
        room=room,
        actor_user_id=actor_user_id,
        event_type=GROUP_AUDIT_EPOCH_ROTATED,
        metadata={
            "old_epoch_number": old_epoch_number,
            "new_epoch_number": next_epoch.epoch_number,
            "rotation_reason": rotation_reason,
        },
    )

    room.save(update_fields=["updated_at"])

    return next_epoch


def get_active_epoch_numbers_by_room_id(
    *,
    room_ids: list[Any],
) -> dict[Any, int]:
    epochs = GroupEncryptionEpoch.objects.filter(
        group_room_id__in=room_ids,
        status=GroupEncryptionEpoch.Status.ACTIVE,
    ).values_list(
        "group_room_id",
        "epoch_number",
    )

    return {
        room_id: epoch_number
        for room_id, epoch_number in epochs
    }


def get_next_epoch_number(
    *,
    room: Room,
) -> int:
    max_epoch = (
        GroupEncryptionEpoch.objects.filter(
            group_room=room,
        ).aggregate(
            value=Max("epoch_number"),
        )["value"]
        or 0
    )

    return int(max_epoch) + 1





@transaction.atomic
def rotate_group_epoch_system(
    *,
    group_room: Room,
    actor_user_id: Any,
    reason: str,
) -> GroupEncryptionEpoch:
    """Rotate epoch without requiring actor role checks.

    Used by trusted backend orchestration after membership/device security
    transitions. User-facing manual rotation must still use rotate_group_epoch.
    """

    actor_user_id = _normalize_user_id(
        actor_user_id,
        field_name="actor_user_id",
    )

    if group_room.room_type != ROOM_TYPE_GROUP:
        raise GroupEpochValidationError(
            "Epoch rotation can only run for group rooms."
        )

    room = (
        Room.objects.select_for_update()
        .filter(
            id=group_room.id,
            room_type=ROOM_TYPE_GROUP,
            is_active=True,
        )
        .first()
    )

    if room is None:
        raise GroupEpochNotFoundError("Group was not found.")

    current_epoch = (
        GroupEncryptionEpoch.objects.select_for_update()
        .filter(
            group_room=room,
            status=GroupEncryptionEpoch.Status.ACTIVE,
        )
        .order_by("-epoch_number")
        .first()
    )

    if current_epoch is None:
        return create_initial_epoch_for_group(
            room=room,
            actor_user_id=actor_user_id,
        )

    now = timezone.now()
    old_epoch_number = current_epoch.epoch_number

    _revoke_sender_keys_for_epoch(
        epoch=current_epoch,
        actor_user_id=actor_user_id,
        reason=reason,
    )

    current_epoch.status = GroupEncryptionEpoch.Status.CLOSED
    current_epoch.closed_at = now
    _run_epoch_validation(current_epoch)
    current_epoch.save(
        update_fields=[
            "status",
            "closed_at",
            "active_epoch_key",
        ]
    )

    next_epoch = _create_epoch(
        room=room,
        epoch_number=old_epoch_number + 1,
        actor_user_id=actor_user_id,
        rotation_reason=reason,
    )

    record_group_audit_event(
        room=room,
        actor_user_id=actor_user_id,
        event_type=GROUP_AUDIT_EPOCH_ROTATED,
        metadata={
            "old_epoch_number": old_epoch_number,
            "new_epoch_number": next_epoch.epoch_number,
            "rotation_reason": reason,
            "system_orchestrated": True,
        },
    )

    room.save(update_fields=["updated_at"])

    return next_epoch
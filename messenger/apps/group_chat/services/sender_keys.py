from dataclasses import dataclass
from typing import Any
from uuid import UUID

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.e2ee_devices.models import Device
from apps.rooms.models import Room, RoomMember

from ..constants import (
    GROUP_AUDIT_SENDER_KEY_REGISTERED,
    GROUP_AUDIT_SENDER_KEY_REVOKED,
    GROUP_SENDER_KEY_ALGORITHM,
    GROUP_SENDER_KEY_SIGNING_ALGORITHM,
    GROUP_SENDER_KEY_VERSION,
    ROOM_TYPE_GROUP,
)
from ..models import GroupEncryptionEpoch, GroupProfile, GroupSenderKey
from ..permissions import is_owner_or_admin
from .audit import record_group_audit_event


class GroupSenderKeyServiceError(Exception):
    """Base exception for group sender-key operations."""


class GroupSenderKeyValidationError(GroupSenderKeyServiceError):
    """Raised when sender-key input is invalid."""


class GroupSenderKeyNotFoundError(GroupSenderKeyServiceError):
    """Raised when group, device, epoch or sender key does not exist."""


class GroupSenderKeyPermissionError(GroupSenderKeyServiceError):
    """Raised when caller cannot access a sender key operation."""


class GroupSenderKeyConflictError(GroupSenderKeyServiceError):
    """Raised when sender-key registration conflicts."""


@dataclass(frozen=True, slots=True)
class SenderKeyRegistrationResult:
    sender_key: GroupSenderKey
    created: bool


@dataclass(frozen=True, slots=True)
class SenderKeyAccessContext:
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
        raise GroupSenderKeyValidationError(
            f"{field_name} is required."
        )

    return user_id


def _normalize_uuid(
    value: Any,
    *,
    field_name: str,
) -> UUID:
    try:
        return UUID(str(value))
    except (TypeError, ValueError, AttributeError) as error:
        raise GroupSenderKeyValidationError(
            f"{field_name} must be a valid UUID."
        ) from error


def _run_sender_key_validation(sender_key: GroupSenderKey) -> None:
    try:
        sender_key.full_clean()
    except DjangoValidationError as error:
        raise GroupSenderKeyValidationError(
            error.message_dict
            if hasattr(error, "message_dict")
            else str(error)
        ) from error


def _get_context_for_read(
    *,
    group_id: Any,
    actor_user_id: Any,
) -> SenderKeyAccessContext:
    actor_user_id = _normalize_user_id(
        actor_user_id,
        field_name="authenticated_user_id",
    )

    group_uuid = _normalize_uuid(
        group_id,
        field_name="group_id",
    )

    profile = (
        GroupProfile.objects.select_related("room")
        .filter(
            room_id=group_uuid,
            room__room_type=ROOM_TYPE_GROUP,
            room__is_active=True,
        )
        .first()
    )

    if profile is None:
        raise GroupSenderKeyNotFoundError("Group was not found.")

    actor_membership = (
        RoomMember.objects.filter(
            room=profile.room,
            user_id=actor_user_id,
            is_active=True,
        )
        .first()
    )

    if actor_membership is None:
        raise GroupSenderKeyNotFoundError("Group was not found.")

    return SenderKeyAccessContext(
        profile=profile,
        room=profile.room,
        actor_membership=actor_membership,
    )


def _get_context_for_update(
    *,
    group_id: Any,
    actor_user_id: Any,
) -> SenderKeyAccessContext:
    actor_user_id = _normalize_user_id(
        actor_user_id,
        field_name="authenticated_user_id",
    )

    group_uuid = _normalize_uuid(
        group_id,
        field_name="group_id",
    )

    profile = (
        GroupProfile.objects.select_for_update()
        .select_related("room")
        .filter(
            room_id=group_uuid,
            room__room_type=ROOM_TYPE_GROUP,
            room__is_active=True,
        )
        .first()
    )

    if profile is None:
        raise GroupSenderKeyNotFoundError("Group was not found.")

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
        raise GroupSenderKeyNotFoundError("Group was not found.")

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
        raise GroupSenderKeyNotFoundError("Group was not found.")

    return SenderKeyAccessContext(
        profile=profile,
        room=room,
        actor_membership=actor_membership,
    )


def _get_active_sender_device(
    *,
    device_id: Any,
    actor_user_id: str,
) -> Device:
    device_uuid = _normalize_uuid(
        device_id,
        field_name="sender_device_id",
    )

    device = (
        Device.objects.select_for_update()
        .filter(
            id=device_uuid,
            is_active=True,
        )
        .first()
    )

    if device is None:
        raise GroupSenderKeyNotFoundError(
            "Sender device was not found."
        )

    if device.user_id != actor_user_id:
        raise GroupSenderKeyPermissionError(
            "Sender device does not belong to the authenticated user."
        )

    return device


def _get_current_epoch_by_number(
    *,
    room: Room,
    epoch_number: int,
) -> GroupEncryptionEpoch:
    epoch = (
        GroupEncryptionEpoch.objects.select_for_update()
        .filter(
            group_room=room,
            epoch_number=epoch_number,
        )
        .first()
    )

    if epoch is None:
        raise GroupSenderKeyNotFoundError(
            "Group epoch was not found."
        )

    if epoch.status != GroupEncryptionEpoch.Status.ACTIVE:
        raise GroupSenderKeyConflictError(
            "Sender keys can only be registered for the active epoch."
        )

    return epoch


def _sender_key_matches_payload(
    *,
    existing: GroupSenderKey,
    room: Room,
    epoch: GroupEncryptionEpoch,
    actor_user_id: str,
    sender_device: Device,
    signing_public_key: str,
    key_algorithm: str,
    signing_algorithm: str,
    key_version: int,
) -> bool:
    return (
        existing.group_room_id == room.id
        and existing.epoch_id == epoch.id
        and existing.sender_user_id == actor_user_id
        and existing.sender_device_id == sender_device.id
        and existing.signing_public_key == signing_public_key
        and existing.key_algorithm == key_algorithm
        and existing.signing_algorithm == signing_algorithm
        and existing.key_version == key_version
        and existing.is_active
    )


@transaction.atomic
def register_group_sender_key(
    *,
    authenticated_user_id: Any,
    group_id: Any,
    sender_device_id: Any,
    epoch_number: int,
    sender_key_id: Any,
    signing_public_key: str,
    key_algorithm: str = GROUP_SENDER_KEY_ALGORITHM,
    signing_algorithm: str = GROUP_SENDER_KEY_SIGNING_ALGORITHM,
    key_version: int = GROUP_SENDER_KEY_VERSION,
) -> SenderKeyRegistrationResult:
    actor_user_id = _normalize_user_id(
        authenticated_user_id,
        field_name="authenticated_user_id",
    )

    sender_key_uuid = _normalize_uuid(
        sender_key_id,
        field_name="sender_key_id",
    )

    signing_public_key = str(signing_public_key).strip()
    key_algorithm = str(key_algorithm).strip().lower()
    signing_algorithm = str(signing_algorithm).strip().lower()

    if not signing_public_key:
        raise GroupSenderKeyValidationError(
            "Signing public key is required."
        )

    context = _get_context_for_update(
        group_id=group_id,
        actor_user_id=actor_user_id,
    )

    sender_device = _get_active_sender_device(
        device_id=sender_device_id,
        actor_user_id=actor_user_id,
    )

    epoch = _get_current_epoch_by_number(
        room=context.room,
        epoch_number=int(epoch_number),
    )

    existing_by_sender_key_id = (
        GroupSenderKey.objects.select_for_update()
        .filter(sender_key_id=sender_key_uuid)
        .first()
    )

    if existing_by_sender_key_id is not None:
        if _sender_key_matches_payload(
            existing=existing_by_sender_key_id,
            room=context.room,
            epoch=epoch,
            actor_user_id=actor_user_id,
            sender_device=sender_device,
            signing_public_key=signing_public_key,
            key_algorithm=key_algorithm,
            signing_algorithm=signing_algorithm,
            key_version=key_version,
        ):
            return SenderKeyRegistrationResult(
                sender_key=existing_by_sender_key_id,
                created=False,
            )

        raise GroupSenderKeyConflictError(
            "sender_key_id already exists with different sender-key data."
        )

    active_for_device = (
        GroupSenderKey.objects.select_for_update()
        .filter(
            epoch=epoch,
            sender_device=sender_device,
            is_active=True,
        )
        .first()
    )

    if active_for_device is not None:
        raise GroupSenderKeyConflictError(
            "This device already has an active sender key for this epoch."
        )

    sender_key = GroupSenderKey(
        group_room=context.room,
        epoch=epoch,
        sender_user_id=actor_user_id,
        sender_device=sender_device,
        sender_key_id=sender_key_uuid,
        signing_public_key=signing_public_key,
        key_algorithm=key_algorithm,
        signing_algorithm=signing_algorithm,
        key_version=key_version,
        highest_accepted_iteration=0,
        is_active=True,
        revoked_at=None,
    )

    _run_sender_key_validation(sender_key)

    try:
        sender_key.save(force_insert=True)
    except IntegrityError as error:
        raise GroupSenderKeyConflictError(
            "Could not register sender key because of a conflict."
        ) from error

    record_group_audit_event(
        room=context.room,
        actor_user_id=actor_user_id,
        event_type=GROUP_AUDIT_SENDER_KEY_REGISTERED,
        target_user_id=actor_user_id,
        metadata={
            "sender_device_id": str(sender_device.id),
            "sender_key_id": str(sender_key.sender_key_id),
            "epoch_number": epoch.epoch_number,
            "key_algorithm": sender_key.key_algorithm,
            "signing_algorithm": sender_key.signing_algorithm,
            "key_version": sender_key.key_version,
        },
    )

    return SenderKeyRegistrationResult(
        sender_key=sender_key,
        created=True,
    )


def get_my_group_sender_key(
    *,
    authenticated_user_id: Any,
    group_id: Any,
    sender_device_id: Any,
) -> GroupSenderKey | None:
    actor_user_id = _normalize_user_id(
        authenticated_user_id,
        field_name="authenticated_user_id",
    )

    context = _get_context_for_read(
        group_id=group_id,
        actor_user_id=actor_user_id,
    )

    device_uuid = _normalize_uuid(
        sender_device_id,
        field_name="device_id",
    )

    device = (
        Device.objects.filter(
            id=device_uuid,
            is_active=True,
        )
        .first()
    )

    if device is None:
        raise GroupSenderKeyNotFoundError(
            "Sender device was not found."
        )

    if device.user_id != actor_user_id:
        raise GroupSenderKeyPermissionError(
            "Sender device does not belong to the authenticated user."
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
        raise GroupSenderKeyNotFoundError(
            "Current group epoch was not found."
        )

    return (
        GroupSenderKey.objects.select_related(
            "epoch",
            "sender_device",
        )
        .filter(
            group_room=context.room,
            epoch=epoch,
            sender_user_id=actor_user_id,
            sender_device=device,
            is_active=True,
        )
        .first()
    )


@transaction.atomic
def revoke_group_sender_key(
    *,
    authenticated_user_id: Any,
    group_id: Any,
    sender_key_id: Any,
) -> GroupSenderKey:
    actor_user_id = _normalize_user_id(
        authenticated_user_id,
        field_name="authenticated_user_id",
    )

    sender_key_uuid = _normalize_uuid(
        sender_key_id,
        field_name="sender_key_id",
    )

    context = _get_context_for_update(
        group_id=group_id,
        actor_user_id=actor_user_id,
    )

    sender_key = (
        GroupSenderKey.objects.select_for_update()
        .select_related(
            "epoch",
            "sender_device",
        )
        .filter(
            group_room=context.room,
            sender_key_id=sender_key_uuid,
        )
        .first()
    )

    if sender_key is None:
        raise GroupSenderKeyNotFoundError(
            "Sender key was not found."
        )

    caller_is_owner = sender_key.sender_user_id == actor_user_id
    caller_is_admin = is_owner_or_admin(context.actor_membership)

    if not caller_is_owner and not caller_is_admin:
        raise GroupSenderKeyPermissionError(
            "Only the sender-key owner, group owner or admin can revoke it."
        )

    if not sender_key.is_active:
        return sender_key

    sender_key.is_active = False
    sender_key.revoked_at = timezone.now()

    _run_sender_key_validation(sender_key)

    sender_key.save(
        update_fields=[
            "is_active",
            "revoked_at",
            "active_sender_device_epoch_key",
        ]
    )

    record_group_audit_event(
        room=context.room,
        actor_user_id=actor_user_id,
        event_type=GROUP_AUDIT_SENDER_KEY_REVOKED,
        target_user_id=sender_key.sender_user_id,
        metadata={
            "sender_device_id": str(sender_key.sender_device_id),
            "sender_key_id": str(sender_key.sender_key_id),
            "epoch_number": sender_key.epoch.epoch_number,
        },
    )

    return sender_key


def revoke_active_sender_keys_for_epoch(
    *,
    epoch: GroupEncryptionEpoch,
    actor_user_id: Any,
    reason: str,
) -> int:
    actor_user_id = _normalize_user_id(
        actor_user_id,
        field_name="actor_user_id",
    )

    now = timezone.now()

    sender_keys = list(
        GroupSenderKey.objects.select_for_update()
        .select_related("epoch")
        .filter(
            epoch=epoch,
            is_active=True,
        )
    )

    for sender_key in sender_keys:
        sender_key.is_active = False
        sender_key.revoked_at = now
        sender_key.save(
            update_fields=[
                "is_active",
                "revoked_at",
                "active_sender_device_epoch_key",
            ]
        )

    if sender_keys:
        record_group_audit_event(
            room=epoch.group_room,
            actor_user_id=actor_user_id,
            event_type=GROUP_AUDIT_SENDER_KEY_REVOKED,
            metadata={
                "epoch_number": epoch.epoch_number,
                "revoked_count": len(sender_keys),
                "reason": reason,
            },
        )

    return len(sender_keys)
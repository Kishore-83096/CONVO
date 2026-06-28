from dataclasses import dataclass
from typing import Any
from uuid import UUID

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.e2ee_devices.models import Device
from apps.rooms.models import Room, RoomMember

from ..constants import (
    GROUP_AUDIT_SENDER_KEY_DISTRIBUTED,
    GROUP_AUDIT_SENDER_KEY_DISTRIBUTION_ACKED,
    GROUP_SENDER_KEY_DISTRIBUTION_STATUS_ACKNOWLEDGED,
    GROUP_SENDER_KEY_DISTRIBUTION_STATUS_STORED,
    GROUP_SENDER_KEY_DISTRIBUTION_VERSION,
    ROOM_TYPE_GROUP,
)
from ..models import (
    GroupEncryptionEpoch,
    GroupProfile,
    GroupSenderKey,
    GroupSenderKeyDistribution,
)
from .audit import record_group_audit_event


class GroupSenderKeyDistributionServiceError(Exception):
    """Base exception for group sender-key distribution operations."""


class GroupSenderKeyDistributionValidationError(
    GroupSenderKeyDistributionServiceError
):
    """Raised when distribution input is invalid."""


class GroupSenderKeyDistributionNotFoundError(
    GroupSenderKeyDistributionServiceError
):
    """Raised when group, sender key, device, or distribution is missing."""


class GroupSenderKeyDistributionPermissionError(
    GroupSenderKeyDistributionServiceError
):
    """Raised when caller cannot perform a distribution operation."""


class GroupSenderKeyDistributionConflictError(
    GroupSenderKeyDistributionServiceError
):
    """Raised when distribution state conflicts."""


@dataclass(frozen=True, slots=True)
class DistributionAccessContext:
    profile: GroupProfile
    room: Room
    actor_membership: RoomMember


@dataclass(frozen=True, slots=True)
class DeviceRosterItem:
    user_id: str
    membership_version: int
    device_id: UUID
    device_name: str
    platform: str
    registration_id: int
    identity_key_public: str
    signed_prekey_id: int
    signed_prekey_public: str
    signed_prekey_signature: str
    key_algorithm: str
    key_bundle_version: int
    epoch_number: int
    membership_snapshot_hash: str


@dataclass(frozen=True, slots=True)
class DistributionStoreResult:
    stored_distributions: list[GroupSenderKeyDistribution]
    created_count: int
    existing_count: int
    missing_required_device_ids: list[str]


@dataclass(frozen=True, slots=True)
class PendingDistributionResult:
    sender_key: GroupSenderKey
    required_device_count: int
    covered_device_count: int
    pending_devices: list[DeviceRosterItem]
    is_send_ready: bool


def _normalize_user_id(
    value: Any,
    *,
    field_name: str,
) -> str:
    user_id = str(value).strip()

    if not user_id:
        raise GroupSenderKeyDistributionValidationError(
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
        raise GroupSenderKeyDistributionValidationError(
            f"{field_name} must be a valid UUID."
        ) from error


def _run_distribution_validation(
    distribution: GroupSenderKeyDistribution,
) -> None:
    try:
        distribution.full_clean()
    except DjangoValidationError as error:
        raise GroupSenderKeyDistributionValidationError(
            error.message_dict
            if hasattr(error, "message_dict")
            else str(error)
        ) from error


def _get_context_for_read(
    *,
    group_id: Any,
    actor_user_id: Any,
) -> DistributionAccessContext:
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
        raise GroupSenderKeyDistributionNotFoundError(
            "Group was not found."
        )

    actor_membership = (
        RoomMember.objects.filter(
            room=profile.room,
            user_id=actor_user_id,
            is_active=True,
        )
        .first()
    )

    if actor_membership is None:
        raise GroupSenderKeyDistributionNotFoundError(
            "Group was not found."
        )

    return DistributionAccessContext(
        profile=profile,
        room=profile.room,
        actor_membership=actor_membership,
    )


def _get_context_for_update(
    *,
    group_id: Any,
    actor_user_id: Any,
) -> DistributionAccessContext:
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
        raise GroupSenderKeyDistributionNotFoundError(
            "Group was not found."
        )

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
        raise GroupSenderKeyDistributionNotFoundError(
            "Group was not found."
        )

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
        raise GroupSenderKeyDistributionNotFoundError(
            "Group was not found."
        )

    return DistributionAccessContext(
        profile=profile,
        room=room,
        actor_membership=actor_membership,
    )


def _get_epoch_for_group(
    *,
    room: Room,
    epoch_number: int,
) -> GroupEncryptionEpoch:
    epoch = (
        GroupEncryptionEpoch.objects.filter(
            group_room=room,
            epoch_number=epoch_number,
        )
        .first()
    )

    if epoch is None:
        raise GroupSenderKeyDistributionNotFoundError(
            "Group epoch was not found."
        )

    if epoch.status != GroupEncryptionEpoch.Status.ACTIVE:
        raise GroupSenderKeyDistributionConflictError(
            "Sender-key distribution must target the active epoch."
        )

    return epoch


def _active_member_map(
    *,
    room: Room,
) -> dict[str, RoomMember]:
    return {
        member.user_id: member
        for member in RoomMember.objects.filter(
            room=room,
            is_active=True,
        )
    }


def list_group_device_roster(
    *,
    authenticated_user_id: Any,
    group_id: Any,
    epoch_number: int,
) -> list[DeviceRosterItem]:
    context = _get_context_for_read(
        group_id=group_id,
        actor_user_id=authenticated_user_id,
    )

    epoch = _get_epoch_for_group(
        room=context.room,
        epoch_number=int(epoch_number),
    )

    active_members = _active_member_map(room=context.room)
    active_user_ids = list(active_members.keys())

    devices = list(
        Device.objects.filter(
            user_id__in=active_user_ids,
            is_active=True,
        ).order_by(
            "user_id",
            "created_at",
            "id",
        )
    )

    roster = []

    for device in devices:
        membership = active_members[device.user_id]

        roster.append(
            DeviceRosterItem(
                user_id=device.user_id,
                membership_version=membership.membership_version,
                device_id=device.id,
                device_name=device.device_name,
                platform=device.platform,
                registration_id=device.registration_id,
                identity_key_public=device.identity_key_public,
                signed_prekey_id=device.signed_prekey_id,
                signed_prekey_public=device.signed_prekey_public,
                signed_prekey_signature=device.signed_prekey_signature,
                key_algorithm=device.key_algorithm,
                key_bundle_version=device.key_bundle_version,
                epoch_number=epoch.epoch_number,
                membership_snapshot_hash=epoch.membership_snapshot_hash,
            )
        )

    return roster


def _required_distribution_devices(
    *,
    sender_key: GroupSenderKey,
) -> dict[UUID, DeviceRosterItem]:
    active_members = _active_member_map(room=sender_key.group_room)
    active_user_ids = list(active_members.keys())

    devices = list(
        Device.objects.filter(
            user_id__in=active_user_ids,
            is_active=True,
        ).order_by(
            "user_id",
            "created_at",
            "id",
        )
    )

    required = {}

    for device in devices:
        if device.id == sender_key.sender_device_id:
            continue

        membership = active_members[device.user_id]

        required[device.id] = DeviceRosterItem(
            user_id=device.user_id,
            membership_version=membership.membership_version,
            device_id=device.id,
            device_name=device.device_name,
            platform=device.platform,
            registration_id=device.registration_id,
            identity_key_public=device.identity_key_public,
            signed_prekey_id=device.signed_prekey_id,
            signed_prekey_public=device.signed_prekey_public,
            signed_prekey_signature=device.signed_prekey_signature,
            key_algorithm=device.key_algorithm,
            key_bundle_version=device.key_bundle_version,
            epoch_number=sender_key.epoch.epoch_number,
            membership_snapshot_hash=(
                sender_key.epoch.membership_snapshot_hash
            ),
        )

    return required


def _sender_key_matches_group_and_epoch(
    *,
    sender_key: GroupSenderKey,
    room: Room,
    epoch_number: int,
) -> None:
    if sender_key.group_room_id != room.id:
        raise GroupSenderKeyDistributionNotFoundError(
            "Sender key was not found."
        )

    if not sender_key.is_active:
        raise GroupSenderKeyDistributionConflictError(
            "Sender key is not active."
        )

    if sender_key.epoch.epoch_number != int(epoch_number):
        raise GroupSenderKeyDistributionConflictError(
            "Sender key does not belong to the requested epoch."
        )

    if sender_key.epoch.status != GroupEncryptionEpoch.Status.ACTIVE:
        raise GroupSenderKeyDistributionConflictError(
            "Sender key epoch is no longer active."
        )


def _distribution_matches_payload(
    *,
    existing: GroupSenderKeyDistribution,
    recipient_user_id: str,
    encrypted_sender_key: str,
    distribution_metadata: dict,
    distribution_version: int,
) -> bool:
    return (
        existing.recipient_user_id == recipient_user_id
        and existing.encrypted_sender_key == encrypted_sender_key
        and existing.distribution_metadata == distribution_metadata
        and existing.distribution_version == distribution_version
    )


@transaction.atomic
def store_sender_key_distributions(
    *,
    authenticated_user_id: Any,
    group_id: Any,
    sender_key_id: Any,
    epoch_number: int,
    distributions: list[dict[str, Any]],
) -> DistributionStoreResult:
    actor_user_id = _normalize_user_id(
        authenticated_user_id,
        field_name="authenticated_user_id",
    )

    context = _get_context_for_update(
        group_id=group_id,
        actor_user_id=actor_user_id,
    )

    public_sender_key_uuid = _normalize_uuid(
        sender_key_id,
        field_name="sender_key_id",
    )

    sender_key = (
        GroupSenderKey.objects.select_for_update()
        .select_related(
            "epoch",
            "sender_device",
            "group_room",
        )
        .filter(
            sender_key_id=public_sender_key_uuid,
        )
        .first()
    )

    if sender_key is None:
        raise GroupSenderKeyDistributionNotFoundError(
            "Sender key was not found."
        )

    _sender_key_matches_group_and_epoch(
        sender_key=sender_key,
        room=context.room,
        epoch_number=int(epoch_number),
    )

    if sender_key.sender_user_id != actor_user_id:
        raise GroupSenderKeyDistributionPermissionError(
            "Only the sender-key owner can distribute this sender key."
        )

    required_devices = _required_distribution_devices(
        sender_key=sender_key,
    )
    required_device_ids = set(required_devices.keys())

    supplied_device_ids = {
        _normalize_uuid(
            distribution["recipient_device_id"],
            field_name="recipient_device_id",
        )
        for distribution in distributions
    }

    unexpected_device_ids = sorted(
        str(device_id)
        for device_id in supplied_device_ids - required_device_ids
    )

    if unexpected_device_ids:
        raise GroupSenderKeyDistributionValidationError(
            {
                "recipient_device_ids": (
                    "Unexpected or unauthorized recipient devices: "
                    f"{unexpected_device_ids}"
                )
            }
        )

    missing_required_device_ids = sorted(
        str(device_id)
        for device_id in required_device_ids - supplied_device_ids
    )

    recipient_devices = {
        device.id: device
        for device in Device.objects.select_for_update().filter(
            id__in=supplied_device_ids,
            is_active=True,
        )
    }

    stored_distributions = []
    created_count = 0
    existing_count = 0

    for distribution_data in distributions:
        recipient_device_id = _normalize_uuid(
            distribution_data["recipient_device_id"],
            field_name="recipient_device_id",
        )

        recipient_device = recipient_devices.get(recipient_device_id)

        if recipient_device is None:
            raise GroupSenderKeyDistributionNotFoundError(
                "Recipient device was not found."
            )

        roster_item = required_devices.get(recipient_device_id)

        if roster_item is None:
            raise GroupSenderKeyDistributionValidationError(
                "Recipient device is not required for this sender key."
            )

        recipient_user_id = _normalize_user_id(
            distribution_data["recipient_user_id"],
            field_name="recipient_user_id",
        )

        if recipient_user_id != roster_item.user_id:
            raise GroupSenderKeyDistributionValidationError(
                "recipient_user_id does not match recipient device owner."
            )

        encrypted_sender_key = str(
            distribution_data["encrypted_sender_key"]
        ).strip()
        distribution_metadata = distribution_data[
            "distribution_metadata"
        ]
        distribution_version = int(
            distribution_data.get(
                "distribution_version",
                GROUP_SENDER_KEY_DISTRIBUTION_VERSION,
            )
        )

        if not encrypted_sender_key:
            raise GroupSenderKeyDistributionValidationError(
                "encrypted_sender_key is required."
            )

        if not isinstance(distribution_metadata, dict):
            raise GroupSenderKeyDistributionValidationError(
                "distribution_metadata must be a JSON object."
            )

        existing = (
            GroupSenderKeyDistribution.objects.select_for_update()
            .filter(
                sender_key=sender_key,
                recipient_device=recipient_device,
            )
            .first()
        )

        if existing is not None:
            if not _distribution_matches_payload(
                existing=existing,
                recipient_user_id=recipient_user_id,
                encrypted_sender_key=encrypted_sender_key,
                distribution_metadata=distribution_metadata,
                distribution_version=distribution_version,
            ):
                raise GroupSenderKeyDistributionConflictError(
                    "Distribution already exists with different data."
                )

            stored_distributions.append(existing)
            existing_count += 1
            continue

        distribution = GroupSenderKeyDistribution(
            sender_key=sender_key,
            recipient_user_id=recipient_user_id,
            recipient_device=recipient_device,
            encrypted_sender_key=encrypted_sender_key,
            distribution_metadata=distribution_metadata,
            distribution_version=distribution_version,
            status=GROUP_SENDER_KEY_DISTRIBUTION_STATUS_STORED,
            acknowledged_at=None,
        )

        _run_distribution_validation(distribution)

        try:
            distribution.save(force_insert=True)
        except IntegrityError as error:
            raise GroupSenderKeyDistributionConflictError(
                "Could not store sender-key distribution because of "
                "a conflict."
            ) from error

        stored_distributions.append(distribution)
        created_count += 1

    record_group_audit_event(
        room=context.room,
        actor_user_id=actor_user_id,
        event_type=GROUP_AUDIT_SENDER_KEY_DISTRIBUTED,
        target_user_id=sender_key.sender_user_id,
        metadata={
            "sender_key_id": str(sender_key.sender_key_id),
            "epoch_number": sender_key.epoch.epoch_number,
            "created_count": created_count,
            "existing_count": existing_count,
            "missing_required_device_count": len(
                missing_required_device_ids
            ),
        },
    )

    return DistributionStoreResult(
        stored_distributions=stored_distributions,
        created_count=created_count,
        existing_count=existing_count,
        missing_required_device_ids=missing_required_device_ids,
    )


def get_pending_sender_key_distributions(
    *,
    authenticated_user_id: Any,
    group_id: Any,
    sender_key_id: Any,
) -> PendingDistributionResult:
    actor_user_id = _normalize_user_id(
        authenticated_user_id,
        field_name="authenticated_user_id",
    )

    context = _get_context_for_read(
        group_id=group_id,
        actor_user_id=actor_user_id,
    )

    public_sender_key_uuid = _normalize_uuid(
        sender_key_id,
        field_name="sender_key_id",
    )

    sender_key = (
        GroupSenderKey.objects.select_related(
            "epoch",
            "sender_device",
            "group_room",
        )
        .filter(
            group_room=context.room,
            sender_key_id=public_sender_key_uuid,
        )
        .first()
    )

    if sender_key is None:
        raise GroupSenderKeyDistributionNotFoundError(
            "Sender key was not found."
        )

    if sender_key.sender_user_id != actor_user_id:
        raise GroupSenderKeyDistributionPermissionError(
            "Only the sender-key owner can inspect pending coverage."
        )

    required_devices = _required_distribution_devices(
        sender_key=sender_key,
    )

    stored_device_ids = set(
        GroupSenderKeyDistribution.objects.filter(
            sender_key=sender_key,
            recipient_device_id__in=required_devices.keys(),
            status__in=[
                GROUP_SENDER_KEY_DISTRIBUTION_STATUS_STORED,
                GROUP_SENDER_KEY_DISTRIBUTION_STATUS_ACKNOWLEDGED,
            ],
        ).values_list(
            "recipient_device_id",
            flat=True,
        )
    )

    pending_device_ids = sorted(
        required_devices.keys() - stored_device_ids,
        key=lambda value: str(value),
    )

    pending_devices = [
        required_devices[device_id]
        for device_id in pending_device_ids
    ]

    return PendingDistributionResult(
        sender_key=sender_key,
        required_device_count=len(required_devices),
        covered_device_count=len(stored_device_ids),
        pending_devices=pending_devices,
        is_send_ready=len(pending_devices) == 0,
    )


def list_sender_key_distribution_inbox(
    *,
    authenticated_user_id: Any,
    group_id: Any,
    device_id: Any,
) -> list[GroupSenderKeyDistribution]:
    actor_user_id = _normalize_user_id(
        authenticated_user_id,
        field_name="authenticated_user_id",
    )

    context = _get_context_for_read(
        group_id=group_id,
        actor_user_id=actor_user_id,
    )

    device_uuid = _normalize_uuid(
        device_id,
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
        raise GroupSenderKeyDistributionNotFoundError(
            "Recipient device was not found."
        )

    if device.user_id != actor_user_id:
        raise GroupSenderKeyDistributionPermissionError(
            "Recipient device does not belong to authenticated user."
        )

    return list(
        GroupSenderKeyDistribution.objects.select_related(
            "sender_key",
            "sender_key__epoch",
            "sender_key__sender_device",
        )
        .filter(
            sender_key__group_room=context.room,
            recipient_device=device,
            status__in=[
                GROUP_SENDER_KEY_DISTRIBUTION_STATUS_STORED,
                GROUP_SENDER_KEY_DISTRIBUTION_STATUS_ACKNOWLEDGED,
            ],
        )
        .order_by(
            "-created_at",
            "-id",
        )
    )


@transaction.atomic
def acknowledge_sender_key_distributions(
    *,
    authenticated_user_id: Any,
    group_id: Any,
    device_id: Any,
    distribution_ids: list[Any],
) -> list[GroupSenderKeyDistribution]:
    actor_user_id = _normalize_user_id(
        authenticated_user_id,
        field_name="authenticated_user_id",
    )

    context = _get_context_for_update(
        group_id=group_id,
        actor_user_id=actor_user_id,
    )

    device_uuid = _normalize_uuid(
        device_id,
        field_name="device_id",
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
        raise GroupSenderKeyDistributionNotFoundError(
            "Recipient device was not found."
        )

    if device.user_id != actor_user_id:
        raise GroupSenderKeyDistributionPermissionError(
            "Recipient device does not belong to authenticated user."
        )

    normalized_ids = [
        _normalize_uuid(
            value,
            field_name="distribution_id",
        )
        for value in distribution_ids
    ]

    if len(normalized_ids) != len(set(normalized_ids)):
        raise GroupSenderKeyDistributionValidationError(
            "Duplicate distribution IDs are not allowed."
        )

    distributions = list(
        GroupSenderKeyDistribution.objects.select_for_update()
        .select_related(
            "sender_key",
            "sender_key__epoch",
            "sender_key__group_room",
            "recipient_device",
        )
        .filter(
            id__in=normalized_ids,
            sender_key__group_room=context.room,
            recipient_device=device,
        )
    )

    found_ids = {
        distribution.id
        for distribution in distributions
    }

    missing_ids = sorted(
        str(value)
        for value in set(normalized_ids) - found_ids
    )

    if missing_ids:
        raise GroupSenderKeyDistributionNotFoundError(
            f"Distributions were not found: {missing_ids}"
        )

    now = timezone.now()
    changed_count = 0

    for distribution in distributions:
        if distribution.status == GROUP_SENDER_KEY_DISTRIBUTION_STATUS_ACKNOWLEDGED:
            continue

        distribution.status = GROUP_SENDER_KEY_DISTRIBUTION_STATUS_ACKNOWLEDGED
        distribution.acknowledged_at = now
        _run_distribution_validation(distribution)
        distribution.save(
            update_fields=[
                "status",
                "acknowledged_at",
            ]
        )
        changed_count += 1

    record_group_audit_event(
        room=context.room,
        actor_user_id=actor_user_id,
        event_type=GROUP_AUDIT_SENDER_KEY_DISTRIBUTION_ACKED,
        target_user_id=actor_user_id,
        metadata={
            "device_id": str(device.id),
            "distribution_count": len(distributions),
            "changed_count": changed_count,
        },
    )

    return distributions
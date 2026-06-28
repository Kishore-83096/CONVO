from dataclasses import dataclass
from typing import Any
from uuid import UUID
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from apps.group_chat.constants import (
    GROUP_SENDER_KEY_DISTRIBUTION_STATUS_ACKNOWLEDGED,
    GROUP_SENDER_KEY_DISTRIBUTION_STATUS_STORED,
)
from .event_validation import (
    EncryptedMessageEventValidationError,
    validate_encrypted_message_event,
)
from apps.group_chat.models import (
    GroupEncryptionEpoch,
    GroupProfile,
    GroupSenderKey,
    GroupSenderKeyDistribution,
)
from apps.rooms.models import Room, RoomMember
from apps.e2ee_devices.models import Device, RecoveryBundle
from .models import GroupMessageEncryption, Message, MessageRecoveryEnvelope

class GroupMessageServiceError(Exception):
    """Base exception for group message operations."""


class GroupMessageValidationError(GroupMessageServiceError):
    """Raised when group-message input is invalid."""


class GroupMessageNotFoundError(GroupMessageServiceError):
    """Raised when group, epoch, key, device or reply target is missing."""


class GroupMessagePermissionError(GroupMessageServiceError):
    """Raised when caller cannot send to the group."""


class GroupMessageConflictError(GroupMessageServiceError):
    """Raised when idempotency or iteration state conflicts."""


@dataclass(frozen=True, slots=True)
class GroupMessageSendResult:
    encryption: GroupMessageEncryption
    message_created: bool


@dataclass(frozen=True, slots=True)
class GroupSendContext:
    profile: GroupProfile
    room: Room
    membership: RoomMember


def _normalize_user_id(
    value: Any,
    *,
    field_name: str,
) -> str:
    user_id = str(value).strip()

    if not user_id:
        raise GroupMessageValidationError(
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
        raise GroupMessageValidationError(
            f"{field_name} must be a valid UUID."
        ) from error


def _run_group_encryption_validation(
    encryption: GroupMessageEncryption,
) -> None:
    try:
        encryption.full_clean()
    except DjangoValidationError as error:
        raise GroupMessageValidationError(
            error.message_dict
            if hasattr(error, "message_dict")
            else str(error)
        ) from error


def _get_group_context_for_send(
    *,
    group_id: Any,
    actor_user_id: str,
) -> GroupSendContext:
    group_uuid = _normalize_uuid(
        group_id,
        field_name="group_id",
    )

    profile = (
        GroupProfile.objects.select_for_update()
        .select_related("room")
        .filter(
            room_id=group_uuid,
            room__room_type=Room.RoomType.GROUP,
            room__is_active=True,
        )
        .first()
    )

    if profile is None:
        raise GroupMessageNotFoundError("Group was not found.")

    room = (
        Room.objects.select_for_update()
        .filter(
            id=profile.room_id,
            room_type=Room.RoomType.GROUP,
            is_active=True,
        )
        .first()
    )

    if room is None:
        raise GroupMessageNotFoundError("Group was not found.")

    membership = (
        RoomMember.objects.select_for_update()
        .filter(
            room=room,
            user_id=actor_user_id,
            is_active=True,
        )
        .first()
    )

    if membership is None:
        raise GroupMessageNotFoundError("Group was not found.")

    if (
        profile.only_admins_can_send
        and membership.role == RoomMember.Role.MEMBER
    ):
        raise GroupMessagePermissionError(
            "Only group admins can send messages in this group."
        )

    return GroupSendContext(
        profile=profile,
        room=room,
        membership=membership,
    )


def _get_active_owned_device(
    *,
    sender_device_id: Any,
    actor_user_id: str,
) -> Device:
    device_uuid = _normalize_uuid(
        sender_device_id,
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
        raise GroupMessageNotFoundError("Sender device was not found.")

    if device.user_id != actor_user_id:
        raise GroupMessagePermissionError(
            "Sender device does not belong to the authenticated user."
        )

    return device


def _get_current_epoch(
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
        raise GroupMessageNotFoundError("Group epoch was not found.")

    if epoch.status != GroupEncryptionEpoch.Status.ACTIVE:
        raise GroupMessageConflictError(
            "Group epoch is no longer active."
        )

    return epoch


def _get_active_sender_key(
    *,
    room: Room,
    epoch: GroupEncryptionEpoch,
    sender_key_id: Any,
    actor_user_id: str,
    device: Device,
) -> GroupSenderKey:
    sender_key_uuid = _normalize_uuid(
        sender_key_id,
        field_name="sender_key_id",
    )

    sender_key = (
        GroupSenderKey.objects.select_for_update()
        .select_related(
            "epoch",
            "sender_device",
        )
        .filter(
            group_room=room,
            epoch=epoch,
            sender_key_id=sender_key_uuid,
            sender_user_id=actor_user_id,
            sender_device=device,
            is_active=True,
        )
        .first()
    )

    if sender_key is None:
        raise GroupMessageNotFoundError("Sender key was not found.")

    if sender_key.epoch.status != GroupEncryptionEpoch.Status.ACTIVE:
        raise GroupMessageConflictError(
            "Sender key epoch is no longer active."
        )

    return sender_key


def _required_distribution_device_ids(
    *,
    room: Room,
    sender_device: Device,
) -> set[UUID]:
    active_user_ids = list(
        RoomMember.objects.filter(
            room=room,
            is_active=True,
        ).values_list(
            "user_id",
            flat=True,
        )
    )

    device_ids = set(
        Device.objects.filter(
            user_id__in=active_user_ids,
            is_active=True,
        ).values_list(
            "id",
            flat=True,
        )
    )

    device_ids.discard(sender_device.id)

    return device_ids


def _ensure_distribution_coverage(
    *,
    room: Room,
    sender_key: GroupSenderKey,
    sender_device: Device,
) -> None:
    required_device_ids = _required_distribution_device_ids(
        room=room,
        sender_device=sender_device,
    )

    covered_device_ids = set(
        GroupSenderKeyDistribution.objects.filter(
            sender_key=sender_key,
            recipient_device_id__in=required_device_ids,
            status__in=[
                GROUP_SENDER_KEY_DISTRIBUTION_STATUS_STORED,
                GROUP_SENDER_KEY_DISTRIBUTION_STATUS_ACKNOWLEDGED,
            ],
        ).values_list(
            "recipient_device_id",
            flat=True,
        )
    )

    missing_device_ids = sorted(
        str(device_id)
        for device_id in required_device_ids - covered_device_ids
    )

    if missing_device_ids:
        raise GroupMessageConflictError(
            "Sender key is not distributed to all required devices: "
            f"{missing_device_ids}"
        )


def _get_reply_target(
    *,
    reply_to_message_id: Any,
    room: Room,
) -> Message | None:
    if reply_to_message_id is None:
        return None

    reply_uuid = _normalize_uuid(
        reply_to_message_id,
        field_name="reply_to_message_id",
    )

    reply_to = Message.objects.filter(
        id=reply_uuid,
        room=room,
    ).first()

    if reply_to is None:
        raise GroupMessageValidationError(
            "Reply target must be an existing message in the same group."
        )

    return reply_to


def _existing_message_matches_request(
    *,
    message: Message,
    group_encryption: GroupMessageEncryption | None,
    room: Room,
    sender_device: Device,
    epoch: GroupEncryptionEpoch,
    sender_key: GroupSenderKey,
    chain_iteration: int,
    message_type: str,
    encrypted_payload: str,
    encryption_metadata: dict,
    signature: str,
    reply_to: Message | None,
    client_sent_at,
) -> bool:
    if group_encryption is None:
        return False

    return (
        message.room_id == room.id
        and message.sender_device_id == str(sender_device.id)
        and message.message_type == message_type
        and message.encrypted_payload == encrypted_payload
        and message.encryption_metadata == encryption_metadata
        and message.reply_to_id == (reply_to.id if reply_to else None)
        and message.client_sent_at == client_sent_at
        and group_encryption.epoch_id == epoch.id
        and group_encryption.sender_key_id == sender_key.id
        and group_encryption.chain_iteration == chain_iteration
        and group_encryption.signature == signature
        and group_encryption.encryption_metadata == encryption_metadata
    )


def _get_existing_message_for_idempotency(
    *,
    actor_user_id: str,
    client_message_id: Any,
) -> Message | None:
    client_message_uuid = _normalize_uuid(
        client_message_id,
        field_name="client_message_id",
    )

    return (
        Message.objects.select_for_update()
        .filter(
            sender_user_id=actor_user_id,
            client_message_id=client_message_uuid,
        )
        .first()
    )

def _expected_recovery_bundles_for_group(
    *,
    room: Room,
) -> dict[str, RecoveryBundle]:
    active_user_ids = list(
        RoomMember.objects.filter(
            room=room,
            is_active=True,
        ).values_list(
            "user_id",
            flat=True,
        )
    )

    bundles = RecoveryBundle.objects.filter(
        user_id__in=active_user_ids,
        is_active=True,
    )

    return {
        bundle.user_id: bundle
        for bundle in bundles
    }


def _normalize_recovery_envelopes(
    recovery_envelopes,
) -> list[dict]:
    if recovery_envelopes is None:
        return []

    if not isinstance(recovery_envelopes, list):
        raise GroupMessageValidationError(
            "recovery_envelopes must be a list."
        )

    normalized = []

    for envelope in recovery_envelopes:
        if not isinstance(envelope, dict):
            raise GroupMessageValidationError(
                "Each recovery envelope must be a JSON object."
            )

        normalized.append(
            {
                "recovery_owner_user_id": str(
                    envelope.get("recovery_owner_user_id", "")
                ).strip(),
                "recovery_key_version": int(
                    envelope.get("recovery_key_version", 0)
                ),
                "wrapped_message_key": str(
                    envelope.get("wrapped_message_key", "")
                ).strip(),
                "key_wrap_metadata": envelope.get("key_wrap_metadata", {}),
                "envelope_version": int(
                    envelope.get("envelope_version", 0)
                ),
            }
        )

    return normalized


def _validate_recovery_envelopes(
    *,
    room: Room,
    recovery_envelopes: list[dict],
) -> list[dict]:
    expected_bundles = _expected_recovery_bundles_for_group(
        room=room,
    )

    expected_owner_ids = set(expected_bundles.keys())

    supplied_by_owner = {}

    for envelope in recovery_envelopes:
        owner_user_id = envelope["recovery_owner_user_id"]

        if not owner_user_id:
            raise GroupMessageValidationError(
                "recovery_owner_user_id is required."
            )

        if owner_user_id in supplied_by_owner:
            raise GroupMessageValidationError(
                "Only one recovery envelope is allowed per recovery owner."
            )

        supplied_by_owner[owner_user_id] = envelope

    supplied_owner_ids = set(supplied_by_owner.keys())

    missing_owner_ids = sorted(expected_owner_ids - supplied_owner_ids)
    unexpected_owner_ids = sorted(supplied_owner_ids - expected_owner_ids)

    if missing_owner_ids:
        raise GroupMessageValidationError(
            "Missing recovery envelopes for owners: "
            f"{missing_owner_ids}"
        )

    if unexpected_owner_ids:
        raise GroupMessageValidationError(
            "Unexpected recovery envelope owners: "
            f"{unexpected_owner_ids}"
        )

    for owner_user_id, envelope in supplied_by_owner.items():
        bundle = expected_bundles[owner_user_id]

        if envelope["recovery_key_version"] != bundle.recovery_version:
            raise GroupMessageConflictError(
                "Recovery envelope version is stale for owner "
                f"{owner_user_id}."
            )

        if envelope["envelope_version"] < 1:
            raise GroupMessageValidationError(
                "Recovery envelope version must be at least 1."
            )

        if not envelope["wrapped_message_key"]:
            raise GroupMessageValidationError(
                "wrapped_message_key is required."
            )

        if not isinstance(envelope["key_wrap_metadata"], dict):
            raise GroupMessageValidationError(
                "key_wrap_metadata must be a JSON object."
            )

    return [
        supplied_by_owner[owner_user_id]
        for owner_user_id in sorted(supplied_by_owner.keys())
    ]


def _existing_recovery_envelopes_match_request(
    *,
    message: Message,
    recovery_envelopes: list[dict],
) -> bool:
    existing = list(
        MessageRecoveryEnvelope.objects.filter(
            message=message,
        ).order_by("recovery_owner_user_id")
    )

    if len(existing) != len(recovery_envelopes):
        return False

    for existing_envelope, supplied in zip(existing, recovery_envelopes):
        if (
            existing_envelope.recovery_owner_user_id
            != supplied["recovery_owner_user_id"]
        ):
            return False

        if (
            existing_envelope.recovery_key_version
            != supplied["recovery_key_version"]
        ):
            return False

        if (
            existing_envelope.wrapped_message_key
            != supplied["wrapped_message_key"]
        ):
            return False

        if (
            existing_envelope.key_wrap_metadata
            != supplied["key_wrap_metadata"]
        ):
            return False

        if (
            existing_envelope.envelope_version
            != supplied["envelope_version"]
        ):
            return False

    return True


def _create_message_recovery_envelopes(
    *,
    message: Message,
    recovery_envelopes: list[dict],
) -> None:
    envelope_models = []

    for envelope in recovery_envelopes:
        envelope_model = MessageRecoveryEnvelope(
            message=message,
            recovery_owner_user_id=envelope["recovery_owner_user_id"],
            recovery_key_version=envelope["recovery_key_version"],
            wrapped_message_key=envelope["wrapped_message_key"],
            key_wrap_metadata=envelope["key_wrap_metadata"],
            envelope_version=envelope["envelope_version"],
        )

        try:
            envelope_model.full_clean()
        except DjangoValidationError as error:
            raise GroupMessageValidationError(
                error.message_dict
                if hasattr(error, "message_dict")
                else str(error)
            ) from error

        envelope_models.append(envelope_model)

    try:
        MessageRecoveryEnvelope.objects.bulk_create(
            envelope_models,
        )
    except IntegrityError as error:
        raise GroupMessageConflictError(
            "Could not create recovery envelopes because of a conflict."
        ) from error
@transaction.atomic
def send_encrypted_group_message(
    *,
    authenticated_user_id: Any,
    group_id: Any,
    sender_device_id: Any,
    client_message_id: Any,
    epoch_number: int,
    sender_key_id: Any,
    chain_iteration: int,
    message_type: str,
    encrypted_payload: str,
    encryption_metadata: dict,
    signature: str,
    reply_to_message_id: Any = None,
    client_sent_at=None,
    recovery_envelopes=None,
) -> GroupMessageSendResult:
    actor_user_id = _normalize_user_id(
        authenticated_user_id,
        field_name="authenticated_user_id",
    )
    message_type = str(message_type).strip()
    encrypted_payload = str(encrypted_payload).strip()
    signature = str(signature).strip()

    if not message_type:
        raise GroupMessageValidationError("message_type is required.")

    if not encrypted_payload:
        raise GroupMessageValidationError("encrypted_payload is required.")

    if not signature:
        raise GroupMessageValidationError("signature is required.")

    if not isinstance(encryption_metadata, dict):
        raise GroupMessageValidationError(
            "encryption_metadata must be a JSON object."
        )

    context = _get_group_context_for_send(
        group_id=group_id,
        actor_user_id=actor_user_id,
    )

    sender_device = _get_active_owned_device(
        sender_device_id=sender_device_id,
        actor_user_id=actor_user_id,
    )

    epoch = _get_current_epoch(
        room=context.room,
        epoch_number=int(epoch_number),
    )

    sender_key = _get_active_sender_key(
        room=context.room,
        epoch=epoch,
        sender_key_id=sender_key_id,
        actor_user_id=actor_user_id,
        device=sender_device,
    )

    _ensure_distribution_coverage(
        room=context.room,
        sender_key=sender_key,
        sender_device=sender_device,
    )

    reply_to = _get_reply_target(
        reply_to_message_id=reply_to_message_id,
        room=context.room,
    )
    try:
        validate_encrypted_message_event(
            room=context.room,
            actor_user_id=actor_user_id,
            message_type=message_type,
            encryption_metadata=encryption_metadata,
        )
    except EncryptedMessageEventValidationError as error:
        raise GroupMessageValidationError(str(error)) from error
    normalized_recovery_envelopes = _normalize_recovery_envelopes(
        recovery_envelopes,
    )

    validated_recovery_envelopes = _validate_recovery_envelopes(
        room=context.room,
        recovery_envelopes=normalized_recovery_envelopes,
    )

    existing_message = _get_existing_message_for_idempotency(
        actor_user_id=actor_user_id,
        client_message_id=client_message_id,
    )

    if existing_message is not None:
        existing_encryption = getattr(
            existing_message,
            "group_encryption",
            None,
        )
        if (
            _existing_message_matches_request(
                message=existing_message,
                group_encryption=existing_encryption,
                room=context.room,
                sender_device=sender_device,
                epoch=epoch,
                sender_key=sender_key,
                chain_iteration=int(chain_iteration),
                message_type=message_type,
                encrypted_payload=encrypted_payload,
                encryption_metadata=encryption_metadata,
                signature=signature,
                reply_to=reply_to,
                client_sent_at=client_sent_at,
            )
            and _existing_recovery_envelopes_match_request(
                message=existing_message,
                recovery_envelopes=validated_recovery_envelopes,
            )
        ):
            return GroupMessageSendResult(
                encryption=existing_encryption,
                message_created=False,
            )

        raise GroupMessageConflictError(
            "client_message_id already exists with different message data."
        )

    if int(chain_iteration) <= sender_key.highest_accepted_iteration:
        raise GroupMessageConflictError(
            "chain_iteration must be greater than the sender key's highest "
            "accepted iteration."
        )
    message = Message(
        room=context.room,
        sender_user_id=actor_user_id,
        sender_device_id=str(sender_device.id),
        client_message_id=client_message_id,
        message_type=message_type,
        encrypted_payload=encrypted_payload,
        encryption_metadata=encryption_metadata,
        encryption_version=1,
        reply_to=reply_to,
        client_sent_at=client_sent_at,
    )

    try:
        message.full_clean()
        message.save(force_insert=True)
    except DjangoValidationError as error:
        raise GroupMessageValidationError(
            error.message_dict
            if hasattr(error, "message_dict")
            else str(error)
        ) from error
    except IntegrityError as error:
        raise GroupMessageConflictError(
            "Could not create group message because of a conflict."
        ) from error

    group_encryption = GroupMessageEncryption(
        message=message,
        group_room=context.room,
        epoch=epoch,
        sender_key=sender_key,
        chain_iteration=int(chain_iteration),
        signature=signature,
        encryption_metadata=encryption_metadata,
    )

    _run_group_encryption_validation(group_encryption)

    try:
        group_encryption.save(force_insert=True)
        _create_message_recovery_envelopes(
            message=message,
            recovery_envelopes=validated_recovery_envelopes,
        )
    except IntegrityError as error:
        raise GroupMessageConflictError(
            "Could not create group encryption metadata because of a conflict."
        ) from error

    sender_key.highest_accepted_iteration = int(chain_iteration)
    sender_key.save(
        update_fields=[
            "highest_accepted_iteration",
        ]
    )

    context.room.save(
        update_fields=[
            "updated_at",
        ]
    )

    return GroupMessageSendResult(
        encryption=group_encryption,
        message_created=True,
    )
import hashlib
from dataclasses import dataclass
from typing import Any
from uuid import UUID
from apps.group_chat.models import GroupEncryptionEpoch
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from .policy_services import get_delivery_policy_snapshot
from apps.e2ee_devices.models import Device
from apps.rooms.models import Room, RoomMember

from .models import (
    DirectMessageReceiptDecision,
    Message,
    MessageKeyEnvelope,
)


from django.db.models import Prefetch, QuerySet

from apps.group_chat.models import GroupProfile


class DirectMessageServiceError(Exception):
    """Base exception for direct-message operations."""


class DirectMessageValidationError(DirectMessageServiceError):
    """Raised when message input is invalid."""


class DirectRoomUnavailableError(DirectMessageServiceError):
    """Raised when an existing direct room cannot be used."""


class IdempotencyConflictError(DirectMessageServiceError):
    """
    Raised when a client_message_id is reused with different content.
    """


@dataclass(frozen=True, slots=True)
class DirectMessageResult:
    room: Room
    message: Message
    room_created: bool
    message_created: bool
    envelope_count: int
    recipient_delivery_blocked: bool = False

@dataclass(frozen=True, slots=True)
class RoomListItem:
    room: Room
    member_user_ids: list[str]
    other_member_user_ids: list[str]
    last_message: Message | None
    caller_role: str | None = None
    member_count: int = 0
    group_security_ready: bool = False
    group_active_epoch_number: int | None = None


class RoomListAccessError(DirectMessageServiceError):
    """Raised when a user cannot list rooms."""


def build_direct_pair_key(
    first_user_id: Any,
    second_user_id: Any,
) -> str:
    first = str(first_user_id).strip()
    second = str(second_user_id).strip()

    if not first or not second:
        raise DirectMessageValidationError(
            "Both direct-chat user IDs are required."
        )

    if first == second:
        raise DirectMessageValidationError(
            "A direct-chat recipient must be a different user."
        )

    normalized_pair = ":".join(
        sorted([first, second])
    )

    return hashlib.sha256(
        normalized_pair.encode("utf-8")
    ).hexdigest()


def _normalize_uuid(
    value: Any,
    *,
    field_name: str,
) -> UUID:
    try:
        return UUID(str(value))
    except (TypeError, ValueError, AttributeError) as error:
        raise DirectMessageValidationError(
            f"{field_name} must be a valid UUID."
        ) from error


def _normalize_envelopes(
    envelopes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not isinstance(envelopes, list) or not envelopes:
        raise DirectMessageValidationError(
            "At least one encrypted device envelope is required."
        )

    valid_protocols = {
        choice
        for choice, _label
        in MessageKeyEnvelope.Protocol.choices
    }

    normalized = []
    seen_device_ids = set()

    for index, envelope in enumerate(envelopes):
        if not isinstance(envelope, dict):
            raise DirectMessageValidationError(
                f"Envelope {index} must be a JSON object."
            )

        device_id = _normalize_uuid(
            envelope.get("recipient_device_id"),
            field_name=(
                f"envelopes[{index}].recipient_device_id"
            ),
        )

        device_id_text = str(device_id)

        if device_id_text in seen_device_ids:
            raise DirectMessageValidationError(
                "Only one envelope may be supplied for each device."
            )

        seen_device_ids.add(device_id_text)

        protocol = str(
            envelope.get("protocol", "")
        ).strip()

        if protocol not in valid_protocols:
            raise DirectMessageValidationError(
                f"Envelope {index} has an invalid protocol."
            )

        wrapped_message_key = str(
            envelope.get("wrapped_message_key", "")
        ).strip()

        if not wrapped_message_key:
            raise DirectMessageValidationError(
                f"Envelope {index} requires an encrypted "
                "wrapped_message_key."
            )

        session_reference = str(
            envelope.get("session_reference", "")
        ).strip()

        metadata = envelope.get(
            "key_wrap_metadata",
            {},
        )

        if not isinstance(metadata, dict):
            raise DirectMessageValidationError(
                f"Envelope {index} key_wrap_metadata must "
                "be a JSON object."
            )

        try:
            envelope_version = int(
                envelope.get("envelope_version", 1)
            )
        except (TypeError, ValueError) as error:
            raise DirectMessageValidationError(
                f"Envelope {index} has an invalid version."
            ) from error

        if envelope_version < 1:
            raise DirectMessageValidationError(
                f"Envelope {index} version must be at least 1."
            )

        normalized.append(
            {
                "recipient_device_id": device_id,
                "protocol": protocol,
                "session_reference": session_reference,
                "wrapped_message_key": wrapped_message_key,
                "key_wrap_metadata": metadata,
                "envelope_version": envelope_version,
            }
        )

    return normalized


def _canonical_input_envelopes(
    envelopes: list[dict[str, Any]],
) -> list[tuple[Any, ...]]:
    return sorted(
        [
            (
                str(item["recipient_device_id"]),
                item["protocol"],
                item["session_reference"],
                item["wrapped_message_key"],
                item["key_wrap_metadata"],
                item["envelope_version"],
            )
            for item in envelopes
        ],
        key=lambda value: value[0],
    )


def _canonical_stored_envelopes(
    message: Message,
) -> list[tuple[Any, ...]]:
    return sorted(
        [
            (
                str(envelope.recipient_device_id),
                envelope.protocol,
                envelope.session_reference,
                envelope.wrapped_message_key,
                envelope.key_wrap_metadata,
                envelope.envelope_version,
            )
            for envelope in message.key_envelopes.all()
        ],
        key=lambda value: value[0],
    )


def _find_existing_idempotent_message(
    *,
    sender_user_id: str,
    client_message_id: UUID,
) -> Message | None:
    return (
        Message.objects
        .select_for_update()
        .select_related("room")
        .prefetch_related("key_envelopes")
        .filter(
            sender_user_id=sender_user_id,
            client_message_id=client_message_id,
        )
        .first()
    )


def _validate_existing_idempotent_message(
    *,
    message: Message,
    expected_pair_key: str,
    sender_device_id: UUID,
    message_type: str,
    encrypted_payload: str,
    encryption_metadata: dict[str, Any],
    encryption_version: int,
    reply_to_id: UUID | None,
    client_sent_at: Any,
    envelopes: list[dict[str, Any]],
) -> None:
    conflict = (
        message.room.room_type != "direct"
        or message.room.direct_pair_key
        != expected_pair_key
        or message.sender_device_id
        != str(sender_device_id)
        or message.message_type != message_type
        or message.encrypted_payload
        != encrypted_payload
        or message.encryption_metadata
        != encryption_metadata
        or message.encryption_version
        != encryption_version
        or message.reply_to_id != reply_to_id
    )

    if (
        client_sent_at is not None
        and message.client_sent_at != client_sent_at
    ):
        conflict = True

    if (
        _canonical_stored_envelopes(message)
        != _canonical_input_envelopes(envelopes)
    ):
        conflict = True

    if conflict:
        raise IdempotencyConflictError(
            "This client_message_id was already used with "
            "different message or envelope data."
        )


def _validate_existing_direct_room(
    *,
    room: Room,
    sender_user_id: str,
    recipient_user_id: str,
) -> None:
    if room.room_type != "direct":
        raise DirectRoomUnavailableError(
            "The matching room is not a direct room."
        )

    if not room.is_active:
        raise DirectRoomUnavailableError(
            "The direct room is inactive."
        )

    active_members = set(
        room.members.filter(
            is_active=True,
            user_id__in=[
                sender_user_id,
                recipient_user_id,
            ],
        ).values_list(
            "user_id",
            flat=True,
        )
    )

    expected_members = {
        sender_user_id,
        recipient_user_id,
    }

    if active_members != expected_members:
        raise DirectRoomUnavailableError(
            "The direct room does not have both active members."
        )


def _get_or_create_direct_room(
    *,
    sender_user_id: str,
    recipient_user_id: str,
    pair_key: str,
) -> tuple[Room, bool]:
    room = (
        Room.objects
        .select_for_update()
        .filter(direct_pair_key=pair_key)
        .first()
    )

    if room is not None:
        _validate_existing_direct_room(
            room=room,
            sender_user_id=sender_user_id,
            recipient_user_id=recipient_user_id,
        )

        return room, False

    try:
        with transaction.atomic():
            room = Room(
                room_type="direct",
                name="",
                created_by_user_id=sender_user_id,
                direct_pair_key=pair_key,
                is_active=True,
            )

            room.full_clean()
            room.save(force_insert=True)

            sender_member = RoomMember(
                room=room,
                user_id=sender_user_id,
                role="member",
                added_by_user_id=sender_user_id,
                is_active=True,
            )

            recipient_member = RoomMember(
                room=room,
                user_id=recipient_user_id,
                role="member",
                added_by_user_id=sender_user_id,
                is_active=True,
            )

            sender_member.full_clean()
            sender_member.save(force_insert=True)

            recipient_member.full_clean()
            recipient_member.save(force_insert=True)

        return room, True

    except IntegrityError:
        room = (
            Room.objects
            .select_for_update()
            .get(direct_pair_key=pair_key)
        )

        _validate_existing_direct_room(
            room=room,
            sender_user_id=sender_user_id,
            recipient_user_id=recipient_user_id,
        )

        return room, False


def _resolve_and_validate_envelope_devices(
    *,
    sender_user_id: str,
    recipient_user_id: str,
    sender_device_id: UUID,
    envelopes: list[dict[str, Any]],
) -> dict[str, Device]:
    active_devices = list(
        Device.objects
        .select_for_update()
        .filter(
            user_id__in=[
                sender_user_id,
                recipient_user_id,
            ],
            is_active=True,
        )
        .order_by("user_id", "created_at", "id")
    )

    devices_by_id = {
        str(device.id): device
        for device in active_devices
    }

    sender_device = devices_by_id.get(
        str(sender_device_id)
    )

    if sender_device is None:
        raise DirectMessageValidationError(
            "The sender device is not registered or is inactive."
        )

    if sender_device.user_id != sender_user_id:
        raise DirectMessageValidationError(
            "The sender device does not belong to the "
            "authenticated sender."
        )

    recipient_devices = {
        str(device.id)
        for device in active_devices
        if device.user_id == recipient_user_id
    }

    if not recipient_devices:
        raise DirectMessageValidationError(
            "The recipient has no active E2EE devices."
        )

    expected_device_ids = set(
        devices_by_id.keys()
    )

    provided_device_ids = {
        str(item["recipient_device_id"])
        for item in envelopes
    }

    missing_device_ids = sorted(
        expected_device_ids - provided_device_ids
    )

    unexpected_device_ids = sorted(
        provided_device_ids - expected_device_ids
    )

    if missing_device_ids:
        raise DirectMessageValidationError(
            "Encrypted envelopes are missing for these active "
            f"devices: {', '.join(missing_device_ids)}."
        )

    if unexpected_device_ids:
        raise DirectMessageValidationError(
            "Encrypted envelopes were supplied for inactive, "
            "unknown or unrelated devices: "
            f"{', '.join(unexpected_device_ids)}."
        )

    for item in envelopes:
        device = devices_by_id[
            str(item["recipient_device_id"])
        ]

        if device.user_id == sender_user_id:
            expected_protocol = (
                MessageKeyEnvelope.Protocol.DEVICE_SYNC
            )
        else:
            expected_protocol = (
                MessageKeyEnvelope.Protocol.DOUBLE_RATCHET
            )

        if item["protocol"] != expected_protocol:
            raise DirectMessageValidationError(
                f"Device {device.id} must use the "
                f"{expected_protocol} envelope protocol."
            )

    return devices_by_id



def _filter_envelopes_to_stored_devices(
    *,
    message: Message,
    envelopes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    stored_device_ids = {
        str(envelope.recipient_device_id)
        for envelope in message.key_envelopes.all()
    }

    return [
        item
        for item in envelopes
        if str(item["recipient_device_id"]) in stored_device_ids
    ]


def _message_has_recipient_delivery(
    *,
    message: Message,
    recipient_user_id: str,
) -> bool:
    return any(
        envelope.recipient_user_id == recipient_user_id
        for envelope in message.key_envelopes.all()
    )


def _resolve_and_validate_sender_only_envelope_devices(
    *,
    sender_user_id: str,
    sender_device_id: UUID,
    envelopes: list[dict[str, Any]],
) -> tuple[dict[str, Device], list[dict[str, Any]]]:
    """
    Used when recipient has blocked sender.

    Sender should not know they were blocked, so the client may still send
    recipient envelopes. Messenger ignores recipient envelopes and stores only
    sender device-sync envelopes.
    """

    active_sender_devices = list(
        Device.objects
        .select_for_update()
        .filter(
            user_id=sender_user_id,
            is_active=True,
        )
        .order_by("created_at", "id")
    )

    devices_by_id = {
        str(device.id): device
        for device in active_sender_devices
    }

    sender_device = devices_by_id.get(
        str(sender_device_id)
    )

    if sender_device is None:
        raise DirectMessageValidationError(
            "The sender device is not registered or is inactive."
        )

    provided_device_ids = {
        str(item["recipient_device_id"])
        for item in envelopes
    }

    expected_device_ids = set(devices_by_id.keys())

    missing_device_ids = sorted(
        expected_device_ids - provided_device_ids
    )

    if missing_device_ids:
        raise DirectMessageValidationError(
            "Encrypted envelopes are missing for these active "
            f"devices: {', '.join(missing_device_ids)}."
        )

    sender_only_envelopes = [
        item
        for item in envelopes
        if str(item["recipient_device_id"]) in expected_device_ids
    ]

    for item in sender_only_envelopes:
        if item["protocol"] != MessageKeyEnvelope.Protocol.DEVICE_SYNC:
            device_id = str(item["recipient_device_id"])
            raise DirectMessageValidationError(
                f"Device {device_id} must use the "
                f"{MessageKeyEnvelope.Protocol.DEVICE_SYNC} "
                "envelope protocol."
            )

    return devices_by_id, sender_only_envelopes


def _resolve_reply_message(
    *,
    room: Room,
    reply_to_id: UUID | None,
) -> Message | None:
    if reply_to_id is None:
        return None

    reply_message = (
        Message.objects
        .filter(id=reply_to_id)
        .first()
    )

    if reply_message is None:
        raise DirectMessageValidationError(
            "The reply target message was not found."
        )

    if reply_message.room_id != room.id:
        raise DirectMessageValidationError(
            "A reply target must belong to the same room."
        )

    return reply_message



@transaction.atomic
def send_direct_message(
    *,
    sender_user_id: Any,
    recipient_user_id: Any,
    sender_device_id: Any,
    client_message_id: Any,
    message_type: str,
    encrypted_payload: str,
    encryption_metadata: dict[str, Any],
    envelopes: list[dict[str, Any]],
    encryption_version: int = 1,
    reply_to_id: Any = None,
    client_sent_at: Any = None,
) -> DirectMessageResult:
    sender_id = str(sender_user_id).strip()
    recipient_id = str(recipient_user_id).strip()

    if not sender_id:
        raise DirectMessageValidationError(
            "The authenticated sender user ID is required."
        )

    if not recipient_id:
        raise DirectMessageValidationError(
            "The recipient user ID is required."
        )

    pair_key = build_direct_pair_key(
        sender_id,
        recipient_id,
    )

    normalized_sender_device_id = _normalize_uuid(
        sender_device_id,
        field_name="sender_device_id",
    )

    normalized_client_message_id = _normalize_uuid(
        client_message_id,
        field_name="client_message_id",
    )

    normalized_reply_to_id = (
        _normalize_uuid(
            reply_to_id,
            field_name="reply_to_id",
        )
        if reply_to_id is not None
        else None
    )

    normalized_message_type = str(
        message_type
    ).strip()

    valid_message_types = {
        choice
        for choice, _label
        in Message.MessageType.choices
    }

    if normalized_message_type not in valid_message_types:
        raise DirectMessageValidationError(
            "The message type is invalid."
        )

    normalized_encrypted_payload = str(
        encrypted_payload
    ).strip()

    if not normalized_encrypted_payload:
        raise DirectMessageValidationError(
            "The encrypted message payload is required."
        )

    if not isinstance(encryption_metadata, dict):
        raise DirectMessageValidationError(
            "Encryption metadata must be a JSON object."
        )

    try:
        normalized_encryption_version = int(
            encryption_version
        )
    except (TypeError, ValueError) as error:
        raise DirectMessageValidationError(
            "The encryption version is invalid."
        ) from error

    if normalized_encryption_version < 1:
        raise DirectMessageValidationError(
            "The encryption version must be at least 1."
        )

    normalized_envelopes = _normalize_envelopes(
        envelopes
    )

    delivery_policy_snapshot = get_delivery_policy_snapshot(
        recipient_user_id=recipient_id,
        sender_user_id=sender_id,
    )

    recipient_delivery_blocked = (
        delivery_policy_snapshot.is_blocked
    )

    recipient_ghosting_sender = (
        delivery_policy_snapshot.ghost_active
        and not recipient_delivery_blocked
    )

    existing_message = (
        _find_existing_idempotent_message(
            sender_user_id=sender_id,
            client_message_id=(
                normalized_client_message_id
            ),
        )
    )

    if existing_message is not None:
        existing_has_recipient_delivery = (
            _message_has_recipient_delivery(
                message=existing_message,
                recipient_user_id=recipient_id,
            )
        )

        effective_existing_envelopes = (
            normalized_envelopes
            if existing_has_recipient_delivery
            else _filter_envelopes_to_stored_devices(
                message=existing_message,
                envelopes=normalized_envelopes,
            )
        )

        _validate_existing_idempotent_message(
            message=existing_message,
            expected_pair_key=pair_key,
            sender_device_id=(
                normalized_sender_device_id
            ),
            message_type=normalized_message_type,
            encrypted_payload=(
                normalized_encrypted_payload
            ),
            encryption_metadata=encryption_metadata,
            encryption_version=(
                normalized_encryption_version
            ),
            reply_to_id=normalized_reply_to_id,
            client_sent_at=client_sent_at,
            envelopes=effective_existing_envelopes,
        )

        return DirectMessageResult(
            room=existing_message.room,
            message=existing_message,
            room_created=False,
            message_created=False,
            envelope_count=(
                existing_message.key_envelopes.count()
            ),
            recipient_delivery_blocked=(
                not existing_has_recipient_delivery
            ),
        )

    try:
        if recipient_delivery_blocked:
            devices_by_id, effective_envelopes = (
                _resolve_and_validate_sender_only_envelope_devices(
                    sender_user_id=sender_id,
                    sender_device_id=(
                        normalized_sender_device_id
                    ),
                    envelopes=normalized_envelopes,
                )
            )
        else:
            devices_by_id = (
                _resolve_and_validate_envelope_devices(
                    sender_user_id=sender_id,
                    recipient_user_id=recipient_id,
                    sender_device_id=(
                        normalized_sender_device_id
                    ),
                    envelopes=normalized_envelopes,
                )
            )
            effective_envelopes = normalized_envelopes

        room, room_created = (
            _get_or_create_direct_room(
                sender_user_id=sender_id,
                recipient_user_id=recipient_id,
                pair_key=pair_key,
            )
        )

        reply_message = _resolve_reply_message(
            room=room,
            reply_to_id=normalized_reply_to_id,
        )

        message = Message(
            room=room,
            sender_user_id=sender_id,
            sender_device_id=str(
                normalized_sender_device_id
            ),
            client_message_id=(
                normalized_client_message_id
            ),
            message_type=normalized_message_type,
            encrypted_payload=(
                normalized_encrypted_payload
            ),
            encryption_metadata=(
                encryption_metadata
            ),
            encryption_version=(
                normalized_encryption_version
            ),
            reply_to=reply_message,
            client_sent_at=client_sent_at,
        )

        message.full_clean()
        message.save(force_insert=True)

        envelope_models = []

        for item in effective_envelopes:
            device = devices_by_id[
                str(item["recipient_device_id"])
            ]

            envelope = MessageKeyEnvelope(
                message=message,
                recipient_device_id=item["recipient_device_id"],
                recipient_user_id=device.user_id,
                protocol=item["protocol"],
                session_reference=item["session_reference"],
                wrapped_message_key=item["wrapped_message_key"],
                key_wrap_metadata=item["key_wrap_metadata"],
                envelope_version=item["envelope_version"],
            )
            envelope.full_clean()
            envelope_models.append(envelope)

        MessageKeyEnvelope.objects.bulk_create(
            envelope_models
        )

        if recipient_delivery_blocked:
            policy_reason = (
                DirectMessageReceiptDecision.PolicyReason.BLOCKED
            )
        elif recipient_ghosting_sender:
            policy_reason = (
                DirectMessageReceiptDecision.PolicyReason.GHOST
            )
        else:
            policy_reason = (
                DirectMessageReceiptDecision.PolicyReason.NORMAL
            )

        receipt_decision = DirectMessageReceiptDecision(
            message=message,
            sender_user_id=sender_id,
            recipient_user_id=recipient_id,
            suppress_delivered_receipt=(
                recipient_ghosting_sender
            ),
            suppress_read_receipt=(
                recipient_ghosting_sender
            ),
            policy_reason=policy_reason,
            policy_version=(
                delivery_policy_snapshot.policy_version
            ),
        )
        receipt_decision.full_clean()
        receipt_decision.save()

        room.updated_at = timezone.now()
        room.save(
            update_fields=[
                "updated_at",
            ]
        )

    except ValidationError as error:
        raise DirectMessageValidationError(
            error.message_dict
            if hasattr(error, "message_dict")
            else error.messages
        ) from error

    except IntegrityError:
        existing_message = (
            _find_existing_idempotent_message(
                sender_user_id=sender_id,
                client_message_id=(
                    normalized_client_message_id
                ),
            )
        )

        if existing_message is None:
            raise

        existing_has_recipient_delivery = (
            _message_has_recipient_delivery(
                message=existing_message,
                recipient_user_id=recipient_id,
            )
        )

        effective_existing_envelopes = (
            normalized_envelopes
            if existing_has_recipient_delivery
            else _filter_envelopes_to_stored_devices(
                message=existing_message,
                envelopes=normalized_envelopes,
            )
        )

        _validate_existing_idempotent_message(
            message=existing_message,
            expected_pair_key=pair_key,
            sender_device_id=(
                normalized_sender_device_id
            ),
            message_type=normalized_message_type,
            encrypted_payload=(
                normalized_encrypted_payload
            ),
            encryption_metadata=encryption_metadata,
            encryption_version=(
                normalized_encryption_version
            ),
            reply_to_id=normalized_reply_to_id,
            client_sent_at=client_sent_at,
            envelopes=effective_existing_envelopes,
        )

        return DirectMessageResult(
            room=existing_message.room,
            message=existing_message,
            room_created=False,
            message_created=False,
            envelope_count=(
                existing_message.key_envelopes.count()
            ),
            recipient_delivery_blocked=(
                not existing_has_recipient_delivery
            ),
        )

    return DirectMessageResult(
        room=room,
        message=message,
        room_created=room_created,
        message_created=True,
        envelope_count=len(envelope_models),
        recipient_delivery_blocked=recipient_delivery_blocked,
    )


def list_user_rooms(
    *,
    authenticated_user_id: str,
) -> list[RoomListItem]:
    user_id = str(authenticated_user_id).strip()

    if not user_id:
        raise RoomListAccessError(
            "The authenticated user ID is required."
        )

    active_members = RoomMember.objects.filter(
        is_active=True,
    ).order_by(
        "joined_at",
        "id",
    )

    rooms = list(
        Room.objects.select_related(
            "group_profile",
        )
        .filter(
            is_active=True,
            members__user_id=user_id,
            members__is_active=True,
        )
        .prefetch_related(
            Prefetch(
                "members",
                queryset=active_members,
                to_attr="active_members",
            )
        )
        .order_by(
            "-updated_at",
            "-created_at",
            "id",
        )
        .distinct()
    )

    last_messages = (
        Message.objects.filter(
            room__in=rooms,
        )
        .order_by(
            "room_id",
            "-created_at",
            "-id",
        )
    )

    last_message_by_room_id = {}

    for message in last_messages:
        last_message_by_room_id.setdefault(
            message.room_id,
            message,
        )

    active_epoch_by_room_id = {
        epoch.group_room_id: epoch
        for epoch in GroupEncryptionEpoch.objects.filter(
            group_room__in=rooms,
            status=GroupEncryptionEpoch.Status.ACTIVE,
        )
    }

    room_items = []

    for room in rooms:
        active_room_members = list(
            getattr(
                room,
                "active_members",
                [],
            )
        )

        caller_membership = next(
            (
                member
                for member in active_room_members
                if member.user_id == user_id
            ),
            None,
        )

        active_epoch = active_epoch_by_room_id.get(room.id)

        room_items.append(
            RoomListItem(
                room=room,
                member_user_ids=[
                    member.user_id
                    for member in active_room_members
                ],
                other_member_user_ids=[
                    member.user_id
                    for member in active_room_members
                    if member.user_id != user_id
                ],
                last_message=last_message_by_room_id.get(
                    room.id,
                ),
                caller_role=(
                    caller_membership.role
                    if caller_membership is not None
                    else None
                ),
                member_count=len(active_room_members),
                group_security_ready=False,
                group_active_epoch_number=(
                    active_epoch.epoch_number
                    if active_epoch is not None
                    else None
                ),
            )
        )

    return room_items








from django.db.models import Prefetch, QuerySet

from apps.rooms.models import Room, RoomMember

from .models import Message, MessageKeyEnvelope


class MessageHistoryAccessError(DirectMessageServiceError):
    """Raised when a user or device cannot access room history."""


@dataclass(frozen=True)
class EncryptedMessageHistoryResult:
    room: Room
    device: Device
    messages: QuerySet


def get_encrypted_message_history(
    *,
    authenticated_user_id: str,
    room_id: UUID | str,
    device_id: UUID | str,
) -> EncryptedMessageHistoryResult:
    user_id = str(authenticated_user_id).strip()

    if not user_id:
        raise MessageHistoryAccessError(
            "The authenticated user ID is required."
        )

    normalized_room_id = _normalize_uuid(
        room_id,
        field_name="room_id",
    )

    normalized_device_id = _normalize_uuid(
        device_id,
        field_name="device_id",
    )

    try:
        room = Room.objects.get(
            id=normalized_room_id,
            is_active=True,
        )
    except Room.DoesNotExist as error:
        raise MessageHistoryAccessError(
            "The requested room does not exist or is inactive."
        ) from error

    membership_exists = RoomMember.objects.filter(
        room=room,
        user_id=user_id,
        is_active=True,
    ).exists()

    if not membership_exists:
        raise MessageHistoryAccessError(
            "The authenticated user is not an active member "
            "of this room."
        )

    try:
        device = Device.objects.get(
            id=normalized_device_id,
            user_id=user_id,
            is_active=True,
        )
    except Device.DoesNotExist as error:
        raise MessageHistoryAccessError(
            "The requested device is not an active device "
            "owned by the authenticated user."
        ) from error

    device_envelopes = MessageKeyEnvelope.objects.filter(
        recipient_device_id=device.id,
        recipient_user_id=user_id,
    ).order_by(
        "created_at",
        "id",
    )

    messages = (
        Message.objects.filter(
            room=room,
            key_envelopes__recipient_device_id=device.id,
            key_envelopes__recipient_user_id=user_id,
        )
        .select_related(
            "reply_to",
        )
        .prefetch_related(
            Prefetch(
                "key_envelopes",
                queryset=device_envelopes,
                to_attr="requesting_device_envelopes",
            )
        )
        .distinct()
        .order_by(
            "-created_at",
            "-id",
        )
    )

    return EncryptedMessageHistoryResult(
        room=room,
        device=device,
        messages=messages,
    )

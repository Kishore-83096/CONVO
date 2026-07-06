import hashlib
import os
import time
from contextvars import ContextVar
from contextlib import nullcontext
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any
from uuid import UUID
from apps.group_chat.models import GroupEncryptionEpoch
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.utils import timezone
from .policy_services import (
    DeliveryPolicySnapshot,
    get_delivery_policy_snapshot,
    sender_has_saved_direct_contact,
)
from apps.e2ee_devices.models import Device
from apps.e2ee_devices.services import get_active_device_user_ids_by_id
from apps.rooms.models import Room, RoomMember


from .models import (
    DirectContactState,
    DirectMessageReceiptDecision,
    Message,
    MessageKeyEnvelope,
)

from .attachment_services import (
    AttachmentConflictError,
    AttachmentNotFoundError,
    AttachmentPermissionError,
    AttachmentValidationError,
    validate_and_attach_message_attachments,
    validate_idempotent_message_attachments,
)


from django.db.models import Prefetch, QuerySet

from apps.group_chat.models import GroupProfile
from apps.realtime.events import (
    MESSAGE_STORED,
    build_event,
)

from apps.realtime.outbox import (
    RealtimeOutboxCreateSpec,
    build_direct_message_stored_event_key,
    enqueue_new_realtime_outbox_events_sync,
)


from apps.realtime.publishers import make_device_group_name


class DirectMessageServiceError(Exception):
    """Base exception for direct-message operations."""


class DirectMessageValidationError(DirectMessageServiceError):
    """Raised when message input is invalid."""


class DirectRoomUnavailableError(DirectMessageServiceError):
    """Raised when an existing direct room cannot be used."""


class SavedContactRequiredError(DirectMessageServiceError):
    """
    Raised when the sender tries to send to a user they have not saved.
    """

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
    recipient_device_ids: tuple[str, ...] = ()
    realtime_event_payload: dict[str, Any] | None = None
    realtime_outbox_event_count: int = 0
    profile_timings_ms: dict[str, float] | None = None

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


def direct_send_profile_enabled() -> bool:
    return os.getenv(
        "MYNA_PROFILE_DIRECT_SEND",
        "false",
    ).strip().lower() in {"1", "true", "yes", "on"}


def profile_checkpoint(
    timings: dict[str, float] | None,
    name: str,
    started_at: float,
) -> None:
    if timings is not None:
        timings[name] = round(
            (time.perf_counter() - started_at) * 1000,
            2,
        )


def _profile_percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return round(ordered[0], 2)
    rank = (len(ordered) - 1) * pct
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    weight = rank - lower
    return round(ordered[lower] * (1 - weight) + ordered[upper] * weight, 2)


_ACTIVE_DB_PROFILE: ContextVar[
    "DirectSendDatabaseProfile | None"
] = ContextVar(
    "myna_direct_send_db_profile",
    default=None,
)


class DirectSendDatabaseProfile:
    def __init__(self, timings: dict[str, float] | None) -> None:
        self.timings = timings
        self.query_durations_ms: list[float] = []
        self.query_durations_by_stage_ms: dict[str, list[float]] = {}
        self.operation_counts: dict[str, int] = {
            "select": 0,
            "insert": 0,
            "update": 0,
            "delete": 0,
            "other": 0,
        }
        self.operation_counts_by_stage: dict[str, dict[str, int]] = {}
        self.current_stage = "unattributed"
        self.started_with_connection = False
        self._context = None
        self._profile_token = None

    def __enter__(self):
        if self.timings is None:
            return self
        self.started_with_connection = connection.connection is not None
        self.timings["db_connection_was_present_before_ensure"] = (
            1.0
            if self.started_with_connection
            else 0.0
        )
        ensure_started_ns = time.perf_counter_ns()
        connection.ensure_connection()
        self.timings["db_connection_ensure_ms"] = round(
            (time.perf_counter_ns() - ensure_started_ns) / 1_000_000,
            2,
        )
        self._context = connection.execute_wrapper(self._execute_wrapper)
        self._context.__enter__()
        self._profile_token = _ACTIVE_DB_PROFILE.set(self)
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        if self._profile_token is not None:
            _ACTIVE_DB_PROFILE.reset(self._profile_token)
        if self._context is not None:
            self._context.__exit__(exc_type, exc, traceback)
        if self.timings is None:
            return None

        query_count = len(self.query_durations_ms)
        total_ms = round(sum(self.query_durations_ms), 2)
        self.timings["db_query_count"] = float(query_count)
        self.timings["db_query_total_ms"] = total_ms
        self.timings["db_query_avg_ms"] = (
            round(total_ms / query_count, 2)
            if query_count
            else 0.0
        )
        self.timings["db_query_p50_ms"] = _profile_percentile(
            self.query_durations_ms,
            0.50,
        )
        self.timings["db_query_p95_ms"] = _profile_percentile(
            self.query_durations_ms,
            0.95,
        )
        self.timings["db_query_p99_ms"] = _profile_percentile(
            self.query_durations_ms,
            0.99,
        )
        self.timings["db_query_max_ms"] = (
            round(max(self.query_durations_ms), 2)
            if self.query_durations_ms
            else 0.0
        )
        for operation, count in self.operation_counts.items():
            self.timings[f"db_query_{operation}_count"] = float(count)
        for stage, durations in sorted(self.query_durations_by_stage_ms.items()):
            stage_query_count = len(durations)
            stage_total_ms = round(sum(durations), 2)
            self.timings[f"{stage}_db_query_count"] = float(stage_query_count)
            self.timings[f"{stage}_db_query_total_ms"] = stage_total_ms
            self.timings[f"{stage}_db_query_avg_ms"] = (
                round(stage_total_ms / stage_query_count, 2)
                if stage_query_count
                else 0.0
            )
            self.timings[f"{stage}_db_query_p95_ms"] = _profile_percentile(
                durations,
                0.95,
            )
            self.timings[f"{stage}_db_query_p99_ms"] = _profile_percentile(
                durations,
                0.99,
            )
            operation_counts = self.operation_counts_by_stage.get(stage, {})
            for operation in ("select", "insert", "update", "delete", "other"):
                self.timings[f"{stage}_db_query_{operation}_count"] = float(
                    operation_counts.get(operation, 0)
                )
        self.timings["db_connection_open_at_profile_start"] = (
            1.0
            if self.started_with_connection
            else 0.0
        )
        self.timings["db_connection_open_at_profile_finish"] = (
            1.0
            if connection.connection is not None
            else 0.0
        )
        self.timings["db_connection_observed_new"] = (
            1.0
            if (
                not self.started_with_connection
                and connection.connection is not None
                and query_count > 0
            )
            else 0.0
        )
        return None

    def _execute_wrapper(self, execute, sql, params, many, context):
        started_at = time.perf_counter()
        try:
            return execute(sql, params, many, context)
        finally:
            duration_ms = (time.perf_counter() - started_at) * 1000
            self.query_durations_ms.append(duration_ms)
            operation = self._operation_for_sql(sql)
            self.operation_counts[operation] = (
                self.operation_counts.get(operation, 0) + 1
            )
            stage = str(self.current_stage or "unattributed")
            self.query_durations_by_stage_ms.setdefault(stage, []).append(
                duration_ms
            )
            stage_operations = self.operation_counts_by_stage.setdefault(
                stage,
                {
                    "select": 0,
                    "insert": 0,
                    "update": 0,
                    "delete": 0,
                    "other": 0,
                },
            )
            stage_operations[operation] = stage_operations.get(operation, 0) + 1

    @staticmethod
    def _operation_for_sql(sql: Any) -> str:
        first_token = str(sql or "").lstrip().split(maxsplit=1)
        operation = first_token[0].lower() if first_token else ""
        if operation in {"select", "insert", "update", "delete"}:
            return operation
        return "other"


def profile_database_queries(timings: dict[str, float] | None):
    if timings is None:
        return nullcontext()
    return DirectSendDatabaseProfile(timings)


@contextmanager
def profile_database_stage(stage: str):
    profile = _ACTIVE_DB_PROFILE.get()
    if profile is None:
        yield
        return

    previous_stage = profile.current_stage
    profile.current_stage = str(stage or "unattributed")
    try:
        yield
    finally:
        profile.current_stage = previous_stage



def resolve_existing_direct_room_recipient(
    *,
    authenticated_user_id: str,
    room_id: Any,
) -> tuple[Room, str]:
    """
    Resolve the recipient for an existing direct room using only the
    hot-path columns required for validation and sending.

    This avoids the identity-service saved-contact lookup and avoids
    prefetching full RoomMember model objects when the request already
    contains a trusted existing room_id.
    """

    sender_id = str(authenticated_user_id).strip()

    if not sender_id:
        raise DirectRoomUnavailableError(
            "Direct room is unavailable."
        )

    active_members = list(
        RoomMember.objects.filter(
            room_id=room_id,
            is_active=True,
            room__room_type=Room.RoomType.DIRECT,
            room__is_active=True,
        )
        .select_related(
            "room",
        )
        .only(
            "id",
            "room_id",
            "user_id",
            "is_active",
            "joined_at",
            "room__id",
            "room__room_type",
            "room__is_active",
            "room__direct_pair_key",
            "room__created_at",
            "room__updated_at",
        )
        .order_by(
            "joined_at",
            "id",
        )
    )

    if not active_members:
        raise DirectRoomUnavailableError(
            "Direct room is unavailable."
        )

    room = active_members[0].room
    active_member_user_ids = [
        member.user_id
        for member in active_members
    ]

    if (
        len(active_member_user_ids) != 2
        or sender_id not in active_member_user_ids
    ):
        raise DirectRoomUnavailableError(
            "Direct room is unavailable."
        )

    recipient_user_id = next(
        user_id
        for user_id in active_member_user_ids
        if user_id != sender_id
    )

    if (
        room.direct_pair_key
        != build_direct_pair_key(
            sender_id,
            recipient_user_id,
        )
    ):
        raise DirectRoomUnavailableError(
            "Direct room is unavailable."
        )

    room.active_members = tuple(active_members)

    return room, str(recipient_user_id)





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
    expected_pair_key: str | None = None,
) -> None:
    if room.room_type != "direct":
        raise DirectRoomUnavailableError(
            "The matching room is not a direct room."
        )

    if not room.is_active:
        raise DirectRoomUnavailableError(
            "The direct room is inactive."
        )

    if (
        expected_pair_key is not None
        and room.direct_pair_key != expected_pair_key
    ):
        raise DirectRoomUnavailableError(
            "The direct room does not match the sender and recipient."
        )

    prefetched_members = getattr(
        room,
        "active_members",
        None,
    )

    if prefetched_members is not None:
        active_members = {
            member.user_id
            for member in prefetched_members
            if member.user_id in {
                sender_user_id,
                recipient_user_id,
            }
        }
    else:
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
            expected_pair_key=pair_key,
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
            expected_pair_key=pair_key,
        )

        return room, False

def _resolve_and_validate_envelope_devices(
    *,
    sender_user_id: str,
    recipient_user_id: str,
    sender_device_id: UUID,
    envelopes: list[dict[str, Any]],
) -> dict[str, str]:
    devices_by_id = get_active_device_user_ids_by_id(
        user_ids=(
            sender_user_id,
            recipient_user_id,
        )
    )

    sender_device_user_id = devices_by_id.get(
        str(sender_device_id)
    )

    if sender_device_user_id is None:
        raise DirectMessageValidationError(
            "The sender device is not registered or is inactive."
        )

    if sender_device_user_id != sender_user_id:
        raise DirectMessageValidationError(
            "The sender device does not belong to the "
            "authenticated sender."
        )

    recipient_devices = {
        device_id
        for device_id, device_user_id in devices_by_id.items()
        if device_user_id == recipient_user_id
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
        device_id = str(item["recipient_device_id"])
        device_user_id = devices_by_id[device_id]

        if device_user_id == sender_user_id:
            expected_protocol = (
                MessageKeyEnvelope.Protocol.DEVICE_SYNC
            )
        else:
            expected_protocol = (
                MessageKeyEnvelope.Protocol.DOUBLE_RATCHET
            )

        if item["protocol"] != expected_protocol:
            raise DirectMessageValidationError(
                f"Device {device_id} must use the "
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


def _return_existing_idempotent_direct_message(
    *,
    sender_id: str,
    recipient_id: str,
    pair_key: str,
    normalized_client_message_id: UUID,
    normalized_sender_device_id: UUID,
    normalized_message_type: str,
    normalized_encrypted_payload: str,
    encryption_metadata: dict[str, Any],
    normalized_encryption_version: int,
    normalized_reply_to_id: UUID | None,
    client_sent_at: Any,
    normalized_envelopes: list[dict[str, Any]],
    attachment_ids: list[Any] | None,
    profile_timings_ms: dict[str, float] | None = None,
) -> DirectMessageResult:
    existing_message = (
        _find_existing_idempotent_message(
            sender_user_id=sender_id,
            client_message_id=(
                normalized_client_message_id
            ),
        )
    )

    if existing_message is None:
        raise IntegrityError(
            "Message insert failed but no idempotent message was found."
        )

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

    try:
        validate_idempotent_message_attachments(
            message=existing_message,
            attachment_ids=attachment_ids,
        )
    except AttachmentConflictError as error:
        raise IdempotencyConflictError(str(error)) from error
    except (
        AttachmentValidationError,
        AttachmentNotFoundError,
        AttachmentPermissionError,
    ) as error:
        raise DirectMessageValidationError(str(error)) from error

    return DirectMessageResult(
        room=existing_message.room,
        message=existing_message,
        room_created=False,
        message_created=False,
        envelope_count=len(existing_message.key_envelopes.all()),
        recipient_delivery_blocked=(
            not existing_has_recipient_delivery
        ),
        profile_timings_ms=profile_timings_ms,
    )

def _resolve_and_validate_sender_only_envelope_devices(
    *,
    sender_user_id: str,
    sender_device_id: UUID,
    envelopes: list[dict[str, Any]],
) -> tuple[dict[str, str], list[dict[str, Any]]]:
    """
    Used when recipient has blocked sender.

    Sender should not know they were blocked, so the client may still send
    recipient envelopes. Messenger ignores recipient envelopes and stores only
    sender device-sync envelopes.
    """

    devices_by_id = get_active_device_user_ids_by_id(
        user_ids=(sender_user_id,)
    )

    sender_device_user_id = devices_by_id.get(
        str(sender_device_id)
    )

    if sender_device_user_id is None:
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




def _upsert_sender_saved_contact_state_from_identity(
    *,
    room: Room,
    sender_user_id: str,
    recipient_user_id: str,
    identity_contact_id: Any = None,
) -> None:
    """
    Create or repair DirectContactState after Identity has already confirmed
    recipient_contact_id belongs to the authenticated sender.

    This is used for the recipient_contact_id send path.

    It must not be used for room_id sends, because room_id sends should not
    call Identity.
    """

    normalized_identity_contact_id = None

    if identity_contact_id is not None:
        try:
            normalized_identity_contact_id = int(identity_contact_id)
        except (TypeError, ValueError) as error:
            raise DirectMessageValidationError(
                "identity_contact_id is invalid."
            ) from error

        if normalized_identity_contact_id < 1:
            raise DirectMessageValidationError(
                "identity_contact_id must be greater than zero."
            )

    contact_state = (
        DirectContactState.objects
        .select_for_update()
        .filter(
            owner_user_id=sender_user_id,
            contact_user_id=recipient_user_id,
        )
        .first()
    )

    created = contact_state is None

    if contact_state is None:
        contact_state = DirectContactState(
            room=room,
            owner_user_id=sender_user_id,
            contact_user_id=recipient_user_id,
        )

    changed = (
        created
        or contact_state.room_id != room.id
        or contact_state.is_saved is not True
        or (
            normalized_identity_contact_id is not None
            and contact_state.identity_contact_id
            != normalized_identity_contact_id
        )
    )

    contact_state.room = room
    contact_state.is_saved = True

    if normalized_identity_contact_id is not None:
        contact_state.identity_contact_id = normalized_identity_contact_id

    if changed:
        contact_state.full_clean()
        contact_state.save()






@transaction.atomic(savepoint=False)
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
    attachment_ids: list[Any] | None = None,
    sender_contact_validated_by_identity: bool = False,
    identity_contact_id: Any = None,
    existing_room: Room | None = None,
    delivery_policy_snapshot: DeliveryPolicySnapshot | None = None,
    require_saved_contact: bool = False,
    profile_timings_ms: dict[str, float] | None = None,
) -> DirectMessageResult:
    total_started_at = time.perf_counter()
    phase_started_at = time.perf_counter()

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
    profile_checkpoint(
        profile_timings_ms,
        "service_validate_input",
        phase_started_at,
    )

    if delivery_policy_snapshot is None:
        phase_started_at = time.perf_counter()
        delivery_policy_snapshot = get_delivery_policy_snapshot(
            recipient_user_id=recipient_id,
            sender_user_id=sender_id,
        )
        profile_checkpoint(
            profile_timings_ms,
            "service_policy_snapshot",
            phase_started_at,
        )
    else:
        profile_timings_ms and profile_timings_ms.setdefault(
            "service_policy_snapshot",
            0.0,
        )

    if existing_room is not None:
        phase_started_at = time.perf_counter()
        _validate_existing_direct_room(
            room=existing_room,
            sender_user_id=sender_id,
            recipient_user_id=recipient_id,
            expected_pair_key=pair_key,
        )
        profile_checkpoint(
            profile_timings_ms,
            "service_existing_room_validation",
            phase_started_at,
        )

    recipient_delivery_blocked = (
        delivery_policy_snapshot.is_blocked
    )

    recipient_ghosting_sender = (
        delivery_policy_snapshot.ghost_active
        and not recipient_delivery_blocked
    )

    if (
        existing_room is None
        and
        require_saved_contact
        and
        not sender_contact_validated_by_identity
        and not sender_has_saved_direct_contact(
            sender_user_id=sender_id,
            recipient_user_id=recipient_id,
        )
    ):
        raise SavedContactRequiredError(
            "Save this contact before sending a message."
        )

    try:
        phase_started_at = time.perf_counter()
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
        profile_checkpoint(
            profile_timings_ms,
            "service_device_lookup",
            phase_started_at,
        )

        phase_started_at = time.perf_counter()
        if existing_room is not None:
            room = existing_room
            room_created = False
        else:
            room, room_created = _get_or_create_direct_room(
                sender_user_id=sender_id,
                recipient_user_id=recipient_id,
                pair_key=pair_key,
            )
        profile_checkpoint(
            profile_timings_ms,
            "service_room_validation",
            phase_started_at,
        )


        if sender_contact_validated_by_identity:
            phase_started_at = time.perf_counter()
            _upsert_sender_saved_contact_state_from_identity(
                room=room,
                sender_user_id=sender_id,
                recipient_user_id=recipient_id,
                identity_contact_id=identity_contact_id,
            )
            profile_checkpoint(
                profile_timings_ms,
                "service_contact_state_upsert",
                phase_started_at,
            )


        phase_started_at = time.perf_counter()
        reply_message = _resolve_reply_message(
            room=room,
            reply_to_id=normalized_reply_to_id,
        )
        profile_checkpoint(
            profile_timings_ms,
            "service_reply_lookup",
            phase_started_at,
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

        try:
            with transaction.atomic():
                phase_started_at = time.perf_counter()
                message.save(force_insert=True)
                profile_checkpoint(
                    profile_timings_ms,
                    "service_message_insert",
                    phase_started_at,
                )
        except IntegrityError:
            profile_checkpoint(
                profile_timings_ms,
                "service_total",
                total_started_at,
            )
            return _return_existing_idempotent_direct_message(
                sender_id=sender_id,
                recipient_id=recipient_id,
                pair_key=pair_key,
                normalized_client_message_id=(
                    normalized_client_message_id
                ),
                normalized_sender_device_id=(
                    normalized_sender_device_id
                ),
                normalized_message_type=normalized_message_type,
                normalized_encrypted_payload=(
                    normalized_encrypted_payload
                ),
                encryption_metadata=encryption_metadata,
                normalized_encryption_version=(
                    normalized_encryption_version
                ),
                normalized_reply_to_id=normalized_reply_to_id,
                client_sent_at=client_sent_at,
                normalized_envelopes=normalized_envelopes,
                attachment_ids=attachment_ids,
                profile_timings_ms=profile_timings_ms,
            )

        if attachment_ids:
            try:
                phase_started_at = time.perf_counter()
                validate_and_attach_message_attachments(
                    authenticated_user_id=sender_id,
                    sender_device_id=normalized_sender_device_id,
                    room=room,
                    message=message,
                    attachment_ids=attachment_ids,
                )
                profile_checkpoint(
                    profile_timings_ms,
                    "service_attachment_validation",
                    phase_started_at,
                )
            except AttachmentConflictError as error:
                raise IdempotencyConflictError(str(error)) from error
            except (
                AttachmentValidationError,
                AttachmentNotFoundError,
                AttachmentPermissionError,
            ) as error:
                raise DirectMessageValidationError(str(error)) from error



        envelope_models = []

        for item in effective_envelopes:
            device_user_id = devices_by_id[
                str(item["recipient_device_id"])
            ]

            envelope = MessageKeyEnvelope(
                message=message,
                recipient_device_id=item["recipient_device_id"],
                recipient_user_id=device_user_id,
                protocol=item["protocol"],
                session_reference=item["session_reference"],
                wrapped_message_key=item["wrapped_message_key"],
                key_wrap_metadata=item["key_wrap_metadata"],
                envelope_version=item["envelope_version"],
            )
            envelope_models.append(envelope)

        phase_started_at = time.perf_counter()
        MessageKeyEnvelope.objects.bulk_create(
            envelope_models
        )
        profile_checkpoint(
            profile_timings_ms,
            "service_key_envelope_bulk_insert",
            phase_started_at,
        )

        if recipient_delivery_blocked or recipient_ghosting_sender:
            if recipient_delivery_blocked:
                policy_reason = (
                    DirectMessageReceiptDecision.PolicyReason.BLOCKED
                )
            else:
                policy_reason = (
                    DirectMessageReceiptDecision.PolicyReason.GHOST
                )

            phase_started_at = time.perf_counter()
            DirectMessageReceiptDecision.objects.create(
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
            profile_checkpoint(
                profile_timings_ms,
                "service_receipt_decision_insert",
                phase_started_at,
            )
        elif profile_timings_ms is not None:
            profile_timings_ms["service_receipt_decision_insert"] = 0.0

        room_updated_at = timezone.now()
        phase_started_at = time.perf_counter()
        Room.objects.filter(
            id=room.id,
        ).update(
            updated_at=room_updated_at,
        )
        room.updated_at = room_updated_at
        profile_checkpoint(
            profile_timings_ms,
            "service_room_update",
            phase_started_at,
        )

        recipient_device_ids = tuple(
            sorted(
                str(envelope.recipient_device_id)
                for envelope in envelope_models
                if envelope.recipient_user_id == recipient_id
            )
        )

        realtime_event_payload = {
            "room_id": str(room.id),
            "message_id": str(message.id),
            "client_message_id": str(message.client_message_id),
            "sender_user_id": str(message.sender_user_id),
            "message_type": message.message_type,
            "requires_fetch": True,
        }

        realtime_outbox_event_count = 0
        phase_started_at = time.perf_counter()
        with profile_database_stage("outbox"):
            if (
                not recipient_delivery_blocked
                and recipient_device_ids
            ):
                websocket_payload = build_event(
                    MESSAGE_STORED,
                    realtime_event_payload,
                )
                outbox_events = []

                for recipient_device_id in recipient_device_ids:
                    target_group = make_device_group_name(
                        recipient_device_id,
                    )
                    outbox_events.append(
                        RealtimeOutboxCreateSpec(
                            event_type=MESSAGE_STORED,
                            target_group=target_group,
                            payload=websocket_payload,
                            event_key=build_direct_message_stored_event_key(
                                message_id=message.id,
                                target_group=target_group,
                            ),
                        )
                    )

                realtime_outbox_event_count = (
                    enqueue_new_realtime_outbox_events_sync(
                        outbox_events,
                    )
               )

        profile_checkpoint(
            profile_timings_ms,
            "service_realtime_outbox_persist",
            phase_started_at,
        )
        
    except ValidationError as error:
        raise DirectMessageValidationError(
            error.message_dict
            if hasattr(error, "message_dict")
            else error.messages
        ) from error

    profile_checkpoint(
        profile_timings_ms,
        "service_total",
        total_started_at,
    )

    return DirectMessageResult(
        room=room,
        message=message,
        room_created=room_created,
        message_created=True,
        envelope_count=len(envelope_models),
        recipient_delivery_blocked=recipient_delivery_blocked,
        recipient_device_ids=recipient_device_ids,
        realtime_event_payload=realtime_event_payload,
        realtime_outbox_event_count=realtime_outbox_event_count,
        profile_timings_ms=profile_timings_ms,
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

import json
import time
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from django.db import IntegrityError, transaction
from apps.e2ee_devices.recovery_services import (
    get_active_recovery_versions_for_users,
)

from .models import MessageRecoveryEnvelope
from .services import (
    direct_send_profile_enabled,
    profile_checkpoint,
    profile_database_stage,
    send_direct_message,
)
from .policy_services import get_delivery_policy_snapshot

class RecoveryEnvelopeValidationError(Exception):
    """Raised when required recovery envelopes are invalid."""


class RecoveryEnvelopeConflictError(Exception):
    """Raised when an idempotent retry changes recovery data."""

@dataclass(frozen=True)
class RecoveryAwareDirectMessageResult:
    room: Any
    message: Any
    room_created: bool
    message_created: bool
    envelope_count: int
    recovery_envelope_count: int
    recipient_delivery_blocked: bool = False
    recipient_device_ids: tuple[str, ...] = ()
    realtime_event_payload: dict[str, Any] | None = None
    realtime_outbox_event_count: int = 0
    profile_timings_ms: dict[str, float] | None = None


def _canonical_json(value: dict) -> str:
    return json.dumps(
        value,
        separators=(",", ":"),
        sort_keys=True,
    )


def _normalize_recovery_envelopes(
    recovery_envelopes: list[dict] | None,
) -> list[dict]:
    normalized = []

    for envelope in recovery_envelopes or []:
        normalized.append(
            {
                "recovery_owner_user_id": str(
                    envelope["recovery_owner_user_id"]
                ),
                "recovery_key_version": int(
                    envelope["recovery_key_version"]
                ),
                "wrapped_message_key": envelope[
                    "wrapped_message_key"
                ],
                "key_wrap_metadata": envelope[
                    "key_wrap_metadata"
                ],
                "envelope_version": int(
                    envelope.get(
                        "envelope_version",
                        1,
                    )
                ),
            }
        )

    return normalized




def _validate_recovery_envelopes(
    *,
    sender_user_id: str,
    recipient_user_id: str,
    recovery_envelopes: list[dict],
    active_recovery_versions: dict[str, int],
) -> None:
    participant_ids = {
        str(sender_user_id),
        str(recipient_user_id),
    }

    provided_owner_ids = [
        envelope["recovery_owner_user_id"]
        for envelope in recovery_envelopes
    ]

    if len(provided_owner_ids) != len(
        set(provided_owner_ids)
    ):
        raise RecoveryEnvelopeValidationError(
            "Duplicate recovery envelope owners are not allowed."
        )

    unexpected_owner_ids = sorted(
        set(provided_owner_ids).difference(participant_ids)
    )

    if unexpected_owner_ids:
        raise RecoveryEnvelopeValidationError(
            "Recovery envelopes contain unexpected owners: "
            + ", ".join(unexpected_owner_ids)
            + "."
        )

    expected_owner_ids = set(active_recovery_versions)
    actual_owner_ids = set(provided_owner_ids)

    missing_owner_ids = sorted(
        expected_owner_ids.difference(actual_owner_ids)
    )

    if missing_owner_ids:
        raise RecoveryEnvelopeValidationError(
            "Recovery envelopes are missing for these users: "
            + ", ".join(missing_owner_ids)
            + "."
        )

    inactive_owner_ids = sorted(
        actual_owner_ids.difference(expected_owner_ids)
    )

    if inactive_owner_ids:
        raise RecoveryEnvelopeValidationError(
            "Recovery envelopes were supplied for users without "
            "active recovery: "
            + ", ".join(inactive_owner_ids)
            + "."
        )

    for envelope in recovery_envelopes:
        owner_id = envelope["recovery_owner_user_id"]

        if (
            envelope["recovery_key_version"]
            != active_recovery_versions[owner_id]
        ):
            raise RecoveryEnvelopeValidationError(
                "Recovery envelope key version does not match "
                f"the active bundle for user {owner_id}."
            )



def _active_recovery_bundle_exists(
    *,
    participant_ids: set[str],
) -> bool:
    return bool(
        get_active_recovery_versions_for_users(participant_ids)
    )


def _stored_recovery_envelopes_match(
    *,
    message,
    recovery_envelopes: list[dict],
) -> bool:
    stored = list(
        message.recovery_envelopes.order_by(
            "recovery_owner_user_id"
        )
    )

    requested = sorted(
        recovery_envelopes,
        key=lambda item: item[
            "recovery_owner_user_id"
        ],
    )

    if len(stored) != len(requested):
        return False

    for stored_item, requested_item in zip(
        stored,
        requested,
        strict=True,
    ):
        if (
            stored_item.recovery_owner_user_id
            != requested_item[
                "recovery_owner_user_id"
            ]
            or stored_item.recovery_key_version
            != requested_item[
                "recovery_key_version"
            ]
            or stored_item.wrapped_message_key
            != requested_item[
                "wrapped_message_key"
            ]
            or _canonical_json(
                stored_item.key_wrap_metadata
            )
            != _canonical_json(
                requested_item[
                    "key_wrap_metadata"
                ]
            )
            or stored_item.envelope_version
            != requested_item["envelope_version"]
        ):
            return False

    return True



@dataclass(frozen=True, slots=True)
class RecoverySendPreparation:
    normalized_recovery_envelopes: list[dict]
    delivery_policy_snapshot: Any
    recovery_recipient_user_id: str
    active_recovery_versions: dict[str, int]


def _prepare_recovery_send(
    *,
    sender_user_id: str,
    recipient_user_id: str,
    recovery_envelopes: list[dict] | None,
    profile_timings_ms: dict[str, float] | None,
) -> RecoverySendPreparation:
    phase_started_at = time.perf_counter()

    normalized_recovery_envelopes = _normalize_recovery_envelopes(
        recovery_envelopes
    )

    profile_checkpoint(
        profile_timings_ms,
        "recovery_normalize_input",
        phase_started_at,
    )

    phase_started_at = time.perf_counter()

    with profile_database_stage("recovery"):
        delivery_policy_snapshot = get_delivery_policy_snapshot(
            recipient_user_id=str(recipient_user_id),
            sender_user_id=str(sender_user_id),
        )

    profile_checkpoint(
        profile_timings_ms,
        "recovery_policy_snapshot",
        phase_started_at,
    )

    recipient_delivery_blocked = delivery_policy_snapshot.is_blocked

    if recipient_delivery_blocked:
        normalized_recovery_envelopes = [
            envelope
            for envelope in normalized_recovery_envelopes
            if envelope["recovery_owner_user_id"]
            == str(sender_user_id)
        ]

    recovery_recipient_user_id = (
        str(sender_user_id)
        if recipient_delivery_blocked
        else str(recipient_user_id)
    )

    recovery_participant_ids = {
        str(sender_user_id),
        recovery_recipient_user_id,
    }

    phase_started_at = time.perf_counter()

    with profile_database_stage("recovery"):
        active_recovery_versions = (
            get_active_recovery_versions_for_users(
                recovery_participant_ids
            )
        )

    profile_checkpoint(
        profile_timings_ms,
        "recovery_bundle_check",
        phase_started_at,
    )

    recovery_required = bool(
        normalized_recovery_envelopes
        or active_recovery_versions
    )

    if recovery_required:
        phase_started_at = time.perf_counter()

        _validate_recovery_envelopes(
            sender_user_id=str(sender_user_id),
            recipient_user_id=recovery_recipient_user_id,
            recovery_envelopes=normalized_recovery_envelopes,
            active_recovery_versions=active_recovery_versions,
        )

        profile_checkpoint(
            profile_timings_ms,
            "recovery_validate_envelopes",
            phase_started_at,
        )

    elif profile_timings_ms is not None:
        profile_timings_ms[
            "recovery_validate_envelopes"
        ] = 0.0

    return RecoverySendPreparation(
        normalized_recovery_envelopes=normalized_recovery_envelopes,
        delivery_policy_snapshot=delivery_policy_snapshot,
        recovery_recipient_user_id=recovery_recipient_user_id,
        active_recovery_versions=active_recovery_versions,
    )


@transaction.atomic
def _send_direct_message_with_recovery_transaction(
    *,
    preparation: RecoverySendPreparation,
    direct_message_kwargs: dict[str, Any],
    profile_timings_ms: dict[str, float] | None,
    defer_idempotency_retry_to_outer_transaction: bool,
):
    phase_started_at = time.perf_counter()

    with profile_database_stage("direct_send"):
        base_result = send_direct_message(
            delivery_policy_snapshot=(
                preparation.delivery_policy_snapshot
            ),
            profile_timings_ms=profile_timings_ms,
            defer_idempotency_retry_to_outer_transaction=(
                defer_idempotency_retry_to_outer_transaction
            ),
            **direct_message_kwargs,
        )

    profile_checkpoint(
        profile_timings_ms,
        "recovery_base_send_total",
        phase_started_at,
    )

    if base_result.message_created:
        phase_started_at = time.perf_counter()

        with profile_database_stage("recovery"):
            recovery_models = [
                MessageRecoveryEnvelope(
                    message=base_result.message,
                    recovery_owner_user_id=envelope[
                        "recovery_owner_user_id"
                    ],
                    recovery_key_version=envelope[
                        "recovery_key_version"
                    ],
                    wrapped_message_key=envelope[
                        "wrapped_message_key"
                    ],
                    key_wrap_metadata=envelope[
                        "key_wrap_metadata"
                    ],
                    envelope_version=envelope[
                        "envelope_version"
                    ],
                )
                for envelope in (
                    preparation.normalized_recovery_envelopes
                )
            ]

            MessageRecoveryEnvelope.objects.bulk_create(
                recovery_models
            )

        profile_checkpoint(
            profile_timings_ms,
            "recovery_envelope_bulk_insert",
            phase_started_at,
        )

    elif not _stored_recovery_envelopes_match(
        message=base_result.message,
        recovery_envelopes=(
            preparation.normalized_recovery_envelopes
        ),
    ):
        raise RecoveryEnvelopeConflictError(
            "This client_message_id was already used with "
            "different recovery envelope data."
        )

    return base_result


def send_direct_message_with_recovery(
    *,
    sender_user_id: str,
    recipient_user_id: str,
    sender_device_id: UUID,
    client_message_id: UUID,
    message_type: str,
    encrypted_payload: str,
    encryption_metadata: dict,
    encryption_version: int,
    envelopes: list[dict],
    recovery_envelopes: list[dict] | None = None,
    reply_to_id: UUID | None = None,
    client_sent_at=None,
    attachment_ids: list | None = None,
    sender_contact_validated_by_identity: bool = False,
    identity_contact_id=None,
    existing_room=None,
    require_saved_contact: bool = False,
    profile_timings_ms: dict[str, float] | None = None,
) -> RecoveryAwareDirectMessageResult:
    """Store a recovery-aware direct message with a short write transaction.

    Recovery policy/version reads and envelope validation happen before the
    write transaction. The normal success path inserts the message without a
    nested savepoint. A rare duplicate-client-message race is retried after
    the first transaction has fully rolled back.
    """
    if (
        profile_timings_ms is None
        and direct_send_profile_enabled()
    ):
        profile_timings_ms = {}

    total_started_at = time.perf_counter()

    preparation = _prepare_recovery_send(
        sender_user_id=sender_user_id,
        recipient_user_id=recipient_user_id,
        recovery_envelopes=recovery_envelopes,
        profile_timings_ms=profile_timings_ms,
    )

    direct_message_kwargs = {
        "sender_user_id": str(sender_user_id),
        "recipient_user_id": str(recipient_user_id),
        "sender_device_id": sender_device_id,
        "client_message_id": client_message_id,
        "message_type": message_type,
        "encrypted_payload": encrypted_payload,
        "encryption_metadata": encryption_metadata,
        "encryption_version": encryption_version,
        "envelopes": envelopes,
        "reply_to_id": reply_to_id,
        "client_sent_at": client_sent_at,
        "attachment_ids": attachment_ids,
        "sender_contact_validated_by_identity": (
            sender_contact_validated_by_identity
        ),
        "identity_contact_id": identity_contact_id,
        "existing_room": existing_room,
        "require_saved_contact": require_saved_contact,
    }

    try:
        base_result = (
            _send_direct_message_with_recovery_transaction(
                preparation=preparation,
                direct_message_kwargs=direct_message_kwargs,
                profile_timings_ms=profile_timings_ms,
                defer_idempotency_retry_to_outer_transaction=True,
            )
        )

    except IntegrityError:
        base_result = (
            _send_direct_message_with_recovery_transaction(
                preparation=preparation,
                direct_message_kwargs=direct_message_kwargs,
                profile_timings_ms=profile_timings_ms,
                defer_idempotency_retry_to_outer_transaction=False,
            )
        )

    profile_checkpoint(
        profile_timings_ms,
        "recovery_total",
        total_started_at,
    )

    return RecoveryAwareDirectMessageResult(
        room=base_result.room,
        message=base_result.message,
        room_created=base_result.room_created,
        message_created=base_result.message_created,
        envelope_count=base_result.envelope_count,
        recovery_envelope_count=len(
            preparation.normalized_recovery_envelopes
        ),
        recipient_delivery_blocked=(
            base_result.recipient_delivery_blocked
        ),
        recipient_device_ids=base_result.recipient_device_ids,
        realtime_event_payload=base_result.realtime_event_payload,
        realtime_outbox_event_count=(
            base_result.realtime_outbox_event_count
        ),
        profile_timings_ms=profile_timings_ms,
    )
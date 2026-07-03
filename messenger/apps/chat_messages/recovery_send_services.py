import json
import time
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from django.db import transaction
from apps.e2ee_devices.models import RecoveryBundle
from apps.e2ee_devices.recovery_services import (
    recovery_bundle_is_active_for_user,
)

from .models import MessageRecoveryEnvelope
from .services import (
    direct_send_profile_enabled,
    profile_checkpoint,
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
) -> dict[str, RecoveryBundle]:
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

    active_bundles = {
        bundle.user_id: bundle
        for bundle in (
            RecoveryBundle.objects.filter(
                user_id__in=participant_ids,
                is_active=True,
                disabled_at__isnull=True,
            )
        )
    }

    expected_owner_ids = set(active_bundles)
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
        bundle = active_bundles[owner_id]

        if (
            envelope["recovery_key_version"]
            != bundle.recovery_version
        ):
            raise RecoveryEnvelopeValidationError(
                "Recovery envelope key version does not match "
                f"the active bundle for user {owner_id}."
            )

    return active_bundles

def _active_recovery_bundle_exists(
    *,
    participant_ids: set[str],
) -> bool:
    return any(
        recovery_bundle_is_active_for_user(user_id)
        for user_id in participant_ids
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

@transaction.atomic
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
) -> RecoveryAwareDirectMessageResult:
    """
    Store the direct message, normal device envelopes, and optional
    mandatory recovery envelopes in one database transaction.

    If the recipient has blocked the sender, recipient delivery is blocked.
    In that case, recovery envelopes for the recipient are ignored and only
    sender-owned recovery envelopes are allowed.
    """
    profile_timings_ms = (
        {}
        if direct_send_profile_enabled()
        else None
    )
    total_started_at = time.perf_counter()

    phase_started_at = time.perf_counter()
    normalized_recovery_envelopes = (
        _normalize_recovery_envelopes(
            recovery_envelopes
        )
    )
    profile_checkpoint(
        profile_timings_ms,
        "recovery_normalize_input",
        phase_started_at,
    )

    phase_started_at = time.perf_counter()
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
    recovery_required = (
        normalized_recovery_envelopes
        or _active_recovery_bundle_exists(
            participant_ids=recovery_participant_ids,
        )
    )
    profile_checkpoint(
        profile_timings_ms,
        "recovery_bundle_check",
        phase_started_at,
    )

    if recovery_required:
        phase_started_at = time.perf_counter()
        _validate_recovery_envelopes(
            sender_user_id=str(sender_user_id),
            recipient_user_id=recovery_recipient_user_id,
            recovery_envelopes=(
                normalized_recovery_envelopes
            ),
        )
        profile_checkpoint(
            profile_timings_ms,
            "recovery_validate_envelopes",
            phase_started_at,
        )

    phase_started_at = time.perf_counter()
    base_result = send_direct_message(
        sender_user_id=str(sender_user_id),
        recipient_user_id=str(recipient_user_id),
        sender_device_id=sender_device_id,
        client_message_id=client_message_id,
        message_type=message_type,
        encrypted_payload=encrypted_payload,
        encryption_metadata=encryption_metadata,
        encryption_version=encryption_version,
        envelopes=envelopes,
        reply_to_id=reply_to_id,
        client_sent_at=client_sent_at,
        attachment_ids=attachment_ids,
        sender_contact_validated_by_identity=(
            sender_contact_validated_by_identity
        ),
        identity_contact_id=identity_contact_id,
        existing_room=existing_room,
        delivery_policy_snapshot=delivery_policy_snapshot,
        require_saved_contact=require_saved_contact,
        profile_timings_ms=profile_timings_ms,
    )
    profile_checkpoint(
        profile_timings_ms,
        "recovery_base_send_total",
        phase_started_at,
    )

    if base_result.message_created:
        phase_started_at = time.perf_counter()
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
                normalized_recovery_envelopes
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
            normalized_recovery_envelopes
        ),
    ):
        raise RecoveryEnvelopeConflictError(
            "This client_message_id was already used with "
            "different recovery envelope data."
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
            normalized_recovery_envelopes
        ),
        recipient_delivery_blocked=(
            base_result.recipient_delivery_blocked
        ),
        recipient_device_ids=base_result.recipient_device_ids,
        realtime_event_payload=base_result.realtime_event_payload,
        profile_timings_ms=profile_timings_ms,
    )

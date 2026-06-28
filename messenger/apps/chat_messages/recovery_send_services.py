import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from django.db import transaction

from apps.e2ee_devices.models import RecoveryBundle

from .models import MessageRecoveryEnvelope
from .services import send_direct_message
from .policy_services import recipient_has_blocked_sender

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
            RecoveryBundle.objects.select_for_update()
            .filter(
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
) -> RecoveryAwareDirectMessageResult:
    """
    Store the direct message, normal device envelopes, and optional
    mandatory recovery envelopes in one database transaction.

    If the recipient has blocked the sender, recipient delivery is blocked.
    In that case, recovery envelopes for the recipient are ignored and only
    sender-owned recovery envelopes are allowed.
    """

    normalized_recovery_envelopes = (
        _normalize_recovery_envelopes(
            recovery_envelopes
        )
    )

    recipient_delivery_blocked = recipient_has_blocked_sender(
        recipient_user_id=str(recipient_user_id),
        sender_user_id=str(sender_user_id),
    )

    if recipient_delivery_blocked:
        normalized_recovery_envelopes = [
            envelope
            for envelope in normalized_recovery_envelopes
            if envelope["recovery_owner_user_id"]
            == str(sender_user_id)
        ]

    _validate_recovery_envelopes(
        sender_user_id=str(sender_user_id),
        recipient_user_id=(
            str(sender_user_id)
            if recipient_delivery_blocked
            else str(recipient_user_id)
        ),
        recovery_envelopes=(
            normalized_recovery_envelopes
        ),
    )

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
    )

    if base_result.message_created:
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

        for recovery_model in recovery_models:
            recovery_model.full_clean()

        MessageRecoveryEnvelope.objects.bulk_create(
            recovery_models
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
    )
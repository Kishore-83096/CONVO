import json
from dataclasses import dataclass
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.chat_messages.models import (
    MessageRecoveryEnvelope,
)

from .models import RecoveryBundle


class RecoveryRotationUnavailableError(Exception):
    """Raised when no active recovery bundle exists."""


class RecoveryRotationConflictError(Exception):
    """Raised for stale or conflicting rotation requests."""


class RecoveryRotationValidationError(Exception):
    """Raised when recovery-envelope coverage is invalid."""


@dataclass(frozen=True)
class RecoveryRotationResult:
    bundle: RecoveryBundle
    rotated_envelope_count: int
    rotation_applied: bool


@dataclass(frozen=True)
class RecoveryDisableResult:
    bundle_deleted: bool
    deleted_recovery_envelope_count: int


def _canonical_json(value: dict) -> str:
    return json.dumps(
        value,
        separators=(",", ":"),
        sort_keys=True,
    )


def _normalize_rotation_envelopes(
    recovery_envelopes: list[dict],
) -> list[dict]:
    return [
        {
            "message_id": item["message_id"],
            "wrapped_message_key": item[
                "wrapped_message_key"
            ],
            "key_wrap_metadata": item[
                "key_wrap_metadata"
            ],
            "envelope_version": int(
                item.get("envelope_version", 1)
            ),
        }
        for item in recovery_envelopes
    ]


def _bundle_matches_rotation_request(
    *,
    bundle: RecoveryBundle,
    recovery_public_key: str,
    encrypted_recovery_private_key: str,
    encryption_metadata: dict,
    target_version: int,
) -> bool:
    return (
        bundle.recovery_version == target_version
        and bundle.recovery_public_key
        == recovery_public_key
        and bundle.encrypted_recovery_private_key
        == encrypted_recovery_private_key
        and _canonical_json(
            bundle.encryption_metadata
        )
        == _canonical_json(encryption_metadata)
        and bundle.is_active
        and bundle.disabled_at is None
    )


def _stored_envelopes_match_rotation_request(
    *,
    user_id: str,
    target_version: int,
    recovery_envelopes: list[dict],
) -> bool:
    stored = list(
        MessageRecoveryEnvelope.objects.filter(
            recovery_owner_user_id=user_id,
        ).order_by("message_id")
    )

    requested = sorted(
        recovery_envelopes,
        key=lambda item: str(item["message_id"]),
    )

    if len(stored) != len(requested):
        return False

    for stored_item, requested_item in zip(
        stored,
        requested,
        strict=True,
    ):
        if (
            stored_item.message_id
            != requested_item["message_id"]
            or stored_item.recovery_key_version
            != target_version
            or stored_item.wrapped_message_key
            != requested_item["wrapped_message_key"]
            or _canonical_json(
                stored_item.key_wrap_metadata
            )
            != _canonical_json(
                requested_item["key_wrap_metadata"]
            )
            or stored_item.envelope_version
            != requested_item["envelope_version"]
        ):
            return False

    return True


def _validate_complete_envelope_coverage(
    *,
    user_id: str,
    current_envelopes: list[
        MessageRecoveryEnvelope
    ],
    requested_envelopes: list[dict],
) -> None:
    current_message_ids = {
        envelope.message_id
        for envelope in current_envelopes
    }
    requested_message_ids = {
        envelope["message_id"]
        for envelope in requested_envelopes
    }

    missing_message_ids = sorted(
        current_message_ids.difference(
            requested_message_ids
        ),
        key=str,
    )
    unexpected_message_ids = sorted(
        requested_message_ids.difference(
            current_message_ids
        ),
        key=str,
    )

    if missing_message_ids:
        raise RecoveryRotationValidationError(
            "Rotated recovery envelopes are missing for "
            "these messages: "
            + ", ".join(
                str(message_id)
                for message_id in missing_message_ids
            )
            + "."
        )

    if unexpected_message_ids:
        raise RecoveryRotationValidationError(
            "Rotated recovery envelopes are unavailable "
            "for these messages: "
            + ", ".join(
                str(message_id)
                for message_id in unexpected_message_ids
            )
            + "."
        )


@transaction.atomic
def rotate_recovery_bundle(
    *,
    user_id: str,
    current_recovery_version: int,
    recovery_public_key: str,
    encrypted_recovery_private_key: str,
    encryption_metadata: dict,
    recovery_envelopes: list[dict],
) -> RecoveryRotationResult:
    """
    Atomically replace the user's recovery keypair and every
    existing user-owned recovery envelope.

    No plaintext key material is processed by the server.
    """

    normalized_user_id = str(user_id)
    normalized_envelopes = (
        _normalize_rotation_envelopes(
            recovery_envelopes
        )
    )
    target_version = current_recovery_version + 1

    bundle = (
        RecoveryBundle.objects.select_for_update()
        .filter(
            user_id=normalized_user_id,
            is_active=True,
            disabled_at__isnull=True,
        )
        .first()
    )

    if bundle is None:
        raise RecoveryRotationUnavailableError(
            "Encrypted recovery is not available."
        )

    if bundle.recovery_version != current_recovery_version:
        if (
            _bundle_matches_rotation_request(
                bundle=bundle,
                recovery_public_key=recovery_public_key,
                encrypted_recovery_private_key=(
                    encrypted_recovery_private_key
                ),
                encryption_metadata=encryption_metadata,
                target_version=target_version,
            )
            and _stored_envelopes_match_rotation_request(
                user_id=normalized_user_id,
                target_version=target_version,
                recovery_envelopes=normalized_envelopes,
            )
        ):
            return RecoveryRotationResult(
                bundle=bundle,
                rotated_envelope_count=len(
                    normalized_envelopes
                ),
                rotation_applied=False,
            )

        raise RecoveryRotationConflictError(
            "The recovery bundle version changed before "
            "this rotation could be applied."
        )

    if bundle.recovery_public_key == recovery_public_key:
        raise RecoveryRotationValidationError(
            "A full recovery rotation requires a new "
            "recovery public key."
        )

    current_envelopes = list(
        MessageRecoveryEnvelope.objects.select_for_update()
        .filter(
            recovery_owner_user_id=normalized_user_id,
        )
        .order_by("message_id")
    )

    _validate_complete_envelope_coverage(
        user_id=normalized_user_id,
        current_envelopes=current_envelopes,
        requested_envelopes=normalized_envelopes,
    )

    requested_by_message_id = {
        item["message_id"]: item
        for item in normalized_envelopes
    }

    now = timezone.now()

    for stored_envelope in current_envelopes:
        requested = requested_by_message_id[
            stored_envelope.message_id
        ]

        stored_envelope.recovery_key_version = (
            target_version
        )
        stored_envelope.wrapped_message_key = requested[
            "wrapped_message_key"
        ]
        stored_envelope.key_wrap_metadata = requested[
            "key_wrap_metadata"
        ]
        stored_envelope.envelope_version = requested[
            "envelope_version"
        ]
        stored_envelope.updated_at = now
        stored_envelope.full_clean()

    if current_envelopes:
        MessageRecoveryEnvelope.objects.bulk_update(
            current_envelopes,
            fields=[
                "recovery_key_version",
                "wrapped_message_key",
                "key_wrap_metadata",
                "envelope_version",
                "updated_at",
            ],
        )

    bundle.recovery_public_key = recovery_public_key
    bundle.encrypted_recovery_private_key = (
        encrypted_recovery_private_key
    )
    bundle.encryption_metadata = encryption_metadata
    bundle.recovery_version = target_version
    bundle.rotated_at = now

    bundle.full_clean()
    bundle.save(
        update_fields=[
            "recovery_public_key",
            "encrypted_recovery_private_key",
            "encryption_metadata",
            "recovery_version",
            "rotated_at",
            "updated_at",
        ]
    )

    return RecoveryRotationResult(
        bundle=bundle,
        rotated_envelope_count=len(
            current_envelopes
        ),
        rotation_applied=True,
    )


@transaction.atomic
def disable_recovery(
    *,
    user_id: str,
) -> RecoveryDisableResult:
    """
    Permanently remove cloud recovery material for the user.

    Messages and normal per-device envelopes remain intact.
    """

    normalized_user_id = str(user_id)

    bundle = (
        RecoveryBundle.objects.select_for_update()
        .filter(user_id=normalized_user_id)
        .first()
    )

    deleted_envelope_count, _ = (
        MessageRecoveryEnvelope.objects.filter(
            recovery_owner_user_id=normalized_user_id,
        ).delete()
    )

    if bundle is None:
        return RecoveryDisableResult(
            bundle_deleted=False,
            deleted_recovery_envelope_count=(
                deleted_envelope_count
            ),
        )

    bundle.delete()

    return RecoveryDisableResult(
        bundle_deleted=True,
        deleted_recovery_envelope_count=(
            deleted_envelope_count
        ),
    )

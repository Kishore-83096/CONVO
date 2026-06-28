import json
from dataclasses import dataclass
from uuid import UUID

from django.db import transaction
from django.db.models import Prefetch, QuerySet

from apps.e2ee_devices.models import Device, RecoveryBundle

from .models import (
    Message,
    MessageKeyEnvelope,
    MessageRecoveryEnvelope,
)


class RecoveryAccessError(Exception):
    """Raised when encrypted recovery is unavailable."""


class RecoveryDeviceAccessError(Exception):
    """Raised when the target device is not an active owned device."""


class RecoveryEnvelopeAccessError(Exception):
    """Raised when a message is not recoverable by this user."""


class RecoveryRewrapConflictError(Exception):
    """Raised when an existing device envelope differs."""


@dataclass(frozen=True)
class RecoveryRewrapResult:
    device: Device
    created_count: int
    existing_count: int
    total_count: int


def require_active_recovery_bundle(
    *,
    user_id: str,
) -> RecoveryBundle:
    bundle = RecoveryBundle.objects.filter(
        user_id=str(user_id),
        is_active=True,
        disabled_at__isnull=True,
    ).first()

    if bundle is None:
        raise RecoveryAccessError(
            "Encrypted recovery is unavailable."
        )

    return bundle


def get_recovery_history_queryset(
    *,
    user_id: str,
) -> QuerySet:
    normalized_user_id = str(user_id)
    require_active_recovery_bundle(
        user_id=normalized_user_id,
    )

    requested_envelopes = (
        MessageRecoveryEnvelope.objects.filter(
            recovery_owner_user_id=normalized_user_id,
        )
    )

    return (
        Message.objects.filter(
            recovery_envelopes__recovery_owner_user_id=(
                normalized_user_id
            ),
        )
        .select_related(
            "room",
            "reply_to",
        )
        .prefetch_related(
            Prefetch(
                "recovery_envelopes",
                queryset=requested_envelopes,
                to_attr="requested_recovery_envelopes",
            )
        )
        .order_by(
            "-created_at",
            "-id",
        )
    )


def _canonical_json(value: dict) -> str:
    return json.dumps(
        value,
        separators=(",", ":"),
        sort_keys=True,
    )


def _existing_envelope_matches(
    *,
    envelope: MessageKeyEnvelope,
    user_id: str,
    wrapped_message_key: str,
    key_wrap_metadata: dict,
    envelope_version: int,
) -> bool:
    return (
        envelope.recipient_user_id == str(user_id)
        and envelope.protocol == "device_sync"
        and envelope.wrapped_message_key
        == wrapped_message_key
        and _canonical_json(envelope.key_wrap_metadata)
        == _canonical_json(key_wrap_metadata)
        and envelope.envelope_version
        == envelope_version
    )


@transaction.atomic
def rewrap_recovery_messages_for_device(
    *,
    user_id: str,
    device_id: UUID,
    envelopes: list[dict],
) -> RecoveryRewrapResult:
    normalized_user_id = str(user_id)

    require_active_recovery_bundle(
        user_id=normalized_user_id,
    )

    device = (
        Device.objects.select_for_update()
        .filter(
            id=device_id,
            user_id=normalized_user_id,
            is_active=True,
        )
        .first()
    )

    if device is None:
        raise RecoveryDeviceAccessError(
            "The recovery target device is unavailable."
        )

    message_ids = [
        envelope["message_id"]
        for envelope in envelopes
    ]

    messages = {
        message.id: message
        for message in (
            Message.objects.select_for_update()
            .filter(id__in=message_ids)
        )
    }

    authorized_message_ids = set(
        MessageRecoveryEnvelope.objects.filter(
            message_id__in=message_ids,
            recovery_owner_user_id=normalized_user_id,
        ).values_list(
            "message_id",
            flat=True,
        )
    )

    missing_or_unauthorized = [
        str(message_id)
        for message_id in message_ids
        if (
            message_id not in messages
            or message_id not in authorized_message_ids
        )
    ]

    if missing_or_unauthorized:
        raise RecoveryEnvelopeAccessError(
            "Recovery envelopes are unavailable for these "
            "messages: "
            + ", ".join(missing_or_unauthorized)
            + "."
        )

    existing_by_message_id = {
        envelope.message_id: envelope
        for envelope in (
            MessageKeyEnvelope.objects.select_for_update()
            .filter(
                message_id__in=message_ids,
                recipient_device=device,
            )
        )
    }

    created_count = 0
    existing_count = 0

    for envelope_input in envelopes:
        message_id = envelope_input["message_id"]
        existing = existing_by_message_id.get(message_id)

        if existing is not None:
            if not _existing_envelope_matches(
                envelope=existing,
                user_id=normalized_user_id,
                wrapped_message_key=(
                    envelope_input["wrapped_message_key"]
                ),
                key_wrap_metadata=(
                    envelope_input["key_wrap_metadata"]
                ),
                envelope_version=(
                    envelope_input["envelope_version"]
                ),
            ):
                raise RecoveryRewrapConflictError(
                    "A different device envelope already exists "
                    f"for message {message_id}."
                )

            existing_count += 1
            continue

        new_envelope = MessageKeyEnvelope(
            message=messages[message_id],
            recipient_user_id=normalized_user_id,
            recipient_device=device,
            protocol="device_sync",
            session_reference=(
                f"recovery:{device.id}:{message_id}"
            ),
            wrapped_message_key=(
                envelope_input["wrapped_message_key"]
            ),
            key_wrap_metadata=(
                envelope_input["key_wrap_metadata"]
            ),
            envelope_version=(
                envelope_input["envelope_version"]
            ),
        )
        new_envelope.full_clean()
        new_envelope.save()

        created_count += 1

    return RecoveryRewrapResult(
        device=device,
        created_count=created_count,
        existing_count=existing_count,
        total_count=len(envelopes),
    )

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


class RecoveryBackfillUnavailableError(Exception):
    """Raised when active encrypted recovery is unavailable."""


class RecoveryBackfillDeviceError(Exception):
    """Raised when the selected device is not active and owned."""


class RecoveryBackfillAccessError(Exception):
    """Raised when one or more messages cannot be backfilled."""


class RecoveryBackfillConflictError(Exception):
    """Raised for stale versions or changed idempotent retries."""


@dataclass(frozen=True)
class RecoveryBackfillCandidateResult:
    bundle: RecoveryBundle
    device: Device
    messages: QuerySet


@dataclass(frozen=True)
class RecoveryBackfillResult:
    bundle: RecoveryBundle
    device: Device
    created_count: int
    existing_count: int
    total_count: int


def _canonical_json(value: dict) -> str:
    return json.dumps(
        value,
        separators=(",", ":"),
        sort_keys=True,
    )


def _get_active_bundle(
    *,
    user_id: str,
    lock: bool = False,
) -> RecoveryBundle:
    queryset = RecoveryBundle.objects

    if lock:
        queryset = queryset.select_for_update()

    bundle = queryset.filter(
        user_id=str(user_id),
        is_active=True,
        disabled_at__isnull=True,
    ).first()

    if bundle is None:
        raise RecoveryBackfillUnavailableError(
            "Encrypted recovery is unavailable."
        )

    return bundle


def _get_active_owned_device(
    *,
    user_id: str,
    device_id: UUID,
    lock: bool = False,
) -> Device:
    queryset = Device.objects

    if lock:
        queryset = queryset.select_for_update()

    device = queryset.filter(
        id=device_id,
        user_id=str(user_id),
        is_active=True,
    ).first()

    if device is None:
        raise RecoveryBackfillDeviceError(
            "The recovery backfill device is unavailable."
        )

    return device


def get_recovery_backfill_candidates(
    *,
    user_id: str,
    device_id: UUID,
) -> RecoveryBackfillCandidateResult:
    normalized_user_id = str(user_id)

    bundle = _get_active_bundle(
        user_id=normalized_user_id,
    )
    device = _get_active_owned_device(
        user_id=normalized_user_id,
        device_id=device_id,
    )

    requesting_device_envelopes = (
        MessageKeyEnvelope.objects.filter(
            recipient_user_id=normalized_user_id,
            recipient_device=device,
        )
        .order_by("created_at", "id")
    )

    messages = (
        Message.objects.filter(
            room__is_active=True,
            room__members__user_id=normalized_user_id,
            room__members__is_active=True,
            key_envelopes__recipient_user_id=(
                normalized_user_id
            ),
            key_envelopes__recipient_device=device,
        )
        .exclude(
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
                "key_envelopes",
                queryset=requesting_device_envelopes,
                to_attr=(
                    "requesting_device_envelopes"
                ),
            )
        )
        .distinct()
        .order_by("-created_at", "-id")
    )

    return RecoveryBackfillCandidateResult(
        bundle=bundle,
        device=device,
        messages=messages,
    )


def _existing_envelope_matches(
    *,
    envelope: MessageRecoveryEnvelope,
    recovery_key_version: int,
    wrapped_message_key: str,
    key_wrap_metadata: dict,
    envelope_version: int,
) -> bool:
    return (
        envelope.recovery_key_version
        == recovery_key_version
        and envelope.wrapped_message_key
        == wrapped_message_key
        and _canonical_json(
            envelope.key_wrap_metadata
        )
        == _canonical_json(key_wrap_metadata)
        and envelope.envelope_version
        == envelope_version
    )


@transaction.atomic
def backfill_recovery_envelopes(
    *,
    user_id: str,
    device_id: UUID,
    recovery_key_version: int,
    envelopes: list[dict],
) -> RecoveryBackfillResult:
    normalized_user_id = str(user_id)

    bundle = _get_active_bundle(
        user_id=normalized_user_id,
        lock=True,
    )

    if bundle.recovery_version != recovery_key_version:
        raise RecoveryBackfillConflictError(
            "The recovery key version changed before "
            "this backfill could be applied."
        )

    device = _get_active_owned_device(
        user_id=normalized_user_id,
        device_id=device_id,
        lock=True,
    )

    message_ids = [
        item["message_id"]
        for item in envelopes
    ]

    authorized_messages = {
        message.id: message
        for message in (
            Message.objects.select_for_update()
            .filter(
                id__in=message_ids,
                room__is_active=True,
                room__members__user_id=(
                    normalized_user_id
                ),
                room__members__is_active=True,
                key_envelopes__recipient_user_id=(
                    normalized_user_id
                ),
                key_envelopes__recipient_device=device,
            )
            .distinct()
        )
    }

    unavailable_message_ids = [
        str(message_id)
        for message_id in message_ids
        if message_id not in authorized_messages
    ]

    if unavailable_message_ids:
        raise RecoveryBackfillAccessError(
            "Recovery backfill is unavailable for these "
            "messages: "
            + ", ".join(unavailable_message_ids)
            + "."
        )

    existing_by_message_id = {
        envelope.message_id: envelope
        for envelope in (
            MessageRecoveryEnvelope.objects
            .select_for_update()
            .filter(
                message_id__in=message_ids,
                recovery_owner_user_id=(
                    normalized_user_id
                ),
            )
        )
    }

    created_models = []
    existing_count = 0

    for item in envelopes:
        message_id = item["message_id"]
        existing = existing_by_message_id.get(
            message_id
        )

        if existing is not None:
            if not _existing_envelope_matches(
                envelope=existing,
                recovery_key_version=(
                    recovery_key_version
                ),
                wrapped_message_key=(
                    item["wrapped_message_key"]
                ),
                key_wrap_metadata=(
                    item["key_wrap_metadata"]
                ),
                envelope_version=(
                    item["envelope_version"]
                ),
            ):
                raise RecoveryBackfillConflictError(
                    "A different recovery envelope already "
                    f"exists for message {message_id}."
                )

            existing_count += 1
            continue

        model = MessageRecoveryEnvelope(
            message=authorized_messages[message_id],
            recovery_owner_user_id=(
                normalized_user_id
            ),
            recovery_key_version=(
                recovery_key_version
            ),
            wrapped_message_key=(
                item["wrapped_message_key"]
            ),
            key_wrap_metadata=(
                item["key_wrap_metadata"]
            ),
            envelope_version=(
                item["envelope_version"]
            ),
        )
        model.full_clean()
        created_models.append(model)

    if created_models:
        MessageRecoveryEnvelope.objects.bulk_create(
            created_models
        )

    return RecoveryBackfillResult(
        bundle=bundle,
        device=device,
        created_count=len(created_models),
        existing_count=existing_count,
        total_count=len(envelopes),
    )

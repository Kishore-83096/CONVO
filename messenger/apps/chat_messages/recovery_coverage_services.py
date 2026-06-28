from dataclasses import dataclass

from django.db.models import Exists, OuterRef, QuerySet

from apps.e2ee_devices.models import Device, RecoveryBundle

from .models import (
    Message,
    MessageKeyEnvelope,
    MessageRecoveryEnvelope,
)


class RecoveryCoverageUnavailableError(Exception):
    """Raised when the user has no active recovery bundle."""


@dataclass(frozen=True)
class RecoveryCoverageDevice:
    id: object
    device_name: str
    platform: str
    backfill_candidate_count: int


@dataclass(frozen=True)
class RecoveryCoverageResult:
    bundle: RecoveryBundle
    total_eligible_messages: int
    current_version_covered_messages: int
    missing_recovery_envelopes: int
    stale_recovery_envelopes: int
    coverage_percent: float
    is_complete: bool
    active_devices: list[RecoveryCoverageDevice]


def _eligible_messages_for_user(
    *,
    user_id: str,
) -> QuerySet:
    """
    A message is eligible when the authenticated user is still an
    active room member and at least one active owned device has a
    normal message-key envelope for that message.
    """

    return (
        Message.objects.filter(
            room__is_active=True,
            room__members__user_id=user_id,
            room__members__is_active=True,
            key_envelopes__recipient_user_id=user_id,
            key_envelopes__recipient_device__user_id=user_id,
            key_envelopes__recipient_device__is_active=True,
        )
        .distinct()
        .order_by()
    )


def get_recovery_coverage(
    *,
    user_id: str,
) -> RecoveryCoverageResult:
    normalized_user_id = str(user_id)

    bundle = RecoveryBundle.objects.filter(
        user_id=normalized_user_id,
        is_active=True,
        disabled_at__isnull=True,
    ).first()

    if bundle is None:
        raise RecoveryCoverageUnavailableError(
            "Encrypted recovery is unavailable."
        )

    any_recovery_envelope = (
        MessageRecoveryEnvelope.objects.filter(
            message_id=OuterRef("pk"),
            recovery_owner_user_id=normalized_user_id,
        )
    )

    current_recovery_envelope = (
        any_recovery_envelope.filter(
            recovery_key_version=(
                bundle.recovery_version
            ),
        )
    )

    eligible_messages = (
        _eligible_messages_for_user(
            user_id=normalized_user_id,
        )
        .annotate(
            has_any_recovery_envelope=Exists(
                any_recovery_envelope
            ),
            has_current_recovery_envelope=Exists(
                current_recovery_envelope
            ),
        )
    )

    total_eligible_messages = eligible_messages.count()

    current_version_covered_messages = (
        eligible_messages.filter(
            has_current_recovery_envelope=True,
        ).count()
    )

    missing_recovery_envelopes = (
        eligible_messages.filter(
            has_any_recovery_envelope=False,
        ).count()
    )

    stale_recovery_envelopes = (
        eligible_messages.filter(
            has_any_recovery_envelope=True,
            has_current_recovery_envelope=False,
        ).count()
    )

    if total_eligible_messages == 0:
        coverage_percent = 100.0
    else:
        coverage_percent = round(
            (
                current_version_covered_messages
                / total_eligible_messages
            )
            * 100,
            2,
        )

    is_complete = (
        missing_recovery_envelopes == 0
        and stale_recovery_envelopes == 0
    )

    active_devices = []

    for device in Device.objects.filter(
        user_id=normalized_user_id,
        is_active=True,
    ).order_by("created_at", "id"):
        candidate_count = (
            eligible_messages.filter(
                has_any_recovery_envelope=False,
                key_envelopes__recipient_user_id=(
                    normalized_user_id
                ),
                key_envelopes__recipient_device=device,
            )
            .distinct()
            .count()
        )

        active_devices.append(
            RecoveryCoverageDevice(
                id=device.id,
                device_name=device.device_name,
                platform=device.platform,
                backfill_candidate_count=(
                    candidate_count
                ),
            )
        )

    return RecoveryCoverageResult(
        bundle=bundle,
        total_eligible_messages=(
            total_eligible_messages
        ),
        current_version_covered_messages=(
            current_version_covered_messages
        ),
        missing_recovery_envelopes=(
            missing_recovery_envelopes
        ),
        stale_recovery_envelopes=(
            stale_recovery_envelopes
        ),
        coverage_percent=coverage_percent,
        is_complete=is_complete,
        active_devices=active_devices,
    )

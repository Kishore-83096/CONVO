from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from .models import RecoveryBundle


class RecoveryAlreadyConfiguredError(Exception):
    """Raised when an active recovery bundle already exists."""


class RecoveryBundleUnavailableError(Exception):
    """Raised when no active recovery bundle exists."""


@dataclass(frozen=True)
class RecoverySetupResult:
    bundle: RecoveryBundle
    created: bool


@transaction.atomic
def setup_recovery_bundle(
    *,
    user_id: str,
    recovery_public_key: str,
    encrypted_recovery_private_key: str,
    encryption_metadata: dict,
) -> RecoverySetupResult:
    """
    Create the user's first encrypted recovery bundle.

    If a previously disabled bundle exists, it is replaced and
    reactivated with an incremented server-controlled version.

    The server never receives the plaintext recovery private key or
    the recovery secret.
    """

    normalized_user_id = str(user_id)

    existing_bundle = (
        RecoveryBundle.objects.select_for_update()
        .filter(user_id=normalized_user_id)
        .first()
    )

    if existing_bundle is not None and existing_bundle.is_active:
        raise RecoveryAlreadyConfiguredError(
            "Encrypted recovery is already configured. "
            "Use the recovery rotation endpoint to change it."
        )

    if existing_bundle is None:
        bundle = RecoveryBundle.objects.create(
            user_id=normalized_user_id,
            recovery_public_key=recovery_public_key,
            encrypted_recovery_private_key=(
                encrypted_recovery_private_key
            ),
            encryption_metadata=encryption_metadata,
            recovery_version=1,
            is_active=True,
        )

        return RecoverySetupResult(
            bundle=bundle,
            created=True,
        )

    existing_bundle.recovery_public_key = recovery_public_key
    existing_bundle.encrypted_recovery_private_key = (
        encrypted_recovery_private_key
    )
    existing_bundle.encryption_metadata = encryption_metadata
    existing_bundle.recovery_version += 1
    existing_bundle.is_active = True
    existing_bundle.disabled_at = None
    existing_bundle.rotated_at = timezone.now()

    existing_bundle.save(
        update_fields=[
            "recovery_public_key",
            "encrypted_recovery_private_key",
            "encryption_metadata",
            "recovery_version",
            "is_active",
            "disabled_at",
            "rotated_at",
            "updated_at",
        ]
    )

    return RecoverySetupResult(
        bundle=existing_bundle,
        created=False,
    )


def get_recovery_status(*, user_id: str) -> dict:
    bundle = RecoveryBundle.objects.filter(
        user_id=str(user_id),
    ).first()

    if bundle is None:
        return {
            "configured": False,
            "is_active": False,
            "recovery_version": None,
            "created_at": None,
            "updated_at": None,
            "rotated_at": None,
            "disabled_at": None,
        }

    return {
        "configured": True,
        "is_active": bundle.is_active,
        "recovery_version": bundle.recovery_version,
        "created_at": bundle.created_at,
        "updated_at": bundle.updated_at,
        "rotated_at": bundle.rotated_at,
        "disabled_at": bundle.disabled_at,
    }


def get_active_recovery_bundle(
    *,
    user_id: str,
) -> RecoveryBundle:
    bundle = RecoveryBundle.objects.filter(
        user_id=str(user_id),
        is_active=True,
        disabled_at__isnull=True,
    ).first()

    if bundle is None:
        raise RecoveryBundleUnavailableError(
            "Encrypted recovery is not available."
        )

    return bundle

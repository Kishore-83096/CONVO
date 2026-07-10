from dataclasses import dataclass
from typing import Any, Iterable
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone


from .models import RecoveryBundle


RECOVERY_ACTIVE_CACHE_TTL_SECONDS = 600


def get_recovery_active_cache_key(user_id: Any) -> str:
    return f"recovery_active:{str(user_id).strip()}"


def get_recovery_active_version_cache_key(user_id: Any) -> str:
    return f"recovery_active_version:{str(user_id).strip()}"



def invalidate_recovery_active_cache_for_user(user_id: Any) -> None:
    normalized_user_id = str(user_id).strip()

    if not normalized_user_id:
        return

    cache.delete_many(
        [
            get_recovery_active_cache_key(normalized_user_id),
            get_recovery_active_version_cache_key(normalized_user_id),
        ]
    )


def recovery_bundle_is_active_for_user(user_id: Any) -> bool:
    normalized_user_id = str(user_id).strip()

    if not normalized_user_id:
        return False

    cache_key = get_recovery_active_cache_key(
        normalized_user_id
    )
    cached_value = cache.get(cache_key)

    if isinstance(cached_value, bool):
        return cached_value

    is_active = RecoveryBundle.objects.filter(
        user_id=normalized_user_id,
        is_active=True,
        disabled_at__isnull=True,
    ).exists()

    cache.set(
        cache_key,
        is_active,
        RECOVERY_ACTIVE_CACHE_TTL_SECONDS,
    )

    return is_active



def recovery_bundle_is_active_for_users(
    user_ids: Iterable[Any],
) -> bool:
    """
    Return whether any user has active recovery using one batched cache/DB path.

    Cache keys and invalidation semantics stay identical to the single-user
    helper. On cache misses, all missing users are resolved with one query.
    """
    normalized_user_ids: list[str] = []
    seen_user_ids: set[str] = set()

    for user_id in user_ids:
        normalized_user_id = str(user_id).strip()

        if (
            not normalized_user_id
            or normalized_user_id in seen_user_ids
        ):
            continue

        seen_user_ids.add(normalized_user_id)
        normalized_user_ids.append(normalized_user_id)

    if not normalized_user_ids:
        return False

    cache_keys_by_user_id = {
        user_id: get_recovery_active_cache_key(user_id)
        for user_id in normalized_user_ids
    }

    cached_values = cache.get_many(
        cache_keys_by_user_id.values()
    )

    missing_user_ids: list[str] = []

    for user_id in normalized_user_ids:
        cached_value = cached_values.get(
            cache_keys_by_user_id[user_id]
        )

        if isinstance(cached_value, bool):
            if cached_value:
                return True

            continue

        missing_user_ids.append(user_id)

    if not missing_user_ids:
        return False

    active_user_ids = {
        str(user_id)
        for user_id in (
            RecoveryBundle.objects.filter(
                user_id__in=missing_user_ids,
                is_active=True,
                disabled_at__isnull=True,
            ).values_list(
                "user_id",
                flat=True,
            )
        )
    }

    cache.set_many(
        {
            cache_keys_by_user_id[user_id]: (
                user_id in active_user_ids
            )
            for user_id in missing_user_ids
        },
        RECOVERY_ACTIVE_CACHE_TTL_SECONDS,
    )

    return bool(active_user_ids)



def get_active_recovery_versions_for_users(
    user_ids: Iterable[Any],
) -> dict[str, int]:
    """Return active recovery versions using one batched cache/DB lookup.

    A cached value of 0 means that the user has no active recovery bundle.
    Positive integers are the active server-controlled recovery versions.
    """
    normalized_user_ids: list[str] = []
    seen_user_ids: set[str] = set()

    for user_id in user_ids:
        normalized_user_id = str(user_id).strip()

        if (
            not normalized_user_id
            or normalized_user_id in seen_user_ids
        ):
            continue

        seen_user_ids.add(normalized_user_id)
        normalized_user_ids.append(normalized_user_id)

    if not normalized_user_ids:
        return {}

    cache_keys_by_user_id = {
        user_id: get_recovery_active_version_cache_key(user_id)
        for user_id in normalized_user_ids
    }

    cached_values = cache.get_many(
        cache_keys_by_user_id.values()
    )

    active_versions: dict[str, int] = {}
    missing_user_ids: list[str] = []

    for user_id in normalized_user_ids:
        cached_value = cached_values.get(
            cache_keys_by_user_id[user_id]
        )

        if (
            isinstance(cached_value, int)
            and not isinstance(cached_value, bool)
            and cached_value >= 0
        ):
            if cached_value > 0:
                active_versions[user_id] = cached_value

            continue

        missing_user_ids.append(user_id)

    if missing_user_ids:
        database_versions = {
            str(user_id): int(recovery_version)
            for user_id, recovery_version in (
                RecoveryBundle.objects.filter(
                    user_id__in=missing_user_ids,
                    is_active=True,
                    disabled_at__isnull=True,
                ).values_list(
                    "user_id",
                    "recovery_version",
                )
            )
        }

        cache.set_many(
            {
                cache_keys_by_user_id[user_id]: database_versions.get(
                    user_id,
                    0,
                )
                for user_id in missing_user_ids
            },
            RECOVERY_ACTIVE_CACHE_TTL_SECONDS,
        )

        active_versions.update(database_versions)

    return active_versions


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

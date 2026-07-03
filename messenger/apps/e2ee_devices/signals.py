from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Device, RecoveryBundle
from .recovery_services import (
    invalidate_recovery_active_cache_for_user,
)
from .services import invalidate_active_device_cache_for_user


def _invalidate_after_device_change(user_id: str) -> None:
    """
    Delete immediately and again after commit.

    Immediate delete keeps the current process safe. The on_commit
    delete prevents a stale cache value from being repopulated during
    the open transaction and surviving after commit.
    """

    invalidate_active_device_cache_for_user(user_id)

    transaction.on_commit(
        lambda: invalidate_active_device_cache_for_user(user_id)
    )


@receiver(post_save, sender=Device)
def invalidate_active_device_cache_after_save(
    sender,
    instance: Device,
    **kwargs,
) -> None:
    _invalidate_after_device_change(instance.user_id)


@receiver(post_delete, sender=Device)
def invalidate_active_device_cache_after_delete(
    sender,
    instance: Device,
    **kwargs,
) -> None:
    _invalidate_after_device_change(instance.user_id)




def _invalidate_after_recovery_bundle_change(user_id: str) -> None:
    invalidate_recovery_active_cache_for_user(user_id)
    transaction.on_commit(
        lambda: invalidate_recovery_active_cache_for_user(user_id)
    )


@receiver(post_save, sender=RecoveryBundle)
def invalidate_recovery_active_cache_after_save(
    sender,
    instance: RecoveryBundle,
    **kwargs,
) -> None:
    _invalidate_after_recovery_bundle_change(instance.user_id)


@receiver(post_delete, sender=RecoveryBundle)
def invalidate_recovery_active_cache_after_delete(
    sender,
    instance: RecoveryBundle,
    **kwargs,
) -> None:
    _invalidate_after_recovery_bundle_change(instance.user_id)
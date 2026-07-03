from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import ContactDeliveryPolicy
from .policy_services import (
    invalidate_delivery_policy_cache_for_pair,
)


def _invalidate_after_policy_change(
    *,
    owner_user_id: str,
    target_user_id: str,
) -> None:
    invalidate_delivery_policy_cache_for_pair(
        recipient_user_id=owner_user_id,
        sender_user_id=target_user_id,
    )
    transaction.on_commit(
        lambda: invalidate_delivery_policy_cache_for_pair(
            recipient_user_id=owner_user_id,
            sender_user_id=target_user_id,
        )
    )


@receiver(post_save, sender=ContactDeliveryPolicy)
def invalidate_delivery_policy_cache_after_save(
    sender,
    instance: ContactDeliveryPolicy,
    **kwargs,
) -> None:
    _invalidate_after_policy_change(
        owner_user_id=instance.owner_user_id,
        target_user_id=instance.target_user_id,
    )


@receiver(post_delete, sender=ContactDeliveryPolicy)
def invalidate_delivery_policy_cache_after_delete(
    sender,
    instance: ContactDeliveryPolicy,
    **kwargs,
) -> None:
    _invalidate_after_policy_change(
        owner_user_id=instance.owner_user_id,
        target_user_id=instance.target_user_id,
    )
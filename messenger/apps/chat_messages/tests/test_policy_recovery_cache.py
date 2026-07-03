import time
from datetime import timedelta

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from apps.chat_messages.models import ContactDeliveryPolicy
from apps.chat_messages.policy_services import (
    can_view_presence,
    get_delivery_policy_snapshot,
    upsert_contact_delivery_policy,
)
from apps.chat_messages.recovery_send_services import (
    _active_recovery_bundle_exists,
)
from apps.e2ee_devices.models import RecoveryBundle
from apps.e2ee_devices.recovery_services import (
    get_recovery_active_cache_key,
    recovery_bundle_is_active_for_user,
)


class PolicyAndRecoveryCacheTests(TestCase):
    def setUp(self):
        cache.clear()

    def create_recovery_bundle(
        self,
        *,
        user_id: str = "1",
        is_active: bool = True,
    ) -> RecoveryBundle:
        return RecoveryBundle.objects.create(
            user_id=user_id,
            recovery_public_key=f"USER_{user_id}_RECOVERY_PUBLIC",
            encrypted_recovery_private_key=(
                f"USER_{user_id}_ENCRYPTED_PRIVATE"
            ),
            encryption_metadata={
                "algorithm": "xchacha20poly1305-ietf",
                "nonce": f"USER_{user_id}_NONCE",
                "unlock_method": "recovery_key",
            },
            recovery_version=1,
            is_active=is_active,
            disabled_at=None if is_active else timezone.now(),
        )

    def test_delivery_policy_cache_hit_uses_no_database_query(self):
        ContactDeliveryPolicy.objects.create(
            owner_user_id="A",
            target_user_id="B",
            is_blocked=True,
            policy_version=1,
        )

        snapshot = get_delivery_policy_snapshot(
            recipient_user_id="A",
            sender_user_id="B",
        )

        self.assertTrue(snapshot.is_blocked)

        with self.assertNumQueries(0):
            cached_snapshot = get_delivery_policy_snapshot(
                recipient_user_id="A",
                sender_user_id="B",
            )

        self.assertTrue(cached_snapshot.is_blocked)

    def test_block_policy_update_invalidates_cached_normal_snapshot(self):
        snapshot = get_delivery_policy_snapshot(
            recipient_user_id="A",
            sender_user_id="B",
        )
        self.assertFalse(snapshot.is_blocked)

        upsert_contact_delivery_policy(
            owner_user_id="A",
            target_user_id="B",
            is_blocked=True,
            policy_version=1,
        )

        blocked_snapshot = get_delivery_policy_snapshot(
            recipient_user_id="A",
            sender_user_id="B",
        )

        self.assertTrue(blocked_snapshot.is_blocked)
        self.assertFalse(
            can_view_presence(
                viewer_user_id="B",
                subject_user_id="A",
            )
        )

    def test_ghost_policy_update_invalidates_cached_normal_snapshot(self):
        snapshot = get_delivery_policy_snapshot(
            recipient_user_id="A",
            sender_user_id="B",
        )
        self.assertFalse(snapshot.ghost_active)

        upsert_contact_delivery_policy(
            owner_user_id="A",
            target_user_id="B",
            is_blocked=False,
            ghost_until=timezone.now() + timedelta(minutes=5),
            ghost_permanent=False,
            ghost_duration_option="1h",
            policy_version=1,
        )

        ghost_snapshot = get_delivery_policy_snapshot(
            recipient_user_id="A",
            sender_user_id="B",
        )

        self.assertTrue(ghost_snapshot.ghost_active)
        self.assertFalse(
            can_view_presence(
                viewer_user_id="B",
                subject_user_id="A",
            )
        )

    def test_active_ghost_cache_expires_at_ghost_until(self):
        ContactDeliveryPolicy.objects.create(
            owner_user_id="A",
            target_user_id="B",
            is_blocked=False,
            ghost_until=timezone.now() + timedelta(seconds=1),
            ghost_permanent=False,
            ghost_duration_option="1h",
            policy_version=1,
        )

        ghost_snapshot = get_delivery_policy_snapshot(
            recipient_user_id="A",
            sender_user_id="B",
        )
        self.assertTrue(ghost_snapshot.ghost_active)

        time.sleep(1.2)

        expired_snapshot = get_delivery_policy_snapshot(
            recipient_user_id="A",
            sender_user_id="B",
        )
        self.assertFalse(expired_snapshot.ghost_active)
        self.assertTrue(
            can_view_presence(
                viewer_user_id="B",
                subject_user_id="A",
            )
        )

    def test_recovery_active_cache_hit_uses_no_database_query(self):
        self.create_recovery_bundle(user_id="1")

        self.assertTrue(recovery_bundle_is_active_for_user("1"))

        with self.assertNumQueries(0):
            self.assertTrue(
                recovery_bundle_is_active_for_user("1")
            )

        self.assertTrue(
            _active_recovery_bundle_exists(
                participant_ids={"1", "2"},
            )
        )

    def test_recovery_bundle_save_invalidates_cached_inactive_state(self):
        self.assertFalse(recovery_bundle_is_active_for_user("1"))
        self.assertEqual(
            cache.get(get_recovery_active_cache_key("1")),
            False,
        )

        self.create_recovery_bundle(user_id="1")

        self.assertTrue(recovery_bundle_is_active_for_user("1"))

    def test_policy_delete_invalidates_cached_block_state(self):
        policy = ContactDeliveryPolicy.objects.create(
            owner_user_id="A",
            target_user_id="B",
            is_blocked=True,
            policy_version=1,
        )

        self.assertTrue(
            get_delivery_policy_snapshot(
                recipient_user_id="A",
                sender_user_id="B",
            ).is_blocked
        )

        policy.delete()

        snapshot = get_delivery_policy_snapshot(
            recipient_user_id="A",
            sender_user_id="B",
        )

        self.assertFalse(snapshot.is_blocked)
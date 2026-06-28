import uuid
from collections import defaultdict
from datetime import timedelta
from unittest.mock import patch

from django.test import TransactionTestCase, override_settings
from django.utils import timezone

from apps.chat_messages.models import ContactDeliveryPolicy
from apps.e2ee_devices.models import Device
from apps.realtime.presence import mark_device_online
from apps.realtime.services import (
    UNAVAILABLE_PRESENCE_STATUS,
    get_presence_snapshot_for_viewer,
)


class FakeAsyncRedis:
    def __init__(self):
        self.sets = defaultdict(set)
        self.values = {}
        self.expire_calls = []

    async def sadd(self, key, *values):
        before = len(self.sets[key])

        for value in values:
            self.sets[key].add(str(value))

        return len(self.sets[key]) - before

    async def srem(self, key, *values):
        removed = 0

        for value in values:
            value = str(value)

            if value in self.sets[key]:
                self.sets[key].remove(value)
                removed += 1

        return removed

    async def scard(self, key):
        return len(self.sets[key])

    async def smembers(self, key):
        return set(self.sets[key])

    async def expire(self, key, seconds):
        self.expire_calls.append((key, seconds))
        return True

    async def set(self, key, value, ex=None, nx=False):
        if nx and key in self.values:
            return False

        self.values[key] = str(value)

        if ex is not None:
            self.expire_calls.append((key, ex))

        return True

    async def delete(self, *keys):
        deleted = 0

        for key in keys:
            if key in self.values:
                del self.values[key]
                deleted += 1

            if key in self.sets:
                del self.sets[key]
                deleted += 1

        return deleted

    async def aclose(self):
        return None


@override_settings(
    REALTIME_PRESENCE_TTL_SECONDS=45,
)
class PresenceVisibilityTests(TransactionTestCase):
    reset_sequences = True

    subject_device_id = uuid.UUID(
        "11111111-1111-4111-8111-111111111111"
    )

    def setUp(self):
        self.redis = FakeAsyncRedis()

        self.subject_device = Device.objects.create(
            id=self.subject_device_id,
            user_id="A",
            device_name="Subject browser",
            platform=Device.Platform.WEB,
            registration_id=10001,
            identity_key_public="SUBJECT_IDENTITY",
            signed_prekey_id=1,
            signed_prekey_public="SUBJECT_SIGNED_PREKEY",
            signed_prekey_signature="SUBJECT_SIGNATURE",
            key_algorithm="curve25519",
            key_bundle_version=1,
            is_active=True,
        )

    def patch_redis(self):
        return patch(
            "apps.realtime.presence.get_redis_client",
            return_value=self.redis,
        )

    async def mark_subject_online(self):
        await mark_device_online(
            user_id="A",
            device_id=str(self.subject_device_id),
            channel_name="subject.channel.1",
        )

    async def test_allowed_viewer_can_see_subject_online_presence(self):
        with self.patch_redis():
            await self.mark_subject_online()

            snapshot = await get_presence_snapshot_for_viewer(
                viewer_user_id="B",
                subject_user_id="A",
            )

            self.assertEqual(snapshot["user_id"], "A")
            self.assertEqual(snapshot["status"], "online")
            self.assertEqual(
                snapshot["online_device_ids"],
                [str(self.subject_device_id)],
            )
            self.assertIsNotNone(snapshot["last_seen_at"])

    async def test_subject_can_see_own_presence(self):
        with self.patch_redis():
            await self.mark_subject_online()

            snapshot = await get_presence_snapshot_for_viewer(
                viewer_user_id="A",
                subject_user_id="A",
            )

            self.assertEqual(snapshot["user_id"], "A")
            self.assertEqual(snapshot["status"], "online")
            self.assertEqual(
                snapshot["online_device_ids"],
                [str(self.subject_device_id)],
            )
            self.assertIsNotNone(snapshot["last_seen_at"])

    async def test_blocked_viewer_gets_generic_unavailable_presence(self):
        """
        A blocks B.

        B must not see A online/last_seen/device presence.
        The response must not reveal block reason.
        """

        await ContactDeliveryPolicy.objects.acreate(
            owner_user_id="A",
            target_user_id="B",
            is_blocked=True,
            policy_version=1,
        )

        with self.patch_redis():
            await self.mark_subject_online()

            snapshot = await get_presence_snapshot_for_viewer(
                viewer_user_id="B",
                subject_user_id="A",
            )

            self.assertEqual(snapshot["user_id"], "A")
            self.assertEqual(
                snapshot["status"],
                UNAVAILABLE_PRESENCE_STATUS,
            )
            self.assertEqual(snapshot["online_device_ids"], [])
            self.assertIsNone(snapshot["last_seen_at"])
            self.assertNotIn("reason", snapshot)
            self.assertNotIn("blocked", snapshot)

    async def test_block_owner_can_still_see_restricted_user_presence(self):
        """
        A blocks B.

        Directional rule:
        B cannot see A.
        A can still see B unless B also restricted A.
        """

        await ContactDeliveryPolicy.objects.acreate(
            owner_user_id="A",
            target_user_id="B",
            is_blocked=True,
            policy_version=1,
        )

        b_device_id = uuid.UUID(
            "22222222-2222-4222-8222-222222222222"
        )

        await Device.objects.acreate(
            id=b_device_id,
            user_id="B",
            device_name="B browser",
            platform=Device.Platform.WEB,
            registration_id=20001,
            identity_key_public="B_IDENTITY",
            signed_prekey_id=1,
            signed_prekey_public="B_SIGNED_PREKEY",
            signed_prekey_signature="B_SIGNATURE",
            key_algorithm="curve25519",
            key_bundle_version=1,
            is_active=True,
        )

        with self.patch_redis():
            await mark_device_online(
                user_id="B",
                device_id=str(b_device_id),
                channel_name="b.channel.1",
            )

            snapshot = await get_presence_snapshot_for_viewer(
                viewer_user_id="A",
                subject_user_id="B",
            )

            self.assertEqual(snapshot["user_id"], "B")
            self.assertEqual(snapshot["status"], "online")
            self.assertEqual(
                snapshot["online_device_ids"],
                [str(b_device_id)],
            )

    async def test_active_ghosted_viewer_gets_generic_unavailable_presence(self):
        """
        A ghosts B.

        B must not see A presence until ghost expiry.
        The response must not reveal ghost reason.
        """

        await ContactDeliveryPolicy.objects.acreate(
            owner_user_id="A",
            target_user_id="B",
            is_blocked=False,
            ghost_until=timezone.now() + timedelta(hours=1),
            ghost_permanent=False,
            ghost_duration_option="1h",
            policy_version=1,
        )

        with self.patch_redis():
            await self.mark_subject_online()

            snapshot = await get_presence_snapshot_for_viewer(
                viewer_user_id="B",
                subject_user_id="A",
            )

            self.assertEqual(snapshot["user_id"], "A")
            self.assertEqual(
                snapshot["status"],
                UNAVAILABLE_PRESENCE_STATUS,
            )
            self.assertEqual(snapshot["online_device_ids"], [])
            self.assertIsNone(snapshot["last_seen_at"])
            self.assertNotIn("reason", snapshot)
            self.assertNotIn("ghost", snapshot)

    async def test_expired_ghost_allows_presence_again(self):
        await ContactDeliveryPolicy.objects.acreate(
            owner_user_id="A",
            target_user_id="B",
            is_blocked=False,
            ghost_until=timezone.now() - timedelta(minutes=1),
            ghost_permanent=False,
            ghost_duration_option="1h",
            policy_version=1,
        )

        with self.patch_redis():
            await self.mark_subject_online()

            snapshot = await get_presence_snapshot_for_viewer(
                viewer_user_id="B",
                subject_user_id="A",
            )

            self.assertEqual(snapshot["user_id"], "A")
            self.assertEqual(snapshot["status"], "online")
            self.assertEqual(
                snapshot["online_device_ids"],
                [str(self.subject_device_id)],
            )

    async def test_blank_viewer_gets_unavailable(self):
        with self.patch_redis():
            await self.mark_subject_online()

            snapshot = await get_presence_snapshot_for_viewer(
                viewer_user_id="",
                subject_user_id="A",
            )

            self.assertEqual(snapshot["user_id"], "A")
            self.assertEqual(
                snapshot["status"],
                UNAVAILABLE_PRESENCE_STATUS,
            )
            self.assertEqual(snapshot["online_device_ids"], [])
            self.assertIsNone(snapshot["last_seen_at"])

    async def test_blank_subject_gets_unavailable(self):
        snapshot = await get_presence_snapshot_for_viewer(
            viewer_user_id="A",
            subject_user_id="",
        )

        self.assertEqual(snapshot["user_id"], "")
        self.assertEqual(
            snapshot["status"],
            UNAVAILABLE_PRESENCE_STATUS,
        )
        self.assertEqual(snapshot["online_device_ids"], [])
        self.assertIsNone(snapshot["last_seen_at"])
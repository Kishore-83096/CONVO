import uuid
from collections import defaultdict
from datetime import timedelta
from unittest.mock import patch

from channels.layers import get_channel_layer
from django.test import TransactionTestCase, override_settings
from django.utils import timezone

from apps.chat_messages.models import ContactDeliveryPolicy
from apps.e2ee_devices.models import Device
from apps.realtime.events import (
    PRESENCE_CHANGED,
    PRESENCE_HIDDEN,
)
from apps.realtime.presence import mark_device_online
from apps.realtime.publishers import (
    make_user_group_name,
    normalize_viewer_user_ids,
    publish_presence_to_viewers,
)


TEST_CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    },
}


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
    CHANNEL_LAYERS=TEST_CHANNEL_LAYERS,
    REALTIME_PRESENCE_TTL_SECONDS=45,
)
class PresencePublisherTests(TransactionTestCase):
    reset_sequences = True

    subject_device_id = uuid.UUID(
        "11111111-1111-4111-8111-111111111111"
    )

    def setUp(self):
        self.redis = FakeAsyncRedis()

        self.subject_device = Device.objects.create(
            id=self.subject_device_id,
            user_id="A",
            device_name="A browser",
            platform=Device.Platform.WEB,
            registration_id=10001,
            identity_key_public="A_IDENTITY",
            signed_prekey_id=1,
            signed_prekey_public="A_SIGNED_PREKEY",
            signed_prekey_signature="A_SIGNATURE",
            key_algorithm="curve25519",
            key_bundle_version=1,
            is_active=True,
        )

    def patch_redis(self):
        return patch(
            "apps.realtime.presence.get_redis_client",
            return_value=self.redis,
        )

    async def create_group_receiver(self, viewer_user_id: str):
        channel_layer = get_channel_layer()
        channel_name = await channel_layer.new_channel()

        await channel_layer.group_add(
            make_user_group_name(viewer_user_id),
            channel_name,
        )

        return channel_layer, channel_name

    async def mark_subject_online(self):
        await mark_device_online(
            user_id="A",
            device_id=str(self.subject_device_id),
            channel_name="subject.channel.1",
        )

    async def test_normalize_viewer_user_ids_deduplicates_and_removes_blank(self):
        self.assertEqual(
            normalize_viewer_user_ids(
                [
                    "viewer",
                    "",
                    "viewer",
                    " other ",
                    None,
                ]
            ),
            (
                "viewer",
                "other",
                "None",
            ),
        )

    async def test_allowed_viewer_receives_presence_changed(self):
        channel_layer, channel_name = await self.create_group_receiver(
            "viewer",
        )

        with self.patch_redis():
            await self.mark_subject_online()

            result = await publish_presence_to_viewers(
                subject_user_id="A",
                viewer_user_ids=[
                    "viewer",
                ],
            )

        self.assertEqual(result.sent_count, 1)
        self.assertEqual(result.visible_count, 1)
        self.assertEqual(result.hidden_count, 0)

        event = await channel_layer.receive(channel_name)
        payload = event["payload"]

        self.assertEqual(event["type"], "realtime.event")
        self.assertEqual(payload["type"], PRESENCE_CHANGED)
        self.assertIn("event_id", payload)
        self.assertIn("created_at", payload)

        presence = payload["data"]["presence"]

        self.assertEqual(presence["user_id"], "A")
        self.assertEqual(presence["status"], "online")
        self.assertEqual(
            presence["online_device_ids"],
            [str(self.subject_device_id)],
        )
        self.assertIsNotNone(presence["last_seen_at"])
        self.assertNotIn("reason", presence)

    async def test_blocked_viewer_receives_presence_hidden(self):
        await ContactDeliveryPolicy.objects.acreate(
            owner_user_id="A",
            target_user_id="viewer",
            is_blocked=True,
            policy_version=1,
        )

        channel_layer, channel_name = await self.create_group_receiver(
            "viewer",
        )

        with self.patch_redis():
            await self.mark_subject_online()

            result = await publish_presence_to_viewers(
                subject_user_id="A",
                viewer_user_ids=[
                    "viewer",
                ],
            )

        self.assertEqual(result.sent_count, 1)
        self.assertEqual(result.visible_count, 0)
        self.assertEqual(result.hidden_count, 1)

        event = await channel_layer.receive(channel_name)
        payload = event["payload"]

        self.assertEqual(payload["type"], PRESENCE_HIDDEN)

        presence = payload["data"]["presence"]

        self.assertEqual(presence["user_id"], "A")
        self.assertEqual(presence["status"], "unavailable")
        self.assertEqual(presence["online_device_ids"], [])
        self.assertIsNone(presence["last_seen_at"])
        self.assertNotIn("reason", presence)
        self.assertNotIn("blocked", presence)

    async def test_ghosted_viewer_receives_presence_hidden(self):
        await ContactDeliveryPolicy.objects.acreate(
            owner_user_id="A",
            target_user_id="viewer",
            is_blocked=False,
            ghost_until=timezone.now() + timedelta(hours=1),
            ghost_permanent=False,
            ghost_duration_option="1h",
            policy_version=1,
        )

        channel_layer, channel_name = await self.create_group_receiver(
            "viewer",
        )

        with self.patch_redis():
            await self.mark_subject_online()

            result = await publish_presence_to_viewers(
                subject_user_id="A",
                viewer_user_ids=[
                    "viewer",
                ],
            )

        self.assertEqual(result.sent_count, 1)
        self.assertEqual(result.visible_count, 0)
        self.assertEqual(result.hidden_count, 1)

        event = await channel_layer.receive(channel_name)
        payload = event["payload"]

        self.assertEqual(payload["type"], PRESENCE_HIDDEN)

        presence = payload["data"]["presence"]

        self.assertEqual(presence["user_id"], "A")
        self.assertEqual(presence["status"], "unavailable")
        self.assertEqual(presence["online_device_ids"], [])
        self.assertIsNone(presence["last_seen_at"])
        self.assertNotIn("reason", presence)
        self.assertNotIn("ghost", presence)

    async def test_expired_ghost_viewer_receives_presence_changed(self):
        await ContactDeliveryPolicy.objects.acreate(
            owner_user_id="A",
            target_user_id="viewer",
            is_blocked=False,
            ghost_until=timezone.now() - timedelta(minutes=1),
            ghost_permanent=False,
            ghost_duration_option="1h",
            policy_version=1,
        )

        channel_layer, channel_name = await self.create_group_receiver(
            "viewer",
        )

        with self.patch_redis():
            await self.mark_subject_online()

            result = await publish_presence_to_viewers(
                subject_user_id="A",
                viewer_user_ids=[
                    "viewer",
                ],
            )

        self.assertEqual(result.sent_count, 1)
        self.assertEqual(result.visible_count, 1)
        self.assertEqual(result.hidden_count, 0)

        event = await channel_layer.receive(channel_name)
        payload = event["payload"]

        self.assertEqual(payload["type"], PRESENCE_CHANGED)
        self.assertEqual(
            payload["data"]["presence"]["status"],
            "online",
        )

    async def test_duplicate_viewers_receive_only_one_event(self):
        channel_layer, channel_name = await self.create_group_receiver(
            "viewer",
        )

        with self.patch_redis():
            await self.mark_subject_online()

            result = await publish_presence_to_viewers(
                subject_user_id="A",
                viewer_user_ids=[
                    "viewer",
                    "viewer",
                    "",
                ],
            )

        self.assertEqual(result.requested_viewer_count, 3)
        self.assertEqual(result.unique_viewer_count, 1)
        self.assertEqual(result.sent_count, 1)
        self.assertEqual(
            result.viewer_user_ids,
            (
                "viewer",
            ),
        )

        event = await channel_layer.receive(channel_name)

        self.assertEqual(event["payload"]["type"], PRESENCE_CHANGED)
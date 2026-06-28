import uuid
from collections import defaultdict
from datetime import timedelta
from unittest.mock import patch

from django.test import TransactionTestCase, override_settings
from django.utils import timezone

from apps.e2ee_devices.models import Device
from apps.realtime.presence import (
    get_user_online_device_ids,
    get_user_presence_snapshot,
    is_device_online,
    is_user_online,
    mark_device_disconnected,
    mark_device_online,
    presence_device_connections_key,
    presence_device_last_heartbeat_key,
    presence_device_last_seen_write_key,
    presence_device_user_key,
    presence_user_online_devices_key,
    refresh_device_heartbeat,
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
class RealtimePresenceTests(TransactionTestCase):
    reset_sequences = True

    device_id = uuid.UUID(
        "11111111-1111-4111-8111-111111111111"
    )
    second_device_id = uuid.UUID(
        "22222222-2222-4222-8222-222222222222"
    )

    def setUp(self):
        self.redis = FakeAsyncRedis()

        self.device = Device.objects.create(
            id=self.device_id,
            user_id="1",
            device_name="User 1 browser",
            platform=Device.Platform.WEB,
            registration_id=10001,
            identity_key_public="USER_1_IDENTITY",
            signed_prekey_id=1,
            signed_prekey_public="USER_1_SIGNED_PREKEY",
            signed_prekey_signature="USER_1_SIGNATURE",
            key_algorithm="curve25519",
            key_bundle_version=1,
            is_active=True,
        )

        self.second_device = Device.objects.create(
            id=self.second_device_id,
            user_id="1",
            device_name="User 1 phone",
            platform=Device.Platform.ANDROID,
            registration_id=10002,
            identity_key_public="USER_1_PHONE_IDENTITY",
            signed_prekey_id=2,
            signed_prekey_public="USER_1_PHONE_SIGNED_PREKEY",
            signed_prekey_signature="USER_1_PHONE_SIGNATURE",
            key_algorithm="curve25519",
            key_bundle_version=1,
            is_active=True,
        )

    def patch_redis(self):
        return patch(
            "apps.realtime.presence.get_redis_client",
            return_value=self.redis,
        )

    async def test_mark_device_online_stores_connection_and_user_device(self):
        with self.patch_redis():
            state = await mark_device_online(
                user_id="1",
                device_id=str(self.device_id),
                channel_name="specific.channel.1",
            )

            self.assertTrue(state.device_online)
            self.assertTrue(state.user_online)
            self.assertEqual(state.connection_count, 1)
            self.assertEqual(
                state.online_device_ids,
                (str(self.device_id),),
            )

            self.assertIn(
                "specific.channel.1",
                self.redis.sets[
                    presence_device_connections_key(self.device_id)
                ],
            )

            self.assertIn(
                str(self.device_id),
                self.redis.sets[
                    presence_user_online_devices_key("1")
                ],
            )

            self.assertEqual(
                self.redis.values[
                    presence_device_user_key(self.device_id)
                ],
                "1",
            )

            self.assertIn(
                presence_device_last_heartbeat_key(self.device_id),
                self.redis.values,
            )

            device = await Device.objects.aget(id=self.device_id)

            self.assertIsNotNone(device.last_seen_at)

    async def test_heartbeat_refresh_keeps_device_and_user_online(self):
        with self.patch_redis():
            await mark_device_online(
                user_id="1",
                device_id=str(self.device_id),
                channel_name="specific.channel.1",
            )

            state = await refresh_device_heartbeat(
                user_id="1",
                device_id=str(self.device_id),
                channel_name="specific.channel.1",
            )

            self.assertTrue(state.device_online)
            self.assertTrue(state.user_online)
            self.assertEqual(state.connection_count, 1)
            self.assertEqual(
                state.online_device_ids,
                (str(self.device_id),),
            )

            self.assertTrue(
                await is_device_online(
                    device_id=str(self.device_id),
                )
            )
            self.assertTrue(
                await is_user_online(
                    user_id="1",
                )
            )

    async def test_disconnect_one_connection_keeps_device_online(self):
        with self.patch_redis():
            await mark_device_online(
                user_id="1",
                device_id=str(self.device_id),
                channel_name="specific.channel.1",
            )
            await mark_device_online(
                user_id="1",
                device_id=str(self.device_id),
                channel_name="specific.channel.2",
            )

            state = await mark_device_disconnected(
                user_id="1",
                device_id=str(self.device_id),
                channel_name="specific.channel.1",
            )

            self.assertTrue(state.device_online)
            self.assertTrue(state.user_online)
            self.assertEqual(state.connection_count, 1)

            self.assertNotIn(
                "specific.channel.1",
                self.redis.sets[
                    presence_device_connections_key(self.device_id)
                ],
            )
            self.assertIn(
                "specific.channel.2",
                self.redis.sets[
                    presence_device_connections_key(self.device_id)
                ],
            )

    async def test_disconnect_last_connection_marks_device_offline(self):
        with self.patch_redis():
            await mark_device_online(
                user_id="1",
                device_id=str(self.device_id),
                channel_name="specific.channel.1",
            )

            state = await mark_device_disconnected(
                user_id="1",
                device_id=str(self.device_id),
                channel_name="specific.channel.1",
            )

            self.assertFalse(state.device_online)
            self.assertFalse(state.user_online)
            self.assertEqual(state.connection_count, 0)
            self.assertEqual(state.online_device_ids, tuple())

            self.assertFalse(
                await is_device_online(
                    device_id=str(self.device_id),
                )
            )
            self.assertFalse(
                await is_user_online(
                    user_id="1",
                )
            )

    async def test_user_stays_online_when_second_device_is_online(self):
        with self.patch_redis():
            await mark_device_online(
                user_id="1",
                device_id=str(self.device_id),
                channel_name="browser.channel",
            )
            await mark_device_online(
                user_id="1",
                device_id=str(self.second_device_id),
                channel_name="phone.channel",
            )

            state = await mark_device_disconnected(
                user_id="1",
                device_id=str(self.device_id),
                channel_name="browser.channel",
            )

            self.assertFalse(state.device_online)
            self.assertTrue(state.user_online)
            self.assertEqual(
                state.online_device_ids,
                (str(self.second_device_id),),
            )

            online_device_ids = await get_user_online_device_ids(
                user_id="1",
            )

            self.assertEqual(
                online_device_ids,
                (str(self.second_device_id),),
            )

    async def test_get_user_presence_snapshot_returns_online_and_last_seen(self):
        with self.patch_redis():
            await mark_device_online(
                user_id="1",
                device_id=str(self.device_id),
                channel_name="specific.channel.1",
            )

            snapshot = await get_user_presence_snapshot(
                user_id="1",
            )

            self.assertEqual(snapshot["user_id"], "1")
            self.assertEqual(snapshot["status"], "online")
            self.assertEqual(
                snapshot["online_device_ids"],
                [str(self.device_id)],
            )
            self.assertIsNotNone(snapshot["last_seen_at"])

    async def test_get_user_presence_snapshot_returns_offline(self):
        seen_at = timezone.now() - timedelta(minutes=10)
        self.device.last_seen_at = seen_at
        await self.device.asave(
            update_fields=[
                "last_seen_at",
            ]
        )

        with self.patch_redis():
            snapshot = await get_user_presence_snapshot(
                user_id="1",
            )

            self.assertEqual(snapshot["user_id"], "1")
            self.assertEqual(snapshot["status"], "offline")
            self.assertEqual(snapshot["online_device_ids"], [])
            self.assertEqual(
                snapshot["last_seen_at"],
                seen_at.isoformat(),
            )

    async def test_last_seen_database_write_is_throttled(self):
        with self.patch_redis():
            await mark_device_online(
                user_id="1",
                device_id=str(self.device_id),
                channel_name="specific.channel.1",
            )

            first_seen = (
                await Device.objects.aget(id=self.device_id)
            ).last_seen_at

            await refresh_device_heartbeat(
                user_id="1",
                device_id=str(self.device_id),
                channel_name="specific.channel.1",
            )

            second_seen = (
                await Device.objects.aget(id=self.device_id)
            ).last_seen_at

            self.assertEqual(first_seen, second_seen)

            self.assertIn(
                presence_device_last_seen_write_key(self.device_id),
                self.redis.values,
            )
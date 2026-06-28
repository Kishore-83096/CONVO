import uuid
from collections import defaultdict
from datetime import timedelta

from channels.testing import WebsocketCommunicator
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from unittest.mock import patch

from apps.e2ee_devices.models import Device
from apps.realtime.events import (
    CONNECTION_ACCEPTED,
    HEARTBEAT_ACK,
    PRESENCE_CHANGED,
    PRESENCE_HIDDEN,
)
from apps.realtime.models import RealtimeTicket
from apps.realtime.services import hash_realtime_ticket
from apps.rooms.models import Room, RoomMember
from apps.chat_messages.models import ContactDeliveryPolicy
from messenger_config.asgi import application


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
    REALTIME_HEARTBEAT_SECONDS=20,
    REALTIME_PRESENCE_TTL_SECONDS=45,
)
class PresenceLifecyclePublishTests(TransactionTestCase):
    reset_sequences = True

    subject_device_id = uuid.UUID(
        "11111111-1111-4111-8111-111111111111"
    )
    viewer_device_id = uuid.UUID(
        "22222222-2222-4222-8222-222222222222"
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

        self.viewer_device = Device.objects.create(
            id=self.viewer_device_id,
            user_id="viewer",
            device_name="Viewer browser",
            platform=Device.Platform.WEB,
            registration_id=20001,
            identity_key_public="VIEWER_IDENTITY",
            signed_prekey_id=1,
            signed_prekey_public="VIEWER_SIGNED_PREKEY",
            signed_prekey_signature="VIEWER_SIGNATURE",
            key_algorithm="curve25519",
            key_bundle_version=1,
            is_active=True,
        )

        pair_key = Room.build_direct_pair_key(
            "A",
            "viewer",
        )

        self.room = Room.objects.create(
            room_type=Room.RoomType.DIRECT,
            name="",
            created_by_user_id="A",
            direct_pair_key=pair_key,
            is_active=True,
        )

        RoomMember.objects.create(
            room=self.room,
            user_id="A",
            role=RoomMember.Role.MEMBER,
            added_by_user_id="A",
            is_active=True,
        )

        RoomMember.objects.create(
            room=self.room,
            user_id="viewer",
            role=RoomMember.Role.MEMBER,
            added_by_user_id="A",
            is_active=True,
        )

    def patch_redis(self):
        return patch(
            "apps.realtime.presence.get_redis_client",
            return_value=self.redis,
        )

    async def create_ticket(
        self,
        *,
        user_id: str,
        device: Device,
        raw_ticket: str,
    ) -> RealtimeTicket:
        return await RealtimeTicket.objects.acreate(
            ticket_hash=hash_realtime_ticket(raw_ticket),
            user_id=user_id,
            device=device,
            expires_at=timezone.now() + timedelta(minutes=1),
        )

    async def connect_user(
        self,
        *,
        raw_ticket: str,
        user_id: str,
        device: Device,
    ):
        await self.create_ticket(
            user_id=user_id,
            device=device,
            raw_ticket=raw_ticket,
        )

        communicator = WebsocketCommunicator(
            application,
            f"/ws/messenger/?ticket={raw_ticket}",
        )

        connected, extra = await communicator.connect()

        self.assertTrue(
            connected,
            extra,
        )

        accepted_event = await communicator.receive_json_from()

        self.assertEqual(
            accepted_event["type"],
            CONNECTION_ACCEPTED,
        )

        return communicator

    async def test_subject_connect_publishes_presence_changed_to_related_viewer(self):
        with self.patch_redis():
            viewer_socket = await self.connect_user(
                raw_ticket="viewer-ticket-connect",
                user_id="viewer",
                device=self.viewer_device,
            )

            subject_socket = await self.connect_user(
                raw_ticket="subject-ticket-connect",
                user_id="A",
                device=self.subject_device,
            )

            presence_event = await viewer_socket.receive_json_from()

            self.assertEqual(
                presence_event["type"],
                PRESENCE_CHANGED,
            )
            self.assertEqual(
                presence_event["data"]["presence"]["user_id"],
                "A",
            )
            self.assertEqual(
                presence_event["data"]["presence"]["status"],
                "online",
            )
            self.assertEqual(
                presence_event["data"]["presence"]["online_device_ids"],
                [str(self.subject_device_id)],
            )
            self.assertIsNotNone(
                presence_event["data"]["presence"]["last_seen_at"],
            )
            self.assertNotIn(
                "reason",
                presence_event["data"]["presence"],
            )

            await subject_socket.disconnect()
            await viewer_socket.disconnect()

    async def test_subject_connect_publishes_presence_hidden_to_blocked_viewer(self):
        await ContactDeliveryPolicy.objects.acreate(
            owner_user_id="A",
            target_user_id="viewer",
            is_blocked=True,
            policy_version=1,
        )

        with self.patch_redis():
            viewer_socket = await self.connect_user(
                raw_ticket="viewer-ticket-blocked",
                user_id="viewer",
                device=self.viewer_device,
            )

            subject_socket = await self.connect_user(
                raw_ticket="subject-ticket-blocked",
                user_id="A",
                device=self.subject_device,
            )

            presence_event = await viewer_socket.receive_json_from()

            self.assertEqual(
                presence_event["type"],
                PRESENCE_HIDDEN,
            )
            self.assertEqual(
                presence_event["data"]["presence"]["user_id"],
                "A",
            )
            self.assertEqual(
                presence_event["data"]["presence"]["status"],
                "unavailable",
            )
            self.assertEqual(
                presence_event["data"]["presence"]["online_device_ids"],
                [],
            )
            self.assertIsNone(
                presence_event["data"]["presence"]["last_seen_at"],
            )
            self.assertNotIn(
                "reason",
                presence_event["data"]["presence"],
            )
            self.assertNotIn(
                "blocked",
                presence_event["data"]["presence"],
            )

            await subject_socket.disconnect()
            await viewer_socket.disconnect()

    async def test_subject_disconnect_publishes_offline_to_related_viewer(self):
        with self.patch_redis():
            viewer_socket = await self.connect_user(
                raw_ticket="viewer-ticket-disconnect",
                user_id="viewer",
                device=self.viewer_device,
            )

            subject_socket = await self.connect_user(
                raw_ticket="subject-ticket-disconnect",
                user_id="A",
                device=self.subject_device,
            )

            online_event = await viewer_socket.receive_json_from()

            self.assertEqual(
                online_event["type"],
                PRESENCE_CHANGED,
            )
            self.assertEqual(
                online_event["data"]["presence"]["status"],
                "online",
            )

            await subject_socket.disconnect()

            offline_event = await viewer_socket.receive_json_from()

            self.assertEqual(
                offline_event["type"],
                PRESENCE_CHANGED,
            )
            self.assertEqual(
                offline_event["data"]["presence"]["user_id"],
                "A",
            )
            self.assertEqual(
                offline_event["data"]["presence"]["status"],
                "offline",
            )
            self.assertEqual(
                offline_event["data"]["presence"]["online_device_ids"],
                [],
            )
            self.assertIsNotNone(
                offline_event["data"]["presence"]["last_seen_at"],
            )

            await viewer_socket.disconnect()

    async def test_heartbeat_ack_does_not_publish_presence_spam_to_viewer(self):
        with self.patch_redis():
            viewer_socket = await self.connect_user(
                raw_ticket="viewer-ticket-heartbeat",
                user_id="viewer",
                device=self.viewer_device,
            )

            subject_socket = await self.connect_user(
                raw_ticket="subject-ticket-heartbeat",
                user_id="A",
                device=self.subject_device,
            )

            initial_presence_event = await viewer_socket.receive_json_from()

            self.assertEqual(
                initial_presence_event["type"],
                PRESENCE_CHANGED,
            )

            await subject_socket.send_json_to(
                {
                    "type": "heartbeat",
                }
            )

            heartbeat_ack = await subject_socket.receive_json_from()

            self.assertEqual(
                heartbeat_ack["type"],
                HEARTBEAT_ACK,
            )

            self.assertTrue(
                await viewer_socket.receive_nothing(
                    timeout=0.05,
                )
            )

            await subject_socket.disconnect()
            await viewer_socket.disconnect()
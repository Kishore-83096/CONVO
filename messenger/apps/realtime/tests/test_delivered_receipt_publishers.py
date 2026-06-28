import asyncio
import uuid
from datetime import timedelta

from channels.layers import get_channel_layer
from django.test import TransactionTestCase, override_settings
from django.utils import timezone

from apps.chat_messages.models import (
    ContactDeliveryPolicy,
    Message,
    MessageReceipt,
)
from apps.e2ee_devices.models import Device
from apps.realtime.events import MESSAGE_DELIVERED
from apps.realtime.publishers import (
    make_device_group_name,
    publish_message_delivered,
)
from apps.rooms.models import Room, RoomMember


TEST_CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    },
}


@override_settings(
    CHANNEL_LAYERS=TEST_CHANNEL_LAYERS,
)
class DeliveredReceiptPublisherTests(TransactionTestCase):
    reset_sequences = True

    sender_device_id = uuid.UUID(
        "11111111-1111-4111-8111-111111111111"
    )
    recipient_device_id = uuid.UUID(
        "22222222-2222-4222-8222-222222222222"
    )

    def setUp(self):
        self.sender_device = Device.objects.create(
            id=self.sender_device_id,
            user_id="1",
            device_name="Sender browser",
            platform=Device.Platform.WEB,
            registration_id=10001,
            identity_key_public="SENDER_IDENTITY",
            signed_prekey_id=1,
            signed_prekey_public="SENDER_SIGNED_PREKEY",
            signed_prekey_signature="SENDER_SIGNATURE",
            key_algorithm="curve25519",
            key_bundle_version=1,
            is_active=True,
        )

        self.recipient_device = Device.objects.create(
            id=self.recipient_device_id,
            user_id="2",
            device_name="Recipient browser",
            platform=Device.Platform.WEB,
            registration_id=20001,
            identity_key_public="RECIPIENT_IDENTITY",
            signed_prekey_id=1,
            signed_prekey_public="RECIPIENT_SIGNED_PREKEY",
            signed_prekey_signature="RECIPIENT_SIGNATURE",
            key_algorithm="curve25519",
            key_bundle_version=1,
            is_active=True,
        )

        self.room = Room.objects.create(
            room_type=Room.RoomType.DIRECT,
            name="",
            created_by_user_id="1",
            direct_pair_key=Room.build_direct_pair_key(
                "1",
                "2",
            ),
            is_active=True,
        )

        RoomMember.objects.create(
            room=self.room,
            user_id="1",
            role=RoomMember.Role.MEMBER,
            added_by_user_id="1",
            is_active=True,
        )

        RoomMember.objects.create(
            room=self.room,
            user_id="2",
            role=RoomMember.Role.MEMBER,
            added_by_user_id="1",
            is_active=True,
        )

        self.message = Message.objects.create(
            room=self.room,
            sender_user_id="1",
            sender_device_id=str(self.sender_device_id),
            client_message_id=uuid.UUID(
                "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
            ),
            message_type=Message.MessageType.TEXT,
            encrypted_payload="DIRECT_CIPHERTEXT",
            encryption_metadata={
                "algorithm": "xchacha20poly1305",
                "nonce": "DIRECT_NONCE",
            },
            encryption_version=1,
        )

        self.receipt = MessageReceipt.objects.create(
            message=self.message,
            recipient_user_id="2",
            recipient_device=self.recipient_device,
            delivered_at=timezone.now(),
        )

    async def test_publish_message_delivered_sends_to_sender_device_group(self):
        channel_layer = get_channel_layer()
        sender_channel = await channel_layer.new_channel()

        await channel_layer.group_add(
            make_device_group_name(str(self.sender_device_id)),
            sender_channel,
        )

        result = await publish_message_delivered(
            receipt_id=str(self.receipt.id),
        )

        self.assertEqual(result.sent_count, 1)
        self.assertFalse(result.skipped)
        self.assertEqual(
            result.sender_device_ids,
            (
                str(self.sender_device_id),
            ),
        )

        event = await channel_layer.receive(sender_channel)
        payload = event["payload"]

        self.assertEqual(event["type"], "realtime.event")
        self.assertEqual(payload["type"], MESSAGE_DELIVERED)
        self.assertIn("event_id", payload)
        self.assertIn("created_at", payload)

        data = payload["data"]

        self.assertEqual(data["room_id"], str(self.room.id))
        self.assertEqual(data["message_id"], str(self.message.id))
        self.assertEqual(data["recipient_user_id"], "2")
        self.assertEqual(
            data["recipient_device_id"],
            str(self.recipient_device_id),
        )
        self.assertIsNotNone(data["delivered_at"])

        self.assertNotIn("encrypted_payload", data)
        self.assertNotIn("wrapped_message_key", data)
        self.assertNotIn("recovery_envelopes", data)
        self.assertNotIn("plaintext", data)

    async def test_publish_message_delivered_is_skipped_when_reader_policy_suppresses_sender(self):
        """
        User 2 ghosts user 1.

        Even if a receipt exists, publisher must not send message.delivered
        to user 1.
        """

        await ContactDeliveryPolicy.objects.acreate(
            owner_user_id="2",
            target_user_id="1",
            is_blocked=False,
            ghost_until=timezone.now() + timedelta(hours=1),
            ghost_permanent=False,
            ghost_duration_option="1h",
            policy_version=1,
        )

        channel_layer = get_channel_layer()
        sender_channel = await channel_layer.new_channel()

        await channel_layer.group_add(
            make_device_group_name(str(self.sender_device_id)),
            sender_channel,
        )

        result = await publish_message_delivered(
            receipt_id=str(self.receipt.id),
        )

        self.assertEqual(result.sent_count, 0)
        self.assertTrue(result.skipped)

        with self.assertRaises(asyncio.TimeoutError):
            await asyncio.wait_for(
                channel_layer.receive(sender_channel),
                timeout=0.05,
            )
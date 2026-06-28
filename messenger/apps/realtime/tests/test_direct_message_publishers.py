import uuid

from channels.layers import get_channel_layer
from django.test import TransactionTestCase, override_settings

from apps.chat_messages.models import Message, MessageKeyEnvelope
from apps.e2ee_devices.models import Device
from apps.realtime.events import MESSAGE_STORED
from apps.realtime.publishers import (
    make_device_group_name,
    publish_direct_message_stored,
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
class DirectMessagePublisherTests(TransactionTestCase):
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

        MessageKeyEnvelope.objects.create(
            message=self.message,
            recipient_user_id="1",
            recipient_device=self.sender_device,
            protocol=MessageKeyEnvelope.Protocol.DEVICE_SYNC,
            session_reference="sender-sync-session",
            wrapped_message_key="WRAPPED_KEY_FOR_SENDER",
            key_wrap_metadata={
                "algorithm": "device-sync-v1",
            },
            envelope_version=1,
        )

        MessageKeyEnvelope.objects.create(
            message=self.message,
            recipient_user_id="2",
            recipient_device=self.recipient_device,
            protocol=MessageKeyEnvelope.Protocol.DOUBLE_RATCHET,
            session_reference="recipient-ratchet-session",
            wrapped_message_key="WRAPPED_KEY_FOR_RECIPIENT",
            key_wrap_metadata={
                "algorithm": "double-ratchet",
            },
            envelope_version=1,
        )

    async def test_publish_direct_message_stored_sends_to_recipient_device_group(self):
        channel_layer = get_channel_layer()
        channel_name = await channel_layer.new_channel()

        await channel_layer.group_add(
            make_device_group_name(str(self.recipient_device_id)),
            channel_name,
        )

        result = await publish_direct_message_stored(
            message_id=str(self.message.id),
            recipient_user_id="2",
        )

        self.assertEqual(result.sent_count, 1)
        self.assertFalse(result.skipped)
        self.assertEqual(
            result.recipient_device_ids,
            (
                str(self.recipient_device_id),
            ),
        )

        event = await channel_layer.receive(channel_name)
        payload = event["payload"]

        self.assertEqual(event["type"], "realtime.event")
        self.assertEqual(payload["type"], MESSAGE_STORED)
        self.assertIn("event_id", payload)
        self.assertIn("created_at", payload)

        data = payload["data"]

        self.assertEqual(data["room_id"], str(self.room.id))
        self.assertEqual(data["message_id"], str(self.message.id))
        self.assertEqual(
            data["client_message_id"],
            str(self.message.client_message_id),
        )
        self.assertEqual(data["sender_user_id"], "1")
        self.assertEqual(data["message_type"], "text")
        self.assertTrue(data["requires_fetch"])

        self.assertNotIn("encrypted_payload", data)
        self.assertNotIn("wrapped_message_key", data)
        self.assertNotIn("recovery_envelopes", data)

    async def test_publish_direct_message_stored_skips_when_no_recipient_envelope(self):
        result = await publish_direct_message_stored(
            message_id=str(self.message.id),
            recipient_user_id="3",
        )

        self.assertEqual(result.sent_count, 0)
        self.assertTrue(result.skipped)
        self.assertEqual(result.recipient_device_ids, tuple())
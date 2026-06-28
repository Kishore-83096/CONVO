import asyncio
import uuid

from channels.layers import get_channel_layer
from django.test import TransactionTestCase, override_settings

from apps.chat_messages.models import GroupMessageEncryption, Message
from apps.e2ee_devices.models import Device
from apps.group_chat.models import (
    GroupEncryptionEpoch,
    GroupSenderKey,
)
from apps.group_chat.tests.factories import create_group_room
from apps.realtime.events import GROUP_MESSAGE_STORED
from apps.realtime.publishers import (
    make_device_group_name,
    publish_group_message_stored,
)


TEST_CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    },
}


@override_settings(
    CHANNEL_LAYERS=TEST_CHANNEL_LAYERS,
)
class GroupMessagePublisherTests(TransactionTestCase):
    reset_sequences = True

    sender_device_id = uuid.UUID(
        "11111111-1111-4111-8111-111111111111"
    )
    recipient_device_id = uuid.UUID(
        "22222222-2222-4222-8222-222222222222"
    )
    sender_second_device_id = uuid.UUID(
        "33333333-3333-4333-8333-333333333333"
    )

    def setUp(self):
        self.profile = create_group_room(
            owner_user_id="1",
            member_user_ids=[
                "2",
            ],
        )

        self.epoch = GroupEncryptionEpoch.objects.get(
            group_room=self.profile.room,
            status=GroupEncryptionEpoch.Status.ACTIVE,
        )

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

        self.sender_second_device = Device.objects.create(
            id=self.sender_second_device_id,
            user_id="1",
            device_name="Sender phone",
            platform=Device.Platform.ANDROID,
            registration_id=10002,
            identity_key_public="SENDER_SECOND_IDENTITY",
            signed_prekey_id=2,
            signed_prekey_public="SENDER_SECOND_SIGNED_PREKEY",
            signed_prekey_signature="SENDER_SECOND_SIGNATURE",
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

        self.sender_key = GroupSenderKey.objects.create(
            group_room=self.profile.room,
            epoch=self.epoch,
            sender_user_id="1",
            sender_device=self.sender_device,
            sender_key_id=uuid.UUID(
                "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
            ),
            signing_public_key="SENDER_SIGNING_PUBLIC",
            key_algorithm="group-sender-key-v1",
            signing_algorithm="ed25519",
            key_version=1,
            highest_accepted_iteration=1,
            is_active=True,
        )

        self.message = Message.objects.create(
            room=self.profile.room,
            sender_user_id="1",
            sender_device_id=str(self.sender_device_id),
            client_message_id=uuid.UUID(
                "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
            ),
            message_type=Message.MessageType.TEXT,
            encrypted_payload="GROUP_CIPHERTEXT",
            encryption_metadata={
                "algorithm": "group-sender-key-v1",
                "nonce": "GROUP_NONCE",
            },
            encryption_version=1,
        )

        self.group_encryption = GroupMessageEncryption.objects.create(
            message=self.message,
            group_room=self.profile.room,
            epoch=self.epoch,
            sender_key=self.sender_key,
            chain_iteration=1,
            signature="GROUP_SIGNATURE",
            encryption_metadata={
                "algorithm": "group-sender-key-v1",
                "nonce": "GROUP_NONCE",
            },
        )

    async def test_publish_group_message_stored_sends_to_active_member_devices_except_sender_device(self):
        channel_layer = get_channel_layer()

        recipient_channel = await channel_layer.new_channel()
        sender_second_channel = await channel_layer.new_channel()
        sender_current_channel = await channel_layer.new_channel()

        await channel_layer.group_add(
            make_device_group_name(str(self.recipient_device_id)),
            recipient_channel,
        )
        await channel_layer.group_add(
            make_device_group_name(str(self.sender_second_device_id)),
            sender_second_channel,
        )
        await channel_layer.group_add(
            make_device_group_name(str(self.sender_device_id)),
            sender_current_channel,
        )

        result = await publish_group_message_stored(
            message_id=str(self.message.id),
            sender_device_id=str(self.sender_device_id),
        )

        self.assertEqual(result.sent_count, 2)
        self.assertFalse(result.skipped)
        self.assertEqual(result.group_id, str(self.profile.room.id))
        self.assertEqual(
            result.recipient_device_ids,
            (
                str(self.recipient_device_id),
                str(self.sender_second_device_id),
            ),
        )

        recipient_event = await channel_layer.receive(recipient_channel)
        sender_second_event = await channel_layer.receive(sender_second_channel)

        for event in [
            recipient_event,
            sender_second_event,
        ]:
            payload = event["payload"]

            self.assertEqual(event["type"], "realtime.event")
            self.assertEqual(payload["type"], GROUP_MESSAGE_STORED)
            self.assertIn("event_id", payload)
            self.assertIn("created_at", payload)

            data = payload["data"]

            self.assertEqual(data["room_id"], str(self.profile.room.id))
            self.assertEqual(data["group_id"], str(self.profile.room.id))
            self.assertEqual(data["message_id"], str(self.message.id))
            self.assertEqual(
                data["client_message_id"],
                str(self.message.client_message_id),
            )
            self.assertEqual(data["sender_user_id"], "1")
            self.assertEqual(data["sender_device_id"], str(self.sender_device_id))
            self.assertEqual(data["message_type"], "text")
            self.assertEqual(data["epoch_number"], self.epoch.epoch_number)
            self.assertEqual(
                data["sender_key_id"],
                str(self.sender_key.sender_key_id),
            )
            self.assertEqual(data["chain_iteration"], 1)
            self.assertTrue(data["requires_fetch"])

            self.assertNotIn("encrypted_payload", data)
            self.assertNotIn("signature", data)
            self.assertNotIn("sender_chain_secret", data)
            self.assertNotIn("message_key", data)
            self.assertNotIn("recovery_envelopes", data)

        with self.assertRaises(asyncio.TimeoutError):
            await asyncio.wait_for(
                channel_layer.receive(sender_current_channel),
                timeout=0.05,
            )

    async def test_publish_group_message_stored_skips_when_no_recipient_devices(self):
        await Device.objects.filter(
            id=self.sender_second_device_id,
        ).aupdate(
            is_active=False,
        )

        await Device.objects.filter(
            id=self.recipient_device_id,
        ).aupdate(
            is_active=False,
        )

        result = await publish_group_message_stored(
            message_id=str(self.message.id),
            sender_device_id=str(self.sender_device_id),
        )

        self.assertEqual(result.sent_count, 0)
        self.assertTrue(result.skipped)
        self.assertEqual(result.recipient_device_ids, tuple())
import uuid
from unittest.mock import patch

from django.core.management import call_command
from django.test import TransactionTestCase, override_settings

from apps.chat_messages.models import Message, MessageKeyEnvelope
from apps.e2ee_devices.models import Device
from apps.realtime.events import MESSAGE_STORED, build_event
from apps.realtime.models import RealtimeOutboxEvent
from apps.realtime.outbox import retry_pending_realtime_outbox_events
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


class FailingChannelLayer:
    async def group_send(self, group, message):
        raise ConnectionError("redis unavailable")


class RecordingChannelLayer:
    def __init__(self):
        self.sent = []

    async def group_send(self, group, message):
        self.sent.append(
            {
                "group": group,
                "message": message,
            }
        )


@override_settings(
    CHANNEL_LAYERS=TEST_CHANNEL_LAYERS,
)
class RealtimeOutboxTests(TransactionTestCase):
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

    async def test_failed_direct_message_publish_creates_pending_outbox_event(self):
        with patch(
            "apps.realtime.outbox.get_channel_layer",
            return_value=FailingChannelLayer(),
        ):
            result = await publish_direct_message_stored(
                message_id=str(self.message.id),
                recipient_user_id="2",
            )

        self.assertEqual(result.sent_count, 0)
        self.assertFalse(result.skipped)

        self.assertEqual(
            await RealtimeOutboxEvent.objects.acount(),
            1,
        )

        outbox_event = await RealtimeOutboxEvent.objects.aget()

        self.assertEqual(
            outbox_event.event_type,
            MESSAGE_STORED,
        )
        self.assertEqual(
            outbox_event.target_group,
            make_device_group_name(str(self.recipient_device_id)),
        )
        self.assertEqual(
            outbox_event.status,
            RealtimeOutboxEvent.Status.PENDING,
        )
        self.assertEqual(
            outbox_event.payload["type"],
            MESSAGE_STORED,
        )
        self.assertEqual(
            outbox_event.payload["data"]["message_id"],
            str(self.message.id),
        )
        self.assertIn(
            "redis unavailable",
            outbox_event.last_error,
        )

    def test_retry_pending_outbox_event_marks_delivered(self):
        recording_layer = RecordingChannelLayer()
        target_group = make_device_group_name(
            str(self.recipient_device_id),
        )
        payload = build_event(
            MESSAGE_STORED,
            {
                "message_id": str(self.message.id),
                "requires_fetch": True,
            },
        )

        outbox_event = RealtimeOutboxEvent.objects.create(
            event_type=MESSAGE_STORED,
            target_group=target_group,
            payload=payload,
        )

        with patch(
            "apps.realtime.outbox.get_channel_layer",
            return_value=recording_layer,
        ):
            result = retry_pending_realtime_outbox_events(
                limit=10,
            )

        self.assertEqual(
            result,
            {
                "attempted": 1,
                "delivered": 1,
                "failed": 0,
            },
        )

        outbox_event.refresh_from_db()

        self.assertEqual(
            outbox_event.status,
            RealtimeOutboxEvent.Status.DELIVERED,
        )
        self.assertEqual(outbox_event.attempts, 1)
        self.assertIsNotNone(outbox_event.delivered_at)
        self.assertEqual(outbox_event.last_error, "")

        self.assertEqual(len(recording_layer.sent), 1)
        self.assertEqual(
            recording_layer.sent[0]["group"],
            target_group,
        )
        self.assertEqual(
            recording_layer.sent[0]["message"]["payload"]["type"],
            MESSAGE_STORED,
        )

    def test_retry_realtime_outbox_management_command(self):
        recording_layer = RecordingChannelLayer()
        target_group = make_device_group_name(
            str(self.recipient_device_id),
        )

        RealtimeOutboxEvent.objects.create(
            event_type=MESSAGE_STORED,
            target_group=target_group,
            payload=build_event(
                MESSAGE_STORED,
                {
                    "message_id": str(self.message.id),
                    "requires_fetch": True,
                },
            ),
        )

        with patch(
            "apps.realtime.outbox.get_channel_layer",
            return_value=recording_layer,
        ):
            call_command(
                "retry_realtime_outbox",
                "--limit",
                "5",
            )

        self.assertEqual(
            RealtimeOutboxEvent.objects.filter(
                status=RealtimeOutboxEvent.Status.DELIVERED,
            ).count(),
            1,
        )
        self.assertEqual(len(recording_layer.sent), 1)
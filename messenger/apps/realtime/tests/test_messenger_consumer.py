import uuid
from datetime import timedelta

from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from django.test import TransactionTestCase, override_settings
from django.utils import timezone

from apps.e2ee_devices.models import Device
from apps.realtime.consumers import (
    make_device_group_name,
    make_user_group_name,
)
from apps.realtime.events import (
    CONNECTION_ACCEPTED,
    HEARTBEAT_ACK,
    RECONCILIATION_REQUIRED,
    build_event,
)
from apps.realtime.models import RealtimeTicket
from apps.realtime.services import hash_realtime_ticket
from messenger_config.asgi import application


TEST_CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    },
}


@override_settings(
    CHANNEL_LAYERS=TEST_CHANNEL_LAYERS,
    REALTIME_HEARTBEAT_SECONDS=20,
)
class MessengerConsumerTests(TransactionTestCase):
    reset_sequences = True

    device_id = uuid.UUID(
        "11111111-1111-4111-8111-111111111111"
    )

    def setUp(self):
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

    async def create_ticket(self, raw_ticket: str) -> RealtimeTicket:
        return await RealtimeTicket.objects.acreate(
            ticket_hash=hash_realtime_ticket(raw_ticket),
            user_id="1",
            device=self.device,
            expires_at=timezone.now() + timedelta(minutes=1),
        )

    async def connect_with_ticket(self, raw_ticket: str):
        await self.create_ticket(raw_ticket)

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

        return communicator, accepted_event

    async def test_valid_ticket_connects_and_receives_connection_accepted(self):
        communicator, accepted_event = await self.connect_with_ticket(
            "consumer-valid-ticket",
        )

        self.assertIn("event_id", accepted_event)
        self.assertIn("created_at", accepted_event)

        data = accepted_event["data"]

        self.assertEqual(data["user_id"], "1")
        self.assertEqual(data["device_id"], str(self.device_id))
        self.assertEqual(data["heartbeat_seconds"], 20)

        await communicator.disconnect()

    async def test_missing_ticket_is_rejected_by_root_asgi_application(self):
        communicator = WebsocketCommunicator(
            application,
            "/ws/messenger/",
        )

        connected, close_code = await communicator.connect()

        self.assertFalse(connected)
        self.assertEqual(close_code, 4401)

    async def test_ticket_is_one_use(self):
        raw_ticket = "consumer-one-use-ticket"

        await self.create_ticket(raw_ticket)

        first = WebsocketCommunicator(
            application,
            f"/ws/messenger/?ticket={raw_ticket}",
        )

        first_connected, _ = await first.connect()

        self.assertTrue(first_connected)

        await first.receive_json_from()
        await first.disconnect()

        second = WebsocketCommunicator(
            application,
            f"/ws/messenger/?ticket={raw_ticket}",
        )

        second_connected, second_close_code = await second.connect()

        self.assertFalse(second_connected)
        self.assertEqual(second_close_code, 4401)

    async def test_heartbeat_receives_ack(self):
        communicator, _ = await self.connect_with_ticket(
            "consumer-heartbeat-ticket",
        )

        await communicator.send_json_to(
            {
                "type": "heartbeat",
            }
        )

        event = await communicator.receive_json_from()

        self.assertEqual(event["type"], HEARTBEAT_ACK)
        self.assertIn("event_id", event)
        self.assertIn("created_at", event)
        self.assertEqual(event["data"]["user_id"], "1")
        self.assertEqual(event["data"]["device_id"], str(self.device_id))
        self.assertEqual(event["data"]["heartbeat_seconds"], 20)

        await communicator.disconnect()

    async def test_unknown_client_event_receives_client_error(self):
        communicator, _ = await self.connect_with_ticket(
            "consumer-unknown-event-ticket",
        )

        await communicator.send_json_to(
            {
                "type": "message.send",
            }
        )

        event = await communicator.receive_json_from()

        self.assertEqual(event["type"], "client.error")
        self.assertEqual(
            event["data"]["code"],
            "unsupported_event_type",
        )

        await communicator.disconnect()

    async def test_user_group_event_is_forwarded_to_socket(self):
        communicator, _ = await self.connect_with_ticket(
            "consumer-user-group-ticket",
        )

        channel_layer = get_channel_layer()

        payload = build_event(
            RECONCILIATION_REQUIRED,
            {
                "reason": "user_group_test",
            },
        )

        await channel_layer.group_send(
            make_user_group_name("1"),
            {
                "type": "realtime.event",
                "payload": payload,
            },
        )

        event = await communicator.receive_json_from()

        self.assertEqual(event["type"], RECONCILIATION_REQUIRED)
        self.assertEqual(event["data"]["reason"], "user_group_test")

        await communicator.disconnect()

    async def test_device_group_event_is_forwarded_to_socket(self):
        communicator, _ = await self.connect_with_ticket(
            "consumer-device-group-ticket",
        )

        channel_layer = get_channel_layer()

        payload = build_event(
            RECONCILIATION_REQUIRED,
            {
                "reason": "device_group_test",
            },
        )

        await channel_layer.group_send(
            make_device_group_name(str(self.device_id)),
            {
                "type": "realtime.event",
                "payload": payload,
            },
        )

        event = await communicator.receive_json_from()

        self.assertEqual(event["type"], RECONCILIATION_REQUIRED)
        self.assertEqual(event["data"]["reason"], "device_group_test")

        await communicator.disconnect()
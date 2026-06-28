import json
import uuid
from datetime import timedelta

from channels.testing import WebsocketCommunicator
from django.test import TransactionTestCase, override_settings
from django.utils import timezone

from apps.e2ee_devices.models import Device
from apps.realtime.authentication import (
    WEBSOCKET_AUTH_CLOSE_CODE,
    RealtimeTicketAuthMiddleware,
)
from apps.realtime.models import RealtimeTicket
from apps.realtime.services import hash_realtime_ticket


async def authenticated_scope_echo_app(scope, receive, send):
    """
    Tiny ASGI app used only for middleware tests.

    If middleware authenticates successfully, this app accepts the socket
    and sends back selected scope values.
    """

    await receive()

    await send(
        {
            "type": "websocket.accept",
        }
    )

    await send(
        {
            "type": "websocket.send",
            "text": json.dumps(
                {
                    "user_id": scope["myna_user_id"],
                    "device_id": scope["myna_device_id"],
                    "ticket_id": str(scope["realtime_ticket"].id),
                }
            ),
        }
    )

    await send(
        {
            "type": "websocket.close",
            "code": 1000,
        }
    )


@override_settings(REALTIME_TICKET_TTL_SECONDS=60)
class RealtimeTicketAuthMiddlewareTests(TransactionTestCase):
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

        self.application = RealtimeTicketAuthMiddleware(
            authenticated_scope_echo_app,
        )

    def create_ticket(
        self,
        *,
        raw_ticket: str = "valid-ticket",
        expires_at=None,
        used_at=None,
        device=None,
    ) -> RealtimeTicket:
        return RealtimeTicket.objects.create(
            ticket_hash=hash_realtime_ticket(raw_ticket),
            user_id="1",
            device=device or self.device,
            expires_at=expires_at or timezone.now() + timedelta(minutes=1),
            used_at=used_at,
        )

    async def test_valid_ticket_authenticates_and_marks_ticket_used(self):
        raw_ticket = "valid-ticket"
        ticket = await RealtimeTicket.objects.acreate(
            ticket_hash=hash_realtime_ticket(raw_ticket),
            user_id="1",
            device=self.device,
            expires_at=timezone.now() + timedelta(minutes=1),
        )

        communicator = WebsocketCommunicator(
            self.application,
            f"/ws/messenger/?ticket={raw_ticket}",
        )

        connected, _ = await communicator.connect()

        self.assertTrue(connected)

        message = await communicator.receive_from()
        payload = json.loads(message)

        self.assertEqual(payload["user_id"], "1")
        self.assertEqual(payload["device_id"], str(self.device_id))
        self.assertEqual(payload["ticket_id"], str(ticket.id))

        await communicator.disconnect()

        ticket = await RealtimeTicket.objects.aget(id=ticket.id)

        self.assertIsNotNone(ticket.used_at)

    async def test_missing_ticket_is_rejected(self):
        communicator = WebsocketCommunicator(
            self.application,
            "/ws/messenger/",
        )

        connected, close_code = await communicator.connect()

        self.assertFalse(connected)
        self.assertEqual(close_code, WEBSOCKET_AUTH_CLOSE_CODE)

    async def test_unknown_ticket_is_rejected(self):
        communicator = WebsocketCommunicator(
            self.application,
            "/ws/messenger/?ticket=unknown-ticket",
        )

        connected, close_code = await communicator.connect()

        self.assertFalse(connected)
        self.assertEqual(close_code, WEBSOCKET_AUTH_CLOSE_CODE)

    async def test_expired_ticket_is_rejected(self):
        raw_ticket = "expired-ticket"

        await RealtimeTicket.objects.acreate(
            ticket_hash=hash_realtime_ticket(raw_ticket),
            user_id="1",
            device=self.device,
            expires_at=timezone.now() - timedelta(seconds=1),
        )

        communicator = WebsocketCommunicator(
            self.application,
            f"/ws/messenger/?ticket={raw_ticket}",
        )

        connected, close_code = await communicator.connect()

        self.assertFalse(connected)
        self.assertEqual(close_code, WEBSOCKET_AUTH_CLOSE_CODE)

    async def test_used_ticket_is_rejected(self):
        raw_ticket = "used-ticket"

        await RealtimeTicket.objects.acreate(
            ticket_hash=hash_realtime_ticket(raw_ticket),
            user_id="1",
            device=self.device,
            expires_at=timezone.now() + timedelta(minutes=1),
            used_at=timezone.now(),
        )

        communicator = WebsocketCommunicator(
            self.application,
            f"/ws/messenger/?ticket={raw_ticket}",
        )

        connected, close_code = await communicator.connect()

        self.assertFalse(connected)
        self.assertEqual(close_code, WEBSOCKET_AUTH_CLOSE_CODE)

    async def test_inactive_device_ticket_is_rejected(self):
        raw_ticket = "inactive-device-ticket"

        self.device.is_active = False
        await self.device.asave(
            update_fields=[
                "is_active",
            ]
        )

        await RealtimeTicket.objects.acreate(
            ticket_hash=hash_realtime_ticket(raw_ticket),
            user_id="1",
            device=self.device,
            expires_at=timezone.now() + timedelta(minutes=1),
        )

        communicator = WebsocketCommunicator(
            self.application,
            f"/ws/messenger/?ticket={raw_ticket}",
        )

        connected, close_code = await communicator.connect()

        self.assertFalse(connected)
        self.assertEqual(close_code, WEBSOCKET_AUTH_CLOSE_CODE)
import uuid
from datetime import timedelta

import jwt
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.e2ee_devices.models import Device
from apps.realtime.models import RealtimeTicket
from apps.realtime.services import hash_realtime_ticket


class RealtimeTicketAPITests(APITestCase):
    device_id = uuid.UUID(
        "11111111-1111-4111-8111-111111111111"
    )
    other_device_id = uuid.UUID(
        "22222222-2222-4222-8222-222222222222"
    )
    inactive_device_id = uuid.UUID(
        "33333333-3333-4333-8333-333333333333"
    )

    def setUp(self):
        self.url = reverse("realtime:ticket-create")

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

        self.other_device = Device.objects.create(
            id=self.other_device_id,
            user_id="2",
            device_name="User 2 browser",
            platform=Device.Platform.WEB,
            registration_id=20001,
            identity_key_public="USER_2_IDENTITY",
            signed_prekey_id=1,
            signed_prekey_public="USER_2_SIGNED_PREKEY",
            signed_prekey_signature="USER_2_SIGNATURE",
            key_algorithm="curve25519",
            key_bundle_version=1,
            is_active=True,
        )

        self.inactive_device = Device.objects.create(
            id=self.inactive_device_id,
            user_id="1",
            device_name="Inactive browser",
            platform=Device.Platform.WEB,
            registration_id=30001,
            identity_key_public="USER_1_INACTIVE_IDENTITY",
            signed_prekey_id=1,
            signed_prekey_public="USER_1_INACTIVE_SIGNED_PREKEY",
            signed_prekey_signature="USER_1_INACTIVE_SIGNATURE",
            key_algorithm="curve25519",
            key_bundle_version=1,
            is_active=False,
        )

    def authenticate_as(self, user_id: str):
        now = timezone.now()
        token = jwt.encode(
            {
                "sub": user_id,
                "type": "access",
                "iss": settings.JWT_ISSUER,
                "jti": str(uuid.uuid4()),
                "iat": now,
                "nbf": now,
                "exp": now + timedelta(minutes=5),
            },
            settings.JWT_VERIFYING_KEY,
            algorithm=settings.JWT_ALGORITHM,
        )

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

    def test_ticket_create_requires_authentication(self):
        response = self.client.post(
            self.url,
            {
                "device_id": str(self.device_id),
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(RealtimeTicket.objects.count(), 0)

    def test_ticket_create_requires_device_id(self):
        self.authenticate_as("1")

        response = self.client.post(
            self.url,
            {},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(RealtimeTicket.objects.count(), 0)

    def test_ticket_create_rejects_unknown_device(self):
        self.authenticate_as("1")

        response = self.client.post(
            self.url,
            {
                "device_id": str(
                    uuid.UUID(
                        "99999999-9999-4999-8999-999999999999"
                    )
                ),
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
            response.json(),
        )
        self.assertEqual(RealtimeTicket.objects.count(), 0)

    def test_ticket_create_rejects_device_owned_by_another_user(self):
        self.authenticate_as("1")

        response = self.client.post(
            self.url,
            {
                "device_id": str(self.other_device_id),
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
            response.json(),
        )
        self.assertEqual(RealtimeTicket.objects.count(), 0)

    def test_ticket_create_rejects_inactive_device(self):
        self.authenticate_as("1")

        response = self.client.post(
            self.url,
            {
                "device_id": str(self.inactive_device_id),
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
            response.json(),
        )
        self.assertEqual(RealtimeTicket.objects.count(), 0)

    def test_ticket_create_success_returns_raw_ticket_once(self):
        self.authenticate_as("1")

        response = self.client.post(
            self.url,
            {
                "device_id": str(self.device_id),
            },
            format="json",
            HTTP_USER_AGENT="Myna Test Browser",
            REMOTE_ADDR="127.0.0.1",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
            response.json(),
        )

        payload = response.json()

        self.assertTrue(payload["success"])
        self.assertEqual(
            payload["message"],
            "Realtime ticket created successfully.",
        )

        data = payload["data"]

        self.assertIn("ticket", data)
        self.assertIn("expires_at", data)
        self.assertEqual(data["device_id"], str(self.device_id))
        self.assertEqual(
            data["heartbeat_seconds"],
            settings.REALTIME_HEARTBEAT_SECONDS,
        )

        raw_ticket = data["ticket"]

        self.assertTrue(raw_ticket)
        self.assertEqual(RealtimeTicket.objects.count(), 1)

        ticket_record = RealtimeTicket.objects.get()

        self.assertEqual(ticket_record.user_id, "1")
        self.assertEqual(ticket_record.device_id, self.device_id)
        self.assertIsNone(ticket_record.used_at)
        self.assertFalse(ticket_record.is_used)
        self.assertFalse(ticket_record.is_expired)
        self.assertEqual(ticket_record.ip_address, "127.0.0.1")
        self.assertEqual(ticket_record.user_agent, "Myna Test Browser")

        self.assertNotEqual(ticket_record.ticket_hash, raw_ticket)
        self.assertEqual(
            ticket_record.ticket_hash,
            hash_realtime_ticket(raw_ticket),
        )

    def test_ticket_expiry_uses_realtime_ticket_ttl_setting(self):
        self.authenticate_as("1")

        before_request = timezone.now()

        response = self.client.post(
            self.url,
            {
                "device_id": str(self.device_id),
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
            response.json(),
        )

        after_request = timezone.now()
        ticket_record = RealtimeTicket.objects.get()

        min_expected = before_request + timedelta(
            seconds=settings.REALTIME_TICKET_TTL_SECONDS - 1,
        )
        max_expected = after_request + timedelta(
            seconds=settings.REALTIME_TICKET_TTL_SECONDS + 1,
        )

        self.assertGreaterEqual(
            ticket_record.expires_at,
            min_expected,
        )
        self.assertLessEqual(
            ticket_record.expires_at,
            max_expected,
        )

    def test_each_ticket_request_creates_unique_ticket_hash(self):
        self.authenticate_as("1")

        first_response = self.client.post(
            self.url,
            {
                "device_id": str(self.device_id),
            },
            format="json",
        )
        second_response = self.client.post(
            self.url,
            {
                "device_id": str(self.device_id),
            },
            format="json",
        )

        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second_response.status_code, status.HTTP_201_CREATED)

        self.assertEqual(RealtimeTicket.objects.count(), 2)

        ticket_hashes = set(
            RealtimeTicket.objects.values_list(
                "ticket_hash",
                flat=True,
            )
        )

        self.assertEqual(len(ticket_hashes), 2)
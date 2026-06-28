import uuid
from datetime import timedelta

import jwt
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.e2ee_devices.models import Device

from ..services import send_direct_message


class RoomListAPITests(APITestCase):
    sender_device_id = uuid.UUID(
        "11111111-1111-4111-8111-111111111111"
    )
    recipient_device_id = uuid.UUID(
        "22222222-2222-4222-8222-222222222222"
    )

    def setUp(self):
        Device.objects.create(
            id=self.sender_device_id,
            user_id="1",
            device_name="Sender browser",
            platform="web",
            registration_id=10001,
            identity_key_public="SENDER_IDENTITY_PUBLIC",
            signed_prekey_id=1,
            signed_prekey_public="SENDER_SIGNED_PREKEY",
            signed_prekey_signature="SENDER_SIGNATURE",
            key_algorithm="curve25519",
            key_bundle_version=1,
        )
        Device.objects.create(
            id=self.recipient_device_id,
            user_id="2",
            device_name="Recipient browser",
            platform="web",
            registration_id=20001,
            identity_key_public="RECIPIENT_IDENTITY_PUBLIC",
            signed_prekey_id=1,
            signed_prekey_public="RECIPIENT_SIGNED_PREKEY",
            signed_prekey_signature="RECIPIENT_SIGNATURE",
            key_algorithm="curve25519",
            key_bundle_version=1,
        )

        self.room = send_direct_message(
            sender_user_id="1",
            recipient_user_id="2",
            sender_device_id=self.sender_device_id,
            client_message_id=uuid.UUID(
                "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
            ),
            message_type="text",
            encrypted_payload="ROOM_LIST_CIPHERTEXT",
            encryption_metadata={
                "algorithm": "xchacha20poly1305",
                "nonce": "ROOM_LIST_NONCE",
            },
            encryption_version=1,
            envelopes=[
                {
                    "recipient_device_id": str(
                        self.sender_device_id
                    ),
                    "protocol": "device_sync",
                    "session_reference": "sender-sync-session",
                    "wrapped_message_key": (
                        "WRAPPED_KEY_FOR_SENDER"
                    ),
                    "key_wrap_metadata": {
                        "algorithm": "device-sync-v1",
                    },
                    "envelope_version": 1,
                },
                {
                    "recipient_device_id": str(
                        self.recipient_device_id
                    ),
                    "protocol": "double_ratchet",
                    "session_reference": (
                        "recipient-ratchet-session"
                    ),
                    "wrapped_message_key": (
                        "WRAPPED_KEY_FOR_RECIPIENT"
                    ),
                    "key_wrap_metadata": {
                        "algorithm": "double-ratchet",
                    },
                    "envelope_version": 1,
                },
            ],
        ).room

    def authenticate_as(self, user_id: str):
        now = timezone.now()

        token = jwt.encode(
            {
                "sub": user_id,
                "type": "access",
                "jti": str(uuid.uuid4()),
                "iat": now,
                "nbf": now,
                "exp": now + timedelta(minutes=5),
            },
            settings.JWT_VERIFYING_KEY,
            algorithm=settings.JWT_ALGORITHM,
        )

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token}"
        )

    def assert_room_list_response(self, response):
        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        body = response.json()

        self.assertTrue(body["success"])
        self.assertEqual(len(body["data"]), 1)
        self.assertEqual(body["data"][0]["id"], str(self.room.id))
        self.assertEqual(
            body["data"][0]["other_member_user_ids"],
            ["2"],
        )

    def test_legacy_messages_room_list_route_returns_rooms(self):
        self.authenticate_as("1")

        response = self.client.get(
            reverse("chat_messages:room-list")
        )

        self.assert_room_list_response(response)

    def test_top_level_room_list_route_returns_rooms(self):
        self.authenticate_as("1")

        response = self.client.get("/api/v1/rooms/")

        self.assert_room_list_response(response)

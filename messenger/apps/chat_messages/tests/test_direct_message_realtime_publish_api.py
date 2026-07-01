import uuid
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

import jwt
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.chat_messages.models import (
    ContactDeliveryPolicy,
    Message,
    MessageKeyEnvelope,
)
from apps.e2ee_devices.models import Device
from apps.rooms.models import Room, RoomMember


class DirectMessageRealtimePublishAPITests(APITestCase):
    sender_device_id = uuid.UUID(
        "11111111-1111-4111-8111-111111111111"
    )
    recipient_device_id = uuid.UUID(
        "22222222-2222-4222-8222-222222222222"
    )
    recipient_contact_id = 101

    def setUp(self):
        self.sender_device = Device.objects.create(
            id=self.sender_device_id,
            user_id="1",
            device_name="Sender browser",
            platform=Device.Platform.WEB,
            registration_id=10001,
            identity_key_public="SENDER_IDENTITY_PUBLIC",
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
            identity_key_public="RECIPIENT_IDENTITY_PUBLIC",
            signed_prekey_id=1,
            signed_prekey_public="RECIPIENT_SIGNED_PREKEY",
            signed_prekey_signature="RECIPIENT_SIGNATURE",
            key_algorithm="curve25519",
            key_bundle_version=1,
            is_active=True,
        )

        self.url = reverse("chat_messages:send-direct-message")

        self.resolve_contact_patcher = patch(
            "apps.chat_messages.views.resolve_saved_contact_recipient"
        )
        self.mock_resolve_contact = self.resolve_contact_patcher.start()
        self.addCleanup(self.resolve_contact_patcher.stop)

        self.mock_resolve_contact.return_value = SimpleNamespace(
            contact_id=str(self.recipient_contact_id),
            contact_user_id="2",
            saved_name="Recipient",
            contact_number="9999999999",
        )

        self.publish_patcher = patch(
            "apps.chat_messages.views.schedule_direct_message_stored_publish"
        )
        self.mock_schedule_publish = self.publish_patcher.start()
        self.addCleanup(self.publish_patcher.stop)

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

    def valid_payload(
        self,
        *,
        client_message_id: uuid.UUID | None = None,
        encrypted_payload: str = "AUTOMATED_DIRECT_CIPHERTEXT",
    ) -> dict:
        client_message_id = client_message_id or uuid.UUID(
            "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
        )

        return {
            "recipient_contact_id": self.recipient_contact_id,
            "sender_device_id": str(self.sender_device_id),
            "client_message_id": str(client_message_id),
            "message_type": "text",
            "encrypted_payload": encrypted_payload,
            "encryption_metadata": {
                "algorithm": "xchacha20poly1305",
                "nonce": "AUTOMATED_DIRECT_NONCE",
            },
            "encryption_version": 1,
            "envelopes": [
                {
                    "recipient_device_id": str(self.sender_device_id),
                    "protocol": "device_sync",
                    "session_reference": "sender-sync-session",
                    "wrapped_message_key": "WRAPPED_KEY_FOR_SENDER",
                    "key_wrap_metadata": {
                        "algorithm": "device-sync-v1",
                    },
                    "envelope_version": 1,
                },
                {
                    "recipient_device_id": str(self.recipient_device_id),
                    "protocol": "double_ratchet",
                    "session_reference": "recipient-ratchet-session",
                    "wrapped_message_key": "WRAPPED_KEY_FOR_RECIPIENT",
                    "key_wrap_metadata": {
                        "algorithm": "double-ratchet",
                        "message_number": 1,
                    },
                    "envelope_version": 1,
                },
            ],
        }

    def test_new_direct_message_schedules_realtime_publish(self):
        self.authenticate_as("1")

        response = self.client.post(
            self.url,
            self.valid_payload(),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
            response.json(),
        )

        self.assertEqual(Message.objects.count(), 1)
        self.assertEqual(MessageKeyEnvelope.objects.count(), 2)

        self.mock_schedule_publish.assert_called_once()

        call_kwargs = self.mock_schedule_publish.call_args.kwargs

        self.assertEqual(
            str(call_kwargs["message_id"]),
            response.json()["data"]["message_id"],
        )
        self.assertEqual(
            call_kwargs["recipient_user_id"],
            "2",
        )

    def test_idempotent_retry_does_not_schedule_duplicate_realtime_publish(self):
        self.authenticate_as("1")
        payload = self.valid_payload()

        first_response = self.client.post(
            self.url,
            payload,
            format="json",
        )
        second_response = self.client.post(
            self.url,
            payload,
            format="json",
        )

        self.assertEqual(
            first_response.status_code,
            status.HTTP_201_CREATED,
        )
        self.assertEqual(
            second_response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(Message.objects.count(), 1)
        self.assertEqual(MessageKeyEnvelope.objects.count(), 2)

        self.mock_schedule_publish.assert_called_once()

    def test_blocked_recipient_sender_only_message_does_not_publish_to_recipient(self):
        """
        User 2 blocks user 1.

        User 1 can still send, but the message is stored sender-only.
        Recipient device must not receive message.stored.
        """

        ContactDeliveryPolicy.objects.create(
            owner_user_id="2",
            target_user_id="1",
            is_blocked=True,
            policy_version=1,
        )

        self.authenticate_as("1")

        response = self.client.post(
            self.url,
            self.valid_payload(),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
            response.json(),
        )

        data = response.json()["data"]

        self.assertTrue(data["recipient_delivery_blocked"])
        self.assertEqual(Message.objects.count(), 1)
        self.assertEqual(MessageKeyEnvelope.objects.count(), 1)

        stored_recipient_user_ids = set(
            MessageKeyEnvelope.objects.values_list(
                "recipient_user_id",
                flat=True,
            )
        )

        self.assertEqual(stored_recipient_user_ids, {"1"})

        self.mock_schedule_publish.assert_not_called()
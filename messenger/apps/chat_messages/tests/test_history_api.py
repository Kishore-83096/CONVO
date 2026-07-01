import uuid
from datetime import timedelta
from urllib.parse import parse_qs, urlparse

import jwt
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.chat_messages.models import Message, MessageKeyEnvelope
from apps.e2ee_devices.models import Device
from apps.rooms.models import RoomMember

from ..services import send_direct_message


class EncryptedMessageHistoryAPITests(APITestCase):
    sender_device_id = uuid.UUID(
        "11111111-1111-4111-8111-111111111111"
    )
    recipient_device_id = uuid.UUID(
        "22222222-2222-4222-8222-222222222222"
    )

    unavailable_response = {
        "success": False,
        "message": (
            "Encrypted message history is unavailable "
            "for this room and device."
        ),
    }

    def setUp(self):
        self.sender_device = Device.objects.create(
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

        self.recipient_device = Device.objects.create(
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

        result = send_direct_message(
            sender_user_id="1",
            recipient_user_id="2",
            sender_device_id=self.sender_device_id,
            client_message_id=uuid.UUID(
                "12121212-1212-4212-8212-121212121212"
            ),
            message_type="text",
            encrypted_payload="AUTOMATED_HISTORY_CIPHERTEXT",
            encryption_metadata={
                "algorithm": "xchacha20poly1305",
                "nonce": "AUTOMATED_HISTORY_NONCE",
            },
            encryption_version=1,
            envelopes=[
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
                        "message_number": 1,
                    },
                    "envelope_version": 1,
                },
            ],
        )

        self.room = result.room

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
            HTTP_AUTHORIZATION=f"Bearer {token}"
        )

    def history_url(self):
        return reverse(
            "chat_messages:encrypted-message-history",
            kwargs={
                "room_id": self.room.id,
            },
        )

    def assert_history_unavailable(self, response):
        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(
            response.json(),
            self.unavailable_response,
        )

    def test_authentication_is_required(self):
        response = self.client.get(
            self.history_url(),
            {
                "device_id": str(self.sender_device_id),
            },
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_sender_device_can_retrieve_encrypted_history(self):
        self.authenticate_as("1")

        response = self.client.get(
            self.history_url(),
            {
                "device_id": str(self.sender_device_id),
            },
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        body = response.json()
        messages = body["data"]["messages"]

        self.assertTrue(body["success"])
        self.assertEqual(len(messages), 1)

        message = messages[0]
        envelope = message["device_envelope"]

        self.assertEqual(
            message["encrypted_payload"],
            "AUTOMATED_HISTORY_CIPHERTEXT",
        )
        self.assertEqual(envelope["recipient_user_id"], "1")
        self.assertEqual(
            envelope["recipient_device_id"],
            str(self.sender_device_id),
        )
        self.assertEqual(envelope["protocol"], "device_sync")
        self.assertNotEqual(
            envelope["recipient_device_id"],
            str(self.recipient_device_id),
        )

    def test_recipient_device_can_retrieve_encrypted_history(self):
        self.authenticate_as("2")

        response = self.client.get(
            self.history_url(),
            {
                "device_id": str(self.recipient_device_id),
            },
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        body = response.json()
        messages = body["data"]["messages"]

        self.assertTrue(body["success"])
        self.assertEqual(len(messages), 1)

        message = messages[0]
        envelope = message["device_envelope"]

        self.assertEqual(
            message["encrypted_payload"],
            "AUTOMATED_HISTORY_CIPHERTEXT",
        )
        self.assertEqual(envelope["recipient_user_id"], "2")
        self.assertEqual(
            envelope["recipient_device_id"],
            str(self.recipient_device_id),
        )
        self.assertEqual(envelope["protocol"], "double_ratchet")
        self.assertNotEqual(
            envelope["recipient_device_id"],
            str(self.sender_device_id),
        )

    def test_user_cannot_retrieve_history_for_another_users_device(
        self,
    ):
        self.authenticate_as("1")

        response = self.client.get(
            self.history_url(),
            {
                "device_id": str(self.recipient_device_id),
            },
        )

        self.assert_history_unavailable(response)

    def test_non_member_cannot_retrieve_room_history(self):
        self.authenticate_as("3")

        response = self.client.get(
            self.history_url(),
            {
                "device_id": str(self.sender_device_id),
            },
        )

        self.assert_history_unavailable(response)

    def test_device_id_is_required(self):
        self.authenticate_as("1")

        response = self.client.get(self.history_url())

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            response.json(),
            {
                "success": False,
                "message": "Validation failed.",
                "errors": {
                    "device_id": [
                        "This field is required.",
                    ],
                },
            },
        )

    def test_inactive_device_cannot_retrieve_history(self):
        Device.objects.filter(
            id=self.sender_device_id,
            user_id="1",
        ).update(is_active=False)

        self.authenticate_as("1")

        response = self.client.get(
            self.history_url(),
            {
                "device_id": str(self.sender_device_id),
            },
        )

        self.assert_history_unavailable(response)

    def test_inactive_member_cannot_retrieve_room_history(self):
        RoomMember.objects.filter(
            room=self.room,
            user_id="1",
        ).update(
            is_active=False,
            left_at=timezone.now(),
        )

        self.authenticate_as("1")

        response = self.client.get(
            self.history_url(),
            {
                "device_id": str(self.sender_device_id),
            },
        )

        self.assert_history_unavailable(response)

    def test_inactive_room_cannot_return_history(self):
        self.room.is_active = False
        self.room.save(update_fields=["is_active"])

        self.authenticate_as("1")

        response = self.client.get(
            self.history_url(),
            {
                "device_id": str(self.sender_device_id),
            },
        )

        self.assert_history_unavailable(response)

    def test_invalid_device_id_is_rejected(self):
        self.authenticate_as("1")

        response = self.client.get(
            self.history_url(),
            {
                "device_id": "not-a-valid-uuid",
            },
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        body = response.json()

        self.assertFalse(body["success"])
        self.assertEqual(body["message"], "Validation failed.")
        self.assertIn("device_id", body["errors"])

    def test_message_without_requesting_device_envelope_is_excluded(
        self,
    ):
        hidden_message = Message.objects.create(
            room=self.room,
            sender_user_id="2",
            sender_device_id=str(self.recipient_device_id),
            client_message_id=uuid.UUID(
                "34343434-3434-4434-8434-343434343434"
            ),
            message_type="text",
            encrypted_payload="MUST_NOT_BE_RETURNED",
            encryption_metadata={
                "algorithm": "xchacha20poly1305",
                "nonce": "HIDDEN_MESSAGE_NONCE",
            },
            encryption_version=1,
        )

        MessageKeyEnvelope.objects.create(
            message=hidden_message,
            recipient_user_id="2",
            recipient_device=self.recipient_device,
            protocol="double_ratchet",
            session_reference="recipient-only-session",
            wrapped_message_key="RECIPIENT_ONLY_WRAPPED_KEY",
            key_wrap_metadata={
                "algorithm": "double-ratchet",
                "message_number": 2,
            },
            envelope_version=1,
        )

        self.authenticate_as("1")

        response = self.client.get(
            self.history_url(),
            {
                "device_id": str(self.sender_device_id),
            },
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        messages = response.json()["data"]["messages"]

        self.assertEqual(len(messages), 1)

        returned_message_ids = {
            message["id"]
            for message in messages
        }
        encrypted_payloads = {
            message["encrypted_payload"]
            for message in messages
        }

        self.assertNotIn(
            str(hidden_message.id),
            returned_message_ids,
        )
        self.assertNotIn(
            "MUST_NOT_BE_RETURNED",
            encrypted_payloads,
        )

    def test_cursor_pagination_returns_different_pages(self):
        second_message = Message.objects.create(
            room=self.room,
            sender_user_id="1",
            sender_device_id=str(self.sender_device_id),
            client_message_id=uuid.UUID(
                "56565656-5656-4656-8656-565656565656"
            ),
            message_type="text",
            encrypted_payload="SECOND_PAGE_TEST_CIPHERTEXT",
            encryption_metadata={
                "algorithm": "xchacha20poly1305",
                "nonce": "SECOND_PAGE_TEST_NONCE",
            },
            encryption_version=1,
        )

        MessageKeyEnvelope.objects.create(
            message=second_message,
            recipient_user_id="1",
            recipient_device=self.sender_device,
            protocol="device_sync",
            session_reference="pagination-device-session",
            wrapped_message_key="PAGINATION_WRAPPED_KEY",
            key_wrap_metadata={
                "algorithm": "device-sync-v1",
            },
            envelope_version=1,
        )

        self.authenticate_as("1")

        first_response = self.client.get(
            self.history_url(),
            {
                "device_id": str(self.sender_device_id),
                "page_size": 1,
            },
        )

        self.assertEqual(
            first_response.status_code,
            status.HTTP_200_OK,
        )

        first_body = first_response.json()
        first_messages = first_body["data"]["messages"]
        next_link = first_body["data"]["next"]

        self.assertEqual(len(first_messages), 1)
        self.assertIsNotNone(next_link)

        parsed_next_link = urlparse(next_link)
        next_parameters = {
            key: values[0]
            for key, values in parse_qs(
                parsed_next_link.query
            ).items()
        }

        second_response = self.client.get(
            parsed_next_link.path,
            next_parameters,
        )

        self.assertEqual(
            second_response.status_code,
            status.HTTP_200_OK,
        )

        second_messages = second_response.json()["data"]["messages"]

        self.assertEqual(len(second_messages), 1)
        self.assertNotEqual(
            first_messages[0]["id"],
            second_messages[0]["id"],
        )

        returned_ids = {
            first_messages[0]["id"],
            second_messages[0]["id"],
        }

        self.assertEqual(len(returned_ids), 2)

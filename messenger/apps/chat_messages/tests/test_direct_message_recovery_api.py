import uuid
from datetime import timedelta

import jwt
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from types import SimpleNamespace
from unittest.mock import patch

from messenger_config.identity_client import (
    IdentityClientError,
    SavedContactForbiddenError,
)
from apps.e2ee_devices.models import Device, RecoveryBundle
from apps.rooms.models import Room, RoomMember

from ..models import (
    Message,
    MessageKeyEnvelope,
    MessageRecoveryEnvelope,
)


class DirectMessageRecoveryAPITests(APITestCase):
    sender_device_id = uuid.UUID(
        "11111111-1111-4111-8111-111111111111"
    )
    recipient_device_id = uuid.UUID(
        "22222222-2222-4222-8222-222222222222"
    )
    recipient_contact_id = 101

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

        self.url = reverse(
            "chat_messages:send-direct-message"
        )
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

    def create_recovery_bundle(
        self,
        *,
        user_id: str,
        version: int = 1,
    ):
        return RecoveryBundle.objects.create(
            user_id=user_id,
            recovery_public_key=(
                f"USER_{user_id}_RECOVERY_PUBLIC"
            ),
            encrypted_recovery_private_key=(
                f"USER_{user_id}_ENCRYPTED_PRIVATE"
            ),
            encryption_metadata={
                "algorithm": "xchacha20poly1305-ietf",
                "nonce": f"USER_{user_id}_NONCE",
                "unlock_method": "recovery_key",
            },
            recovery_version=version,
            is_active=True,
        )

    def valid_payload(self) -> dict:
        return {
            "recipient_contact_id": self.recipient_contact_id,
            "sender_device_id": str(
                self.sender_device_id
            ),
            "client_message_id": (
                "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
            ),
            "message_type": "text",
            "encrypted_payload": (
                "RECOVERY_AWARE_CIPHERTEXT"
            ),
            "encryption_metadata": {
                "algorithm": "xchacha20poly1305",
                "nonce": "MESSAGE_NONCE",
            },
            "encryption_version": 1,
            "envelopes": [
                {
                    "recipient_device_id": str(
                        self.sender_device_id
                    ),
                    "protocol": "device_sync",
                    "session_reference": (
                        "sender-sync-session"
                    ),
                    "wrapped_message_key": (
                        "SENDER_DEVICE_WRAPPED_KEY"
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
                        "RECIPIENT_DEVICE_WRAPPED_KEY"
                    ),
                    "key_wrap_metadata": {
                        "algorithm": "double-ratchet",
                        "message_number": 1,
                    },
                    "envelope_version": 1,
                },
            ],
            "recovery_envelopes": [
                {
                    "recovery_owner_user_id": "1",
                    "recovery_key_version": 1,
                    "wrapped_message_key": (
                        "SENDER_RECOVERY_WRAPPED_KEY"
                    ),
                    "key_wrap_metadata": {
                        "algorithm": "recovery-box-v1",
                        "nonce": "SENDER_RECOVERY_NONCE",
                    },
                    "envelope_version": 1,
                },
                {
                    "recovery_owner_user_id": "2",
                    "recovery_key_version": 1,
                    "wrapped_message_key": (
                        "RECIPIENT_RECOVERY_WRAPPED_KEY"
                    ),
                    "key_wrap_metadata": {
                        "algorithm": "recovery-box-v1",
                        "nonce": "RECIPIENT_RECOVERY_NONCE",
                    },
                    "envelope_version": 1,
                },
            ],
        }

    def assert_nothing_stored(self):
        self.assertEqual(Room.objects.count(), 0)
        self.assertEqual(RoomMember.objects.count(), 0)
        self.assertEqual(Message.objects.count(), 0)
        self.assertEqual(
            MessageKeyEnvelope.objects.count(),
            0,
        )
        self.assertEqual(
            MessageRecoveryEnvelope.objects.count(),
            0,
        )

    def test_both_recovery_envelopes_are_stored(self):
        self.create_recovery_bundle(user_id="1")
        self.create_recovery_bundle(user_id="2")
        self.authenticate_as("1")

        response = self.client.post(
            self.url,
            self.valid_payload(),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )
        self.assertEqual(
            MessageRecoveryEnvelope.objects.count(),
            2,
        )
        self.assertEqual(
            response.json()["data"][
                "recovery_envelope_count"
            ],
            2,
        )

    def test_missing_required_recovery_envelope_rolls_back(
        self,
    ):
        self.create_recovery_bundle(user_id="1")
        self.create_recovery_bundle(user_id="2")
        self.authenticate_as("1")
        payload = self.valid_payload()
        payload["recovery_envelopes"] = [
            payload["recovery_envelopes"][0]
        ]

        response = self.client.post(
            self.url,
            payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assert_nothing_stored()

    def test_wrong_recovery_key_version_rolls_back(self):
        self.create_recovery_bundle(
            user_id="1",
            version=2,
        )
        self.create_recovery_bundle(user_id="2")
        self.authenticate_as("1")
        payload = self.valid_payload()

        response = self.client.post(
            self.url,
            payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assert_nothing_stored()

    def test_duplicate_recovery_owner_is_rejected(self):
        self.create_recovery_bundle(user_id="1")
        self.create_recovery_bundle(user_id="2")
        self.authenticate_as("1")
        payload = self.valid_payload()
        payload["recovery_envelopes"].append(
            dict(payload["recovery_envelopes"][0])
        )

        response = self.client.post(
            self.url,
            payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assert_nothing_stored()

    def test_unexpected_recovery_owner_is_rejected(self):
        self.create_recovery_bundle(user_id="1")
        self.create_recovery_bundle(user_id="2")
        self.authenticate_as("1")
        payload = self.valid_payload()
        payload["recovery_envelopes"][1][
            "recovery_owner_user_id"
        ] = "999"

        response = self.client.post(
            self.url,
            payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assert_nothing_stored()

    def test_old_payload_still_works_without_recovery(
        self,
    ):
        self.authenticate_as("1")
        payload = self.valid_payload()
        payload.pop("recovery_envelopes")

        response = self.client.post(
            self.url,
            payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )
        self.assertEqual(
            MessageRecoveryEnvelope.objects.count(),
            0,
        )

    def test_only_active_recovery_owner_is_required(self):
        self.create_recovery_bundle(user_id="1")
        self.authenticate_as("1")
        payload = self.valid_payload()
        payload["recovery_envelopes"] = [
            payload["recovery_envelopes"][0]
        ]

        response = self.client.post(
            self.url,
            payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )
        self.assertEqual(
            MessageRecoveryEnvelope.objects.count(),
            1,
        )

    def test_exact_retry_is_idempotent(self):
        self.create_recovery_bundle(user_id="1")
        self.create_recovery_bundle(user_id="2")
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
        self.assertEqual(
            MessageRecoveryEnvelope.objects.count(),
            2,
        )

    def test_changed_recovery_retry_returns_conflict(self):
        self.create_recovery_bundle(user_id="1")
        self.create_recovery_bundle(user_id="2")
        self.authenticate_as("1")
        payload = self.valid_payload()

        first_response = self.client.post(
            self.url,
            payload,
            format="json",
        )
        self.assertEqual(
            first_response.status_code,
            status.HTTP_201_CREATED,
        )

        payload["recovery_envelopes"][0][
            "wrapped_message_key"
        ] = "CHANGED_RECOVERY_KEY"

        second_response = self.client.post(
            self.url,
            payload,
            format="json",
        )

        self.assertEqual(
            second_response.status_code,
            status.HTTP_409_CONFLICT,
        )
        self.assertEqual(Message.objects.count(), 1)
        self.assertEqual(
            MessageRecoveryEnvelope.objects.count(),
            2,
        )

def test_existing_room_send_by_room_id_stores_recovery_envelopes(self):
    self.authenticate_as("1")

    first_response = self.client.post(
        self.url,
        self.valid_payload(),
        format="json",
    )

    self.assertEqual(
        first_response.status_code,
        status.HTTP_201_CREATED,
    )

    room_id = first_response.json()["data"]["room_id"]

    second_payload = self.valid_payload(
        client_message_id=uuid.UUID(
            "99999999-9999-4999-8999-999999999999"
        ),
        encrypted_payload="SECOND_RECOVERY_CIPHERTEXT",
    )

    second_payload.pop("recipient_contact_id")
    second_payload["room_id"] = room_id
    second_payload["encryption_metadata"]["nonce"] = (
        "SECOND_RECOVERY_NONCE"
    )

    second_payload["envelopes"][0][
        "session_reference"
    ] = "second-sender-sync-session"
    second_payload["envelopes"][1][
        "session_reference"
    ] = "second-recipient-ratchet-session"

    second_response = self.client.post(
        self.url,
        second_payload,
        format="json",
    )

    self.assertEqual(
        second_response.status_code,
        status.HTTP_201_CREATED,
    )
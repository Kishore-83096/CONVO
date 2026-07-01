import uuid
from datetime import timedelta

import jwt
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.e2ee_devices.models import Device, RecoveryBundle
from apps.rooms.models import Room, RoomMember

from ..models import (
    Message,
    MessageKeyEnvelope,
    MessageRecoveryEnvelope,
)


class RecoveryHistoryAPITests(APITestCase):
    device_id = uuid.UUID(
        "11111111-1111-4111-8111-111111111111"
    )
    other_device_id = uuid.UUID(
        "22222222-2222-4222-8222-222222222222"
    )

    def setUp(self):
        self.device = Device.objects.create(
            id=self.device_id,
            user_id="1",
            device_name="Recovered browser",
            platform="web",
            registration_id=10001,
            identity_key_public="USER_1_IDENTITY_PUBLIC",
            signed_prekey_id=1,
            signed_prekey_public="USER_1_SIGNED_PREKEY",
            signed_prekey_signature="USER_1_SIGNATURE",
            key_algorithm="curve25519",
            key_bundle_version=1,
        )

        self.other_device = Device.objects.create(
            id=self.other_device_id,
            user_id="2",
            device_name="Other browser",
            platform="web",
            registration_id=20001,
            identity_key_public="USER_2_IDENTITY_PUBLIC",
            signed_prekey_id=1,
            signed_prekey_public="USER_2_SIGNED_PREKEY",
            signed_prekey_signature="USER_2_SIGNATURE",
            key_algorithm="curve25519",
            key_bundle_version=1,
        )

        self.recovery_bundle = RecoveryBundle.objects.create(
            user_id="1",
            recovery_public_key="USER_1_RECOVERY_PUBLIC",
            encrypted_recovery_private_key=(
                "USER_1_ENCRYPTED_RECOVERY_PRIVATE"
            ),
            encryption_metadata={
                "algorithm": "xchacha20poly1305-ietf",
                "nonce": "RECOVERY_BUNDLE_NONCE",
                "unlock_method": "recovery_key",
            },
            recovery_version=1,
            is_active=True,
        )

        self.room = Room.objects.create(
            room_type="direct",
            created_by_user_id="1",
            direct_pair_key=(
                "0123456789abcdef"
                "0123456789abcdef"
                "0123456789abcdef"
                "0123456789abcdef"
            ),
            is_active=True,
        )

        RoomMember.objects.create(
            room=self.room,
            user_id="1",
            role="member",
            added_by_user_id="1",
            is_active=True,
        )
        RoomMember.objects.create(
            room=self.room,
            user_id="2",
            role="member",
            added_by_user_id="1",
            is_active=True,
        )

        self.message = Message.objects.create(
            room=self.room,
            sender_user_id="2",
            sender_device_id=str(self.other_device_id),
            client_message_id=uuid.UUID(
                "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
            ),
            message_type="text",
            encrypted_payload="RECOVERY_CIPHERTEXT",
            encryption_metadata={
                "algorithm": "xchacha20poly1305-ietf",
                "nonce": "MESSAGE_NONCE",
            },
            encryption_version=1,
        )

        self.recovery_envelope = (
            MessageRecoveryEnvelope.objects.create(
                message=self.message,
                recovery_owner_user_id="1",
                recovery_key_version=1,
                wrapped_message_key=(
                    "RECOVERY_WRAPPED_MESSAGE_KEY"
                ),
                key_wrap_metadata={
                    "algorithm": "recovery-box-v1",
                    "nonce": "RECOVERY_ENVELOPE_NONCE",
                },
                envelope_version=1,
            )
        )

        self.history_url = reverse(
            "chat_messages:recovery-history"
        )
        self.rewrap_url = reverse(
            "chat_messages:recovery-rewrap"
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
            HTTP_AUTHORIZATION=f"Bearer {token}"
        )

    def valid_rewrap_payload(self) -> dict:
        return {
            "device_id": str(self.device_id),
            "envelopes": [
                {
                    "message_id": str(self.message.id),
                    "wrapped_message_key": (
                        "DEVICE_SYNC_WRAPPED_MESSAGE_KEY"
                    ),
                    "key_wrap_metadata": {
                        "algorithm": "device-sync-v1",
                        "nonce": "DEVICE_SYNC_NONCE",
                    },
                    "envelope_version": 1,
                }
            ],
        }

    def test_recovery_history_requires_authentication(self):
        response = self.client.get(
            self.history_url,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_owner_can_retrieve_recovery_history(self):
        self.authenticate_as("1")

        response = self.client.get(
            self.history_url,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        messages = response.json()["data"]["messages"]
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            messages[0]["encrypted_payload"],
            "RECOVERY_CIPHERTEXT",
        )
        self.assertEqual(
            messages[0]["recovery_envelope"][
                "wrapped_message_key"
            ],
            "RECOVERY_WRAPPED_MESSAGE_KEY",
        )

    def test_another_user_cannot_see_recovery_history(self):
        self.authenticate_as("2")

        response = self.client.get(
            self.history_url,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_inactive_recovery_bundle_blocks_history(self):
        self.recovery_bundle.is_active = False
        self.recovery_bundle.disabled_at = timezone.now()
        self.recovery_bundle.save(
            update_fields=[
                "is_active",
                "disabled_at",
                "updated_at",
            ]
        )
        self.authenticate_as("1")

        response = self.client.get(
            self.history_url,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_rewrap_creates_device_envelope(self):
        self.authenticate_as("1")

        response = self.client.post(
            self.rewrap_url,
            self.valid_rewrap_payload(),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        envelope = MessageKeyEnvelope.objects.get(
            message=self.message,
            recipient_device=self.device,
        )
        self.assertEqual(
            envelope.recipient_user_id,
            "1",
        )
        self.assertEqual(
            envelope.protocol,
            "device_sync",
        )

    def test_rewrap_rejects_another_users_device(self):
        self.authenticate_as("1")
        payload = self.valid_rewrap_payload()
        payload["device_id"] = str(
            self.other_device_id
        )

        response = self.client.post(
            self.rewrap_url,
            payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            MessageKeyEnvelope.objects.count(),
            0,
        )

    def test_rewrap_rejects_message_without_recovery_envelope(
        self,
    ):
        second_message = Message.objects.create(
            room=self.room,
            sender_user_id="2",
            sender_device_id=str(self.other_device_id),
            client_message_id=uuid.UUID(
                "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
            ),
            message_type="text",
            encrypted_payload="UNAUTHORIZED_CIPHERTEXT",
            encryption_metadata={
                "algorithm": "xchacha20poly1305-ietf",
                "nonce": "SECOND_NONCE",
            },
            encryption_version=1,
        )

        self.authenticate_as("1")
        payload = self.valid_rewrap_payload()
        payload["envelopes"][0]["message_id"] = str(
            second_message.id
        )

        response = self.client.post(
            self.rewrap_url,
            payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            MessageKeyEnvelope.objects.count(),
            0,
        )

    def test_exact_rewrap_retry_is_idempotent(self):
        self.authenticate_as("1")
        payload = self.valid_rewrap_payload()

        first_response = self.client.post(
            self.rewrap_url,
            payload,
            format="json",
        )
        second_response = self.client.post(
            self.rewrap_url,
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
        self.assertEqual(
            second_response.json()["data"][
                "existing_count"
            ],
            1,
        )
        self.assertEqual(
            MessageKeyEnvelope.objects.count(),
            1,
        )

    def test_different_rewrap_retry_returns_conflict(self):
        self.authenticate_as("1")
        payload = self.valid_rewrap_payload()

        first_response = self.client.post(
            self.rewrap_url,
            payload,
            format="json",
        )
        self.assertEqual(
            first_response.status_code,
            status.HTTP_201_CREATED,
        )

        payload["envelopes"][0][
            "wrapped_message_key"
        ] = "DIFFERENT_WRAPPED_KEY"

        second_response = self.client.post(
            self.rewrap_url,
            payload,
            format="json",
        )

        self.assertEqual(
            second_response.status_code,
            status.HTTP_409_CONFLICT,
        )
        self.assertEqual(
            MessageKeyEnvelope.objects.count(),
            1,
        )

    def test_duplicate_message_ids_are_rejected(self):
        self.authenticate_as("1")
        payload = self.valid_rewrap_payload()
        payload["envelopes"].append(
            dict(payload["envelopes"][0])
        )

        response = self.client.post(
            self.rewrap_url,
            payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            MessageKeyEnvelope.objects.count(),
            0,
        )

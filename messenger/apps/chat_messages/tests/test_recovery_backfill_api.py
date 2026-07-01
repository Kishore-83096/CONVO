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


class RecoveryBackfillAPITests(APITestCase):
    user_device_id = uuid.UUID(
        "11111111-1111-4111-8111-111111111111"
    )
    other_device_id = uuid.UUID(
        "22222222-2222-4222-8222-222222222222"
    )

    def setUp(self):
        self.user_device = Device.objects.create(
            id=self.user_device_id,
            user_id="1",
            device_name="User browser",
            platform="web",
            registration_id=10001,
            identity_key_public="USER_1_IDENTITY",
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
            identity_key_public="USER_2_IDENTITY",
            signed_prekey_id=1,
            signed_prekey_public="USER_2_SIGNED_PREKEY",
            signed_prekey_signature="USER_2_SIGNATURE",
            key_algorithm="curve25519",
            key_bundle_version=1,
        )

        self.bundle = RecoveryBundle.objects.create(
            user_id="1",
            recovery_public_key="USER_1_RECOVERY_PUBLIC",
            encrypted_recovery_private_key=(
                "USER_1_ENCRYPTED_PRIVATE"
            ),
            encryption_metadata={
                "algorithm": "xchacha20poly1305-ietf",
                "nonce": "USER_1_BUNDLE_NONCE",
                "unlock_method": "recovery_key",
            },
            recovery_version=3,
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

        self.first_message = self.create_message(
            client_message_id=uuid.UUID(
                "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
            ),
            encrypted_payload="FIRST_CIPHERTEXT",
        )
        self.second_message = self.create_message(
            client_message_id=uuid.UUID(
                "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
            ),
            encrypted_payload="SECOND_CIPHERTEXT",
        )

        self.create_device_envelope(
            message=self.first_message,
        )
        self.create_device_envelope(
            message=self.second_message,
        )

        self.candidates_url = reverse(
            "chat_messages:recovery-backfill-candidates"
        )
        self.backfill_url = reverse(
            "chat_messages:recovery-backfill"
        )

    def create_message(
        self,
        *,
        client_message_id,
        encrypted_payload,
        room=None,
    ):
        return Message.objects.create(
            room=room or self.room,
            sender_user_id="2",
            sender_device_id=str(
                self.other_device_id
            ),
            client_message_id=client_message_id,
            message_type="text",
            encrypted_payload=encrypted_payload,
            encryption_metadata={
                "algorithm": "xchacha20poly1305",
                "nonce": str(client_message_id),
            },
            encryption_version=1,
        )

    def create_device_envelope(
        self,
        *,
        message,
        device=None,
        owner_user_id="1",
    ):
        target_device = device or self.user_device

        return MessageKeyEnvelope.objects.create(
            message=message,
            recipient_user_id=owner_user_id,
            recipient_device=target_device,
            protocol="device_sync",
            session_reference=(
                f"device:{target_device.id}:{message.id}"
            ),
            wrapped_message_key=(
                f"DEVICE_WRAPPED_{message.id}"
            ),
            key_wrap_metadata={
                "algorithm": "device-sync-v1",
                "nonce": f"DEVICE_NONCE_{message.id}",
            },
            envelope_version=1,
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

    def valid_backfill_payload(self) -> dict:
        return {
            "device_id": str(self.user_device_id),
            "recovery_key_version": 3,
            "envelopes": [
                {
                    "message_id": str(
                        self.first_message.id
                    ),
                    "wrapped_message_key": (
                        "RECOVERY_WRAPPED_FIRST"
                    ),
                    "key_wrap_metadata": {
                        "algorithm": "recovery-box-v1",
                        "nonce": "RECOVERY_NONCE_FIRST",
                    },
                    "envelope_version": 1,
                }
            ],
        }

    def test_candidates_require_authentication(self):
        response = self.client.get(
            self.candidates_url,
            {
                "device_id": str(self.user_device_id),
            },
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_candidates_require_device_id(self):
        self.authenticate_as("1")

        response = self.client.get(
            self.candidates_url,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_candidates_return_messages_missing_recovery(
        self,
    ):
        self.authenticate_as("1")

        response = self.client.get(
            self.candidates_url,
            {
                "device_id": str(self.user_device_id),
            },
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        messages = response.json()["data"]["messages"]
        self.assertEqual(len(messages), 2)
        self.assertIsNotNone(
            messages[0]["device_envelope"]
        )

    def test_existing_recovery_envelope_is_excluded(
        self,
    ):
        MessageRecoveryEnvelope.objects.create(
            message=self.first_message,
            recovery_owner_user_id="1",
            recovery_key_version=3,
            wrapped_message_key="ALREADY_RECOVERABLE",
            key_wrap_metadata={
                "algorithm": "recovery-box-v1",
                "nonce": "EXISTING_NONCE",
            },
            envelope_version=1,
        )

        self.authenticate_as("1")

        response = self.client.get(
            self.candidates_url,
            {
                "device_id": str(self.user_device_id),
            },
        )

        message_ids = {
            item["id"]
            for item in response.json()["data"][
                "messages"
            ]
        }

        self.assertNotIn(
            str(self.first_message.id),
            message_ids,
        )
        self.assertIn(
            str(self.second_message.id),
            message_ids,
        )

    def test_another_users_device_is_rejected(self):
        self.authenticate_as("1")

        response = self.client.get(
            self.candidates_url,
            {
                "device_id": str(self.other_device_id),
            },
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_inactive_recovery_blocks_candidates(self):
        self.bundle.is_active = False
        self.bundle.disabled_at = timezone.now()
        self.bundle.save(
            update_fields=[
                "is_active",
                "disabled_at",
                "updated_at",
            ]
        )

        self.authenticate_as("1")

        response = self.client.get(
            self.candidates_url,
            {
                "device_id": str(self.user_device_id),
            },
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_backfill_creates_recovery_envelope(self):
        self.authenticate_as("1")

        response = self.client.post(
            self.backfill_url,
            self.valid_backfill_payload(),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )
        envelope = MessageRecoveryEnvelope.objects.get(
            message=self.first_message,
            recovery_owner_user_id="1",
        )
        self.assertEqual(
            envelope.recovery_key_version,
            3,
        )

    def test_exact_backfill_retry_is_idempotent(self):
        self.authenticate_as("1")
        payload = self.valid_backfill_payload()

        first_response = self.client.post(
            self.backfill_url,
            payload,
            format="json",
        )
        second_response = self.client.post(
            self.backfill_url,
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
            MessageRecoveryEnvelope.objects.count(),
            1,
        )

    def test_changed_backfill_retry_returns_conflict(self):
        self.authenticate_as("1")
        payload = self.valid_backfill_payload()

        first_response = self.client.post(
            self.backfill_url,
            payload,
            format="json",
        )
        self.assertEqual(
            first_response.status_code,
            status.HTTP_201_CREATED,
        )

        payload["envelopes"][0][
            "wrapped_message_key"
        ] = "CHANGED_RECOVERY_WRAPPED_KEY"

        second_response = self.client.post(
            self.backfill_url,
            payload,
            format="json",
        )

        self.assertEqual(
            second_response.status_code,
            status.HTTP_409_CONFLICT,
        )

    def test_stale_recovery_version_returns_conflict(self):
        self.authenticate_as("1")
        payload = self.valid_backfill_payload()
        payload["recovery_key_version"] = 2

        response = self.client.post(
            self.backfill_url,
            payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_409_CONFLICT,
        )
        self.assertEqual(
            MessageRecoveryEnvelope.objects.count(),
            0,
        )

    def test_duplicate_message_ids_are_rejected(self):
        self.authenticate_as("1")
        payload = self.valid_backfill_payload()
        payload["envelopes"].append(
            dict(payload["envelopes"][0])
        )

        response = self.client.post(
            self.backfill_url,
            payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_message_without_device_envelope_is_rejected(
        self,
    ):
        hidden_message = self.create_message(
            client_message_id=uuid.UUID(
                "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
            ),
            encrypted_payload="HIDDEN_CIPHERTEXT",
        )

        self.authenticate_as("1")
        payload = self.valid_backfill_payload()
        payload["envelopes"][0]["message_id"] = str(
            hidden_message.id
        )

        response = self.client.post(
            self.backfill_url,
            payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(
            MessageRecoveryEnvelope.objects.count(),
            0,
        )

    def test_batch_failure_rolls_back_all_envelopes(self):
        hidden_message = self.create_message(
            client_message_id=uuid.UUID(
                "dddddddd-dddd-4ddd-8ddd-dddddddddddd"
            ),
            encrypted_payload="HIDDEN_BATCH_CIPHERTEXT",
        )

        self.authenticate_as("1")
        payload = self.valid_backfill_payload()
        payload["envelopes"].append(
            {
                "message_id": str(hidden_message.id),
                "wrapped_message_key": (
                    "HIDDEN_RECOVERY_WRAPPED_KEY"
                ),
                "key_wrap_metadata": {
                    "algorithm": "recovery-box-v1",
                    "nonce": "HIDDEN_RECOVERY_NONCE",
                },
                "envelope_version": 1,
            }
        )

        response = self.client.post(
            self.backfill_url,
            payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(
            MessageRecoveryEnvelope.objects.count(),
            0,
        )

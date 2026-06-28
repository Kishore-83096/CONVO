import uuid
from datetime import timedelta

import jwt
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.chat_messages.models import (
    Message,
    MessageRecoveryEnvelope,
)
from apps.e2ee_devices.models import Device, RecoveryBundle
from apps.rooms.models import Room, RoomMember


class RecoveryRotationAPITests(APITestCase):
    sender_device_id = uuid.UUID(
        "11111111-1111-4111-8111-111111111111"
    )
    recipient_device_id = uuid.UUID(
        "22222222-2222-4222-8222-222222222222"
    )

    def setUp(self):
        self.rotate_url = reverse(
            "e2ee_devices:recovery-rotate"
        )
        self.disable_url = reverse(
            "e2ee_devices:recovery-disable"
        )

        self.sender_device = Device.objects.create(
            id=self.sender_device_id,
            user_id="1",
            device_name="Sender browser",
            platform="web",
            registration_id=10001,
            identity_key_public="USER_1_IDENTITY",
            signed_prekey_id=1,
            signed_prekey_public="USER_1_SIGNED_PREKEY",
            signed_prekey_signature="USER_1_SIGNATURE",
            key_algorithm="curve25519",
            key_bundle_version=1,
        )

        self.recipient_device = Device.objects.create(
            id=self.recipient_device_id,
            user_id="2",
            device_name="Recipient browser",
            platform="web",
            registration_id=20001,
            identity_key_public="USER_2_IDENTITY",
            signed_prekey_id=1,
            signed_prekey_public="USER_2_SIGNED_PREKEY",
            signed_prekey_signature="USER_2_SIGNATURE",
            key_algorithm="curve25519",
            key_bundle_version=1,
        )

        self.user_bundle = RecoveryBundle.objects.create(
            user_id="1",
            recovery_public_key="OLD_RECOVERY_PUBLIC",
            encrypted_recovery_private_key=(
                "OLD_ENCRYPTED_PRIVATE"
            ),
            encryption_metadata={
                "algorithm": "xchacha20poly1305-ietf",
                "nonce": "OLD_BUNDLE_NONCE",
                "unlock_method": "recovery_key",
            },
            recovery_version=1,
            is_active=True,
        )

        self.other_bundle = RecoveryBundle.objects.create(
            user_id="2",
            recovery_public_key=(
                "OTHER_RECOVERY_PUBLIC"
            ),
            encrypted_recovery_private_key=(
                "OTHER_ENCRYPTED_PRIVATE"
            ),
            encryption_metadata={
                "algorithm": "xchacha20poly1305-ietf",
                "nonce": "OTHER_BUNDLE_NONCE",
                "unlock_method": "recovery_key",
            },
            recovery_version=4,
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

        self.first_envelope = (
            MessageRecoveryEnvelope.objects.create(
                message=self.first_message,
                recovery_owner_user_id="1",
                recovery_key_version=1,
                wrapped_message_key="OLD_WRAPPED_FIRST",
                key_wrap_metadata={
                    "algorithm": "recovery-box-v1",
                    "nonce": "OLD_FIRST_NONCE",
                },
                envelope_version=1,
            )
        )
        self.second_envelope = (
            MessageRecoveryEnvelope.objects.create(
                message=self.second_message,
                recovery_owner_user_id="1",
                recovery_key_version=1,
                wrapped_message_key="OLD_WRAPPED_SECOND",
                key_wrap_metadata={
                    "algorithm": "recovery-box-v1",
                    "nonce": "OLD_SECOND_NONCE",
                },
                envelope_version=1,
            )
        )

        self.other_envelope = (
            MessageRecoveryEnvelope.objects.create(
                message=self.first_message,
                recovery_owner_user_id="2",
                recovery_key_version=4,
                wrapped_message_key="OTHER_WRAPPED_FIRST",
                key_wrap_metadata={
                    "algorithm": "recovery-box-v1",
                    "nonce": "OTHER_FIRST_NONCE",
                },
                envelope_version=1,
            )
        )

    def create_message(
        self,
        *,
        client_message_id,
        encrypted_payload,
    ):
        return Message.objects.create(
            room=self.room,
            sender_user_id="1",
            sender_device_id=str(
                self.sender_device_id
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

    def valid_rotate_payload(self) -> dict:
        return {
            "current_recovery_version": 1,
            "recovery_public_key": (
                "NEW_RECOVERY_PUBLIC"
            ),
            "encrypted_recovery_private_key": (
                "NEW_ENCRYPTED_PRIVATE"
            ),
            "encryption_metadata": {
                "algorithm": "xchacha20poly1305-ietf",
                "nonce": "NEW_BUNDLE_NONCE",
                "unlock_method": (
                    "recovery_key_and_webauthn_prf"
                ),
                "kdf": "hkdf-sha256",
            },
            "recovery_envelopes": [
                {
                    "message_id": str(
                        self.first_message.id
                    ),
                    "wrapped_message_key": (
                        "NEW_WRAPPED_FIRST"
                    ),
                    "key_wrap_metadata": {
                        "algorithm": "recovery-box-v1",
                        "nonce": "NEW_FIRST_NONCE",
                    },
                    "envelope_version": 1,
                },
                {
                    "message_id": str(
                        self.second_message.id
                    ),
                    "wrapped_message_key": (
                        "NEW_WRAPPED_SECOND"
                    ),
                    "key_wrap_metadata": {
                        "algorithm": "recovery-box-v1",
                        "nonce": "NEW_SECOND_NONCE",
                    },
                    "envelope_version": 1,
                },
            ],
        }

    def test_rotation_requires_authentication(self):
        response = self.client.post(
            self.rotate_url,
            self.valid_rotate_payload(),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_rotation_updates_bundle_and_all_envelopes(
        self,
    ):
        self.authenticate_as("1")

        response = self.client.post(
            self.rotate_url,
            self.valid_rotate_payload(),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.user_bundle.refresh_from_db()
        self.assertEqual(
            self.user_bundle.recovery_version,
            2,
        )
        self.assertEqual(
            self.user_bundle.recovery_public_key,
            "NEW_RECOVERY_PUBLIC",
        )

        self.first_envelope.refresh_from_db()
        self.second_envelope.refresh_from_db()

        self.assertEqual(
            self.first_envelope.recovery_key_version,
            2,
        )
        self.assertEqual(
            self.first_envelope.wrapped_message_key,
            "NEW_WRAPPED_FIRST",
        )
        self.assertEqual(
            self.second_envelope.wrapped_message_key,
            "NEW_WRAPPED_SECOND",
        )

    def test_missing_envelope_rolls_back_rotation(self):
        self.authenticate_as("1")
        payload = self.valid_rotate_payload()
        payload["recovery_envelopes"].pop()

        response = self.client.post(
            self.rotate_url,
            payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.user_bundle.refresh_from_db()
        self.first_envelope.refresh_from_db()

        self.assertEqual(
            self.user_bundle.recovery_version,
            1,
        )
        self.assertEqual(
            self.first_envelope.wrapped_message_key,
            "OLD_WRAPPED_FIRST",
        )

    def test_unexpected_message_rolls_back_rotation(self):
        unauthorized_message = self.create_message(
            client_message_id=uuid.UUID(
                "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
            ),
            encrypted_payload="THIRD_CIPHERTEXT",
        )

        self.authenticate_as("1")
        payload = self.valid_rotate_payload()
        payload["recovery_envelopes"].append(
            {
                "message_id": str(
                    unauthorized_message.id
                ),
                "wrapped_message_key": (
                    "UNEXPECTED_WRAPPED_KEY"
                ),
                "key_wrap_metadata": {
                    "algorithm": "recovery-box-v1",
                    "nonce": "UNEXPECTED_NONCE",
                },
                "envelope_version": 1,
            }
        )

        response = self.client.post(
            self.rotate_url,
            payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.user_bundle.refresh_from_db()
        self.assertEqual(
            self.user_bundle.recovery_version,
            1,
        )

    def test_stale_version_returns_conflict(self):
        self.authenticate_as("1")
        payload = self.valid_rotate_payload()
        payload["current_recovery_version"] = 9

        response = self.client.post(
            self.rotate_url,
            payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_409_CONFLICT,
        )

    def test_same_public_key_is_rejected(self):
        self.authenticate_as("1")
        payload = self.valid_rotate_payload()
        payload["recovery_public_key"] = (
            "OLD_RECOVERY_PUBLIC"
        )

        response = self.client.post(
            self.rotate_url,
            payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_exact_rotation_retry_is_idempotent(self):
        self.authenticate_as("1")
        payload = self.valid_rotate_payload()

        first_response = self.client.post(
            self.rotate_url,
            payload,
            format="json",
        )
        second_response = self.client.post(
            self.rotate_url,
            payload,
            format="json",
        )

        self.assertEqual(
            first_response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            second_response.status_code,
            status.HTTP_200_OK,
        )
        self.assertFalse(
            second_response.json()["data"][
                "rotation_applied"
            ]
        )

    def test_changed_rotation_retry_returns_conflict(self):
        self.authenticate_as("1")
        payload = self.valid_rotate_payload()

        first_response = self.client.post(
            self.rotate_url,
            payload,
            format="json",
        )
        self.assertEqual(
            first_response.status_code,
            status.HTTP_200_OK,
        )

        payload["recovery_envelopes"][0][
            "wrapped_message_key"
        ] = "CHANGED_WRAPPED_KEY"

        second_response = self.client.post(
            self.rotate_url,
            payload,
            format="json",
        )

        self.assertEqual(
            second_response.status_code,
            status.HTTP_409_CONFLICT,
        )

    def test_rotation_without_history_is_supported(self):
        MessageRecoveryEnvelope.objects.filter(
            recovery_owner_user_id="1",
        ).delete()

        self.authenticate_as("1")
        payload = self.valid_rotate_payload()
        payload["recovery_envelopes"] = []

        response = self.client.post(
            self.rotate_url,
            payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            response.json()["data"][
                "rotated_envelope_count"
            ],
            0,
        )

    def test_disable_requires_authentication(self):
        response = self.client.delete(
            self.disable_url,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_disable_deletes_bundle_and_user_envelopes(
        self,
    ):
        self.authenticate_as("1")

        response = self.client.delete(
            self.disable_url,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertFalse(
            RecoveryBundle.objects.filter(
                user_id="1"
            ).exists()
        )
        self.assertFalse(
            MessageRecoveryEnvelope.objects.filter(
                recovery_owner_user_id="1"
            ).exists()
        )

    def test_disable_preserves_other_users_recovery_data(
        self,
    ):
        self.authenticate_as("1")

        response = self.client.delete(
            self.disable_url,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertTrue(
            RecoveryBundle.objects.filter(
                user_id="2"
            ).exists()
        )
        self.assertTrue(
            MessageRecoveryEnvelope.objects.filter(
                recovery_owner_user_id="2"
            ).exists()
        )

    def test_disable_is_idempotent(self):
        self.authenticate_as("1")

        first_response = self.client.delete(
            self.disable_url,
        )
        second_response = self.client.delete(
            self.disable_url,
        )

        self.assertEqual(
            first_response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            second_response.status_code,
            status.HTTP_200_OK,
        )
        self.assertFalse(
            second_response.json()["data"][
                "bundle_deleted"
            ]
        )

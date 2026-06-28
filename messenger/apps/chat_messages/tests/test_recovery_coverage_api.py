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


class RecoveryCoverageAPITests(APITestCase):
    first_device_id = uuid.UUID(
        "11111111-1111-4111-8111-111111111111"
    )
    second_device_id = uuid.UUID(
        "22222222-2222-4222-8222-222222222222"
    )
    other_device_id = uuid.UUID(
        "33333333-3333-4333-8333-333333333333"
    )

    def setUp(self):
        self.first_device = Device.objects.create(
            id=self.first_device_id,
            user_id="1",
            device_name="User browser",
            platform="web",
            registration_id=10001,
            identity_key_public="USER_1_BROWSER_IDENTITY",
            signed_prekey_id=1,
            signed_prekey_public="USER_1_BROWSER_PREKEY",
            signed_prekey_signature="USER_1_BROWSER_SIGNATURE",
            key_algorithm="curve25519",
            key_bundle_version=1,
        )

        self.second_device = Device.objects.create(
            id=self.second_device_id,
            user_id="1",
            device_name="User phone",
            platform="android",
            registration_id=10002,
            identity_key_public="USER_1_PHONE_IDENTITY",
            signed_prekey_id=2,
            signed_prekey_public="USER_1_PHONE_PREKEY",
            signed_prekey_signature="USER_1_PHONE_SIGNATURE",
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
            signed_prekey_public="USER_2_PREKEY",
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

        self.user_membership = (
            RoomMember.objects.create(
                room=self.room,
                user_id="1",
                role="member",
                added_by_user_id="1",
                is_active=True,
            )
        )

        RoomMember.objects.create(
            room=self.room,
            user_id="2",
            role="member",
            added_by_user_id="1",
            is_active=True,
        )

        self.url = reverse(
            "chat_messages:recovery-coverage"
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

    def create_message(
        self,
        *,
        client_message_id,
        device=None,
    ):
        message = Message.objects.create(
            room=self.room,
            sender_user_id="2",
            sender_device_id=str(
                self.other_device_id
            ),
            client_message_id=client_message_id,
            message_type="text",
            encrypted_payload=(
                f"CIPHERTEXT_{client_message_id}"
            ),
            encryption_metadata={
                "algorithm": "xchacha20poly1305",
                "nonce": str(client_message_id),
            },
            encryption_version=1,
        )

        target_device = device or self.first_device

        MessageKeyEnvelope.objects.create(
            message=message,
            recipient_user_id="1",
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
            },
            envelope_version=1,
        )

        return message

    def add_recovery_envelope(
        self,
        *,
        message,
        version=3,
        owner_user_id="1",
    ):
        return MessageRecoveryEnvelope.objects.create(
            message=message,
            recovery_owner_user_id=owner_user_id,
            recovery_key_version=version,
            wrapped_message_key=(
                f"RECOVERY_WRAPPED_{message.id}"
            ),
            key_wrap_metadata={
                "algorithm": "recovery-box-v1",
                "nonce": f"RECOVERY_NONCE_{message.id}",
            },
            envelope_version=1,
        )

    def test_authentication_is_required(self):
        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_active_recovery_is_required(self):
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
        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_empty_history_is_complete(self):
        self.authenticate_as("1")
        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        data = response.json()["data"]
        self.assertEqual(
            data["total_eligible_messages"],
            0,
        )
        self.assertEqual(
            data["coverage_percent"],
            100.0,
        )
        self.assertTrue(data["is_complete"])

    def test_current_version_envelope_is_covered(self):
        message = self.create_message(
            client_message_id=uuid.UUID(
                "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
            )
        )
        self.add_recovery_envelope(
            message=message,
        )

        self.authenticate_as("1")
        response = self.client.get(self.url)

        data = response.json()["data"]
        self.assertEqual(
            data["total_eligible_messages"],
            1,
        )
        self.assertEqual(
            data[
                "current_version_covered_messages"
            ],
            1,
        )
        self.assertTrue(data["is_complete"])

    def test_missing_envelope_is_reported(self):
        self.create_message(
            client_message_id=uuid.UUID(
                "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
            )
        )

        self.authenticate_as("1")
        response = self.client.get(self.url)

        data = response.json()["data"]
        self.assertEqual(
            data["missing_recovery_envelopes"],
            1,
        )
        self.assertEqual(
            data["coverage_percent"],
            0.0,
        )
        self.assertFalse(data["is_complete"])

    def test_stale_envelope_is_reported(self):
        message = self.create_message(
            client_message_id=uuid.UUID(
                "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
            )
        )
        self.add_recovery_envelope(
            message=message,
            version=2,
        )

        self.authenticate_as("1")
        response = self.client.get(self.url)

        data = response.json()["data"]
        self.assertEqual(
            data["stale_recovery_envelopes"],
            1,
        )
        self.assertEqual(
            data["missing_recovery_envelopes"],
            0,
        )
        self.assertFalse(data["is_complete"])

    def test_mixed_coverage_percentage(self):
        first = self.create_message(
            client_message_id=uuid.UUID(
                "dddddddd-dddd-4ddd-8ddd-dddddddddddd"
            )
        )
        self.create_message(
            client_message_id=uuid.UUID(
                "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee"
            )
        )
        self.add_recovery_envelope(
            message=first,
        )

        self.authenticate_as("1")
        response = self.client.get(self.url)

        data = response.json()["data"]
        self.assertEqual(
            data["total_eligible_messages"],
            2,
        )
        self.assertEqual(
            data["coverage_percent"],
            50.0,
        )

    def test_message_without_active_device_envelope_excluded(
        self,
    ):
        inactive_device = self.second_device
        inactive_device.is_active = False
        inactive_device.save(
            update_fields=[
                "is_active",
                "updated_at",
            ]
        )

        self.create_message(
            client_message_id=uuid.UUID(
                "ffffffff-ffff-4fff-8fff-ffffffffffff"
            ),
            device=inactive_device,
        )

        self.authenticate_as("1")
        response = self.client.get(self.url)

        self.assertEqual(
            response.json()["data"][
                "total_eligible_messages"
            ],
            0,
        )

    def test_inactive_room_membership_excluded(self):
        self.create_message(
            client_message_id=uuid.UUID(
                "12121212-1212-4212-8212-121212121212"
            )
        )

        self.user_membership.is_active = False
        self.user_membership.left_at = timezone.now()
        self.user_membership.save(
            update_fields=[
                "is_active",
                "left_at",
                "updated_at",
            ]
        )

        self.authenticate_as("1")
        response = self.client.get(self.url)

        self.assertEqual(
            response.json()["data"][
                "total_eligible_messages"
            ],
            0,
        )

    def test_other_users_recovery_envelope_does_not_cover(
        self,
    ):
        message = self.create_message(
            client_message_id=uuid.UUID(
                "13131313-1313-4313-8313-131313131313"
            )
        )
        self.add_recovery_envelope(
            message=message,
            version=3,
            owner_user_id="2",
        )

        self.authenticate_as("1")
        response = self.client.get(self.url)

        data = response.json()["data"]
        self.assertEqual(
            data["missing_recovery_envelopes"],
            1,
        )

    def test_device_candidate_counts_are_reported(self):
        self.create_message(
            client_message_id=uuid.UUID(
                "14141414-1414-4414-8414-141414141414"
            ),
            device=self.first_device,
        )
        second_message = self.create_message(
            client_message_id=uuid.UUID(
                "15151515-1515-4515-8515-151515151515"
            ),
            device=self.second_device,
        )
        self.add_recovery_envelope(
            message=second_message,
        )

        self.authenticate_as("1")
        response = self.client.get(self.url)

        devices = {
            item["device_id"]: item[
                "backfill_candidate_count"
            ]
            for item in response.json()["data"][
                "active_devices"
            ]
        }

        self.assertEqual(
            devices[str(self.first_device_id)],
            1,
        )
        self.assertEqual(
            devices[str(self.second_device_id)],
            0,
        )

    def test_recovery_version_is_returned(self):
        self.authenticate_as("1")
        response = self.client.get(self.url)

        self.assertEqual(
            response.json()["data"][
                "recovery_version"
            ],
            3,
        )

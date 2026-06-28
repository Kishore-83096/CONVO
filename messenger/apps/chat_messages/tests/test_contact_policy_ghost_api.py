import uuid
from datetime import timedelta

import jwt
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from apps.chat_messages.services import build_direct_pair_key
from apps.chat_messages.models import (
    ContactDeliveryPolicy,
    DirectMessageReceiptDecision,
    Message,
    MessageKeyEnvelope,
    MessageReceipt,
)
from apps.e2ee_devices.models import Device
from apps.rooms.models import Room, RoomMember


class ContactPolicyGhostAPITests(APITestCase):
    sender_device_id = uuid.UUID(
        "11111111-1111-4111-8111-111111111111"
    )
    recipient_device_id = uuid.UUID(
        "22222222-2222-4222-8222-222222222222"
    )

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
        self.direct_room = Room.objects.create(
            room_type=Room.RoomType.DIRECT,
            direct_pair_key=build_direct_pair_key("1", "2"),
            created_by_user_id="1",
        )

        RoomMember.objects.create(
            room=self.direct_room,
            user_id="1",
            role=RoomMember.Role.MEMBER,
            added_by_user_id="1",
        )

        RoomMember.objects.create(
            room=self.direct_room,
            user_id="2",
            role=RoomMember.Role.MEMBER,
            added_by_user_id="1",
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

    def valid_payload(self) -> dict:
        return {
            "room_id": str(self.direct_room.id),
            "recipient_user_id": "2",
            "sender_device_id": str(self.sender_device_id),
            "client_message_id": str(uuid.uuid4()),
            "message_type": "text",
            "encrypted_payload": "GHOST_TEST_CIPHERTEXT",
            "encryption_metadata": {
                "algorithm": "xchacha20poly1305",
                "nonce": "GHOST_TEST_NONCE",
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

    def test_policy_sync_accepts_ghost_fields(self):
        response = self.client.post(
            "/api/v1/internal/contact-policies/",
            {
                "owner_user_id": "2",
                "target_user_id": "1",
                "is_blocked": False,
                "ghost_until": (
                    timezone.now() + timedelta(hours=24)
                ).isoformat(),
                "ghost_permanent": False,
                "ghost_duration_option": "24h",
                "policy_version": 2,
            },
            format="json",
            HTTP_X_MYNA_INTERNAL_SECRET=(
                settings.CONTACT_POLICY_SYNC_SECRET
            ),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        policy = ContactDeliveryPolicy.objects.get(
            owner_user_id="2",
            target_user_id="1",
        )

        self.assertFalse(policy.is_blocked)
        self.assertIsNotNone(policy.ghost_until)
        self.assertFalse(policy.ghost_permanent)
        self.assertEqual(policy.ghost_duration_option, "24h")
        self.assertEqual(policy.policy_version, 2)

    def test_ghosted_recipient_receives_message_but_delivered_receipt_is_suppressed(self):
        ContactDeliveryPolicy.objects.create(
            owner_user_id="2",
            target_user_id="1",
            is_blocked=False,
            ghost_until=timezone.now() + timedelta(hours=24),
            ghost_permanent=False,
            ghost_duration_option="24h",
            policy_version=2,
        )

        self.authenticate_as("1")

        send_response = self.client.post(
            reverse("chat_messages:send-direct-message"),
            self.valid_payload(),
            format="json",
        )

        self.assertEqual(
            send_response.status_code,
            status.HTTP_201_CREATED,
            send_response.json(),
        )

        message = Message.objects.get()
        self.assertEqual(MessageKeyEnvelope.objects.count(), 2)

        decision = DirectMessageReceiptDecision.objects.get(
            message=message,
        )

        self.assertEqual(decision.policy_reason, "ghost")
        self.assertTrue(decision.suppress_delivered_receipt)
        self.assertTrue(decision.suppress_read_receipt)

        self.authenticate_as("2")

        delivered_response = self.client.post(
            reverse("chat_messages:message-receipts-delivered"),
            {
                "device_id": str(self.recipient_device_id),
                "message_ids": [str(message.id)],
            },
            format="json",
        )

        self.assertEqual(
            delivered_response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            delivered_response.json()["data"]["updated_count"],
            0,
        )
        self.assertEqual(MessageReceipt.objects.count(), 0)

    def test_expired_ghost_does_not_suppress_future_message(self):
        ContactDeliveryPolicy.objects.create(
            owner_user_id="2",
            target_user_id="1",
            is_blocked=False,
            ghost_until=timezone.now() - timedelta(minutes=1),
            ghost_permanent=False,
            ghost_duration_option="1h",
            policy_version=2,
        )

        self.authenticate_as("1")

        send_response = self.client.post(
            reverse("chat_messages:send-direct-message"),
            self.valid_payload(),
            format="json",
        )

        self.assertEqual(
            send_response.status_code,
            status.HTTP_201_CREATED,
            send_response.json(),
        )

        message = Message.objects.get()
        decision = DirectMessageReceiptDecision.objects.get(
            message=message,
        )

        self.assertEqual(decision.policy_reason, "normal")
        self.assertFalse(decision.suppress_delivered_receipt)

        self.authenticate_as("2")

        delivered_response = self.client.post(
            reverse("chat_messages:message-receipts-delivered"),
            {
                "device_id": str(self.recipient_device_id),
                "message_ids": [str(message.id)],
            },
            format="json",
        )

        self.assertEqual(
            delivered_response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            delivered_response.json()["data"]["updated_count"],
            1,
        )
        self.assertEqual(MessageReceipt.objects.count(), 1)
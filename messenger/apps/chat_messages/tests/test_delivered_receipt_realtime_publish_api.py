import uuid
from datetime import timedelta
from unittest.mock import patch

import jwt
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.chat_messages.models import (
    DirectMessageReceiptDecision,
    Message,
    MessageReceipt,
)
from apps.e2ee_devices.models import Device
from apps.rooms.models import Room, RoomMember


class DeliveredReceiptRealtimePublishAPITests(APITestCase):
    sender_device_id = uuid.UUID(
        "11111111-1111-4111-8111-111111111111"
    )
    recipient_device_id = uuid.UUID(
        "22222222-2222-4222-8222-222222222222"
    )

    def setUp(self):
        self.url = reverse("chat_messages:message-receipts-delivered")

        self.sender_device = Device.objects.create(
            id=self.sender_device_id,
            user_id="1",
            device_name="Sender browser",
            platform=Device.Platform.WEB,
            registration_id=10001,
            identity_key_public="SENDER_IDENTITY",
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
            identity_key_public="RECIPIENT_IDENTITY",
            signed_prekey_id=1,
            signed_prekey_public="RECIPIENT_SIGNED_PREKEY",
            signed_prekey_signature="RECIPIENT_SIGNATURE",
            key_algorithm="curve25519",
            key_bundle_version=1,
            is_active=True,
        )

        self.room = Room.objects.create(
            room_type=Room.RoomType.DIRECT,
            name="",
            created_by_user_id="1",
            direct_pair_key=Room.build_direct_pair_key(
                "1",
                "2",
            ),
            is_active=True,
        )

        RoomMember.objects.create(
            room=self.room,
            user_id="1",
            role=RoomMember.Role.MEMBER,
            added_by_user_id="1",
            is_active=True,
        )

        RoomMember.objects.create(
            room=self.room,
            user_id="2",
            role=RoomMember.Role.MEMBER,
            added_by_user_id="1",
            is_active=True,
        )

        self.message = Message.objects.create(
            room=self.room,
            sender_user_id="1",
            sender_device_id=str(self.sender_device_id),
            client_message_id=uuid.UUID(
                "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
            ),
            message_type=Message.MessageType.TEXT,
            encrypted_payload="DIRECT_CIPHERTEXT",
            encryption_metadata={
                "algorithm": "xchacha20poly1305",
                "nonce": "DIRECT_NONCE",
            },
            encryption_version=1,
        )

        self.publish_patcher = patch(
            "apps.chat_messages.receipt_views.schedule_message_delivered_receipts_publish"
        )
        self.mock_schedule_publish = self.publish_patcher.start()
        self.addCleanup(self.publish_patcher.stop)

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
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

    def valid_payload(self):
        return {
            "device_id": str(self.recipient_device_id),
            "message_ids": [
                str(self.message.id),
            ],
        }

    def test_new_delivered_receipt_schedules_realtime_publish(self):
        self.authenticate_as("2")

        response = self.client.post(
            self.url,
            self.valid_payload(),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            response.json(),
        )

        self.assertEqual(response.json()["data"]["updated_count"], 1)
        self.assertEqual(MessageReceipt.objects.count(), 1)

        receipt = MessageReceipt.objects.get()

        self.mock_schedule_publish.assert_called_once()
        call_kwargs = self.mock_schedule_publish.call_args.kwargs

        self.assertEqual(
            call_kwargs["receipt_ids"],
            [
                receipt.id,
            ],
        )

    def test_idempotent_delivered_receipt_does_not_schedule_duplicate_publish(self):
        self.authenticate_as("2")
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

        self.assertEqual(first_response.status_code, status.HTTP_200_OK)
        self.assertEqual(second_response.status_code, status.HTTP_200_OK)

        self.assertEqual(first_response.json()["data"]["updated_count"], 1)
        self.assertEqual(second_response.json()["data"]["updated_count"], 0)

        self.assertEqual(MessageReceipt.objects.count(), 1)
        self.mock_schedule_publish.assert_called_once()

    def test_suppressed_delivered_receipt_does_not_schedule_publish(self):
        """
        This matches the ghost rule.

        If recipient-user 2 ghosted sender-user 1 at message-send time,
        backend suppresses delivered/read receipts for this message.
        """

        DirectMessageReceiptDecision.objects.create(
            message=self.message,
            sender_user_id="1",
            recipient_user_id="2",
            suppress_delivered_receipt=True,
            suppress_read_receipt=True,
            policy_reason=DirectMessageReceiptDecision.PolicyReason.GHOST,
            policy_version=1,
        )

        self.authenticate_as("2")

        response = self.client.post(
            self.url,
            self.valid_payload(),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            response.json(),
        )

        self.assertEqual(response.json()["data"]["updated_count"], 0)
        self.assertEqual(MessageReceipt.objects.count(), 0)

        self.mock_schedule_publish.assert_not_called()
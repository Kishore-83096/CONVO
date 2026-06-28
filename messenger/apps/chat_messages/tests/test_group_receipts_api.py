import uuid

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.chat_messages.models import Message, MessageReceipt
from apps.e2ee_devices.models import Device
from apps.group_chat.tests.factories import (
    GROUP_MEMBER_USER_ID,
    GROUP_NEW_MEMBER_USER_ID,
    GROUP_OWNER_USER_ID,
    authenticate_client,
    create_group_room,
)
from apps.rooms.models import RoomMember


def create_device(
    *,
    user_id: str,
    is_active: bool = True,
) -> Device:
    return Device.objects.create(
        user_id=user_id,
        device_name="Web",
        platform=Device.Platform.WEB,
        registration_id=12345,
        identity_key_public=f"identity-public-{uuid.uuid4()}",
        signed_prekey_id=1,
        signed_prekey_public=f"signed-prekey-public-{uuid.uuid4()}",
        signed_prekey_signature=f"signature-{uuid.uuid4()}",
        key_algorithm="curve25519",
        key_bundle_version=1,
        is_active=is_active,
    )


def create_group_message(
    *,
    room,
    sender_user_id: str,
):
    return Message.objects.create(
        room=room,
        sender_user_id=sender_user_id,
        sender_device_id=str(uuid.uuid4()),
        client_message_id=uuid.uuid4(),
        message_type=Message.MessageType.TEXT,
        encrypted_payload="ciphertext",
        encryption_metadata={
            "algorithm": "group-sender-key-v1",
        },
        encryption_version=1,
    )


class GroupReceiptAPITests(APITestCase):
    def delivered_url(self):
        return reverse("chat_messages:message-receipts-delivered")

    def read_url(self):
        return reverse("chat_messages:message-receipts-read")

    def summary_url(self, message_id):
        return reverse(
            "chat_messages:message-receipts-summary",
            kwargs={"message_id": message_id},
        )

    def test_delivered_receipt_is_created(self):
        profile = create_group_room(
            member_user_ids=[GROUP_MEMBER_USER_ID],
        )
        device = create_device(user_id=GROUP_MEMBER_USER_ID)
        message = create_group_message(
            room=profile.room,
            sender_user_id=GROUP_OWNER_USER_ID,
        )

        authenticate_client(self.client, GROUP_MEMBER_USER_ID)

        response = self.client.post(
            self.delivered_url(),
            {
                "device_id": str(device.id),
                "message_ids": [str(message.id)],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(MessageReceipt.objects.count(), 1)

        receipt = MessageReceipt.objects.get()
        self.assertEqual(receipt.message_id, message.id)
        self.assertEqual(receipt.recipient_user_id, GROUP_MEMBER_USER_ID)
        self.assertIsNotNone(receipt.delivered_at)
        self.assertIsNone(receipt.read_at)

    def test_delivered_receipt_is_idempotent(self):
        profile = create_group_room(
            member_user_ids=[GROUP_MEMBER_USER_ID],
        )
        device = create_device(user_id=GROUP_MEMBER_USER_ID)
        message = create_group_message(
            room=profile.room,
            sender_user_id=GROUP_OWNER_USER_ID,
        )

        authenticate_client(self.client, GROUP_MEMBER_USER_ID)

        payload = {
            "device_id": str(device.id),
            "message_ids": [str(message.id)],
        }

        first_response = self.client.post(
            self.delivered_url(),
            payload,
            format="json",
        )
        second_response = self.client.post(
            self.delivered_url(),
            payload,
            format="json",
        )

        self.assertEqual(first_response.status_code, status.HTTP_200_OK)
        self.assertEqual(second_response.status_code, status.HTTP_200_OK)
        self.assertEqual(MessageReceipt.objects.count(), 1)

    def test_read_through_marks_previous_group_messages_read(self):
        profile = create_group_room(
            member_user_ids=[GROUP_MEMBER_USER_ID],
        )
        device = create_device(user_id=GROUP_MEMBER_USER_ID)

        first = create_group_message(
            room=profile.room,
            sender_user_id=GROUP_OWNER_USER_ID,
        )
        second = create_group_message(
            room=profile.room,
            sender_user_id=GROUP_OWNER_USER_ID,
        )

        authenticate_client(self.client, GROUP_MEMBER_USER_ID)

        response = self.client.post(
            self.read_url(),
            {
                "device_id": str(device.id),
                "group_id": str(profile.room.id),
                "read_through_message_id": str(second.id),
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(MessageReceipt.objects.count(), 2)

        for message in [first, second]:
            receipt = MessageReceipt.objects.get(message=message)
            self.assertIsNotNone(receipt.delivered_at)
            self.assertIsNotNone(receipt.read_at)

    def test_historical_member_cannot_ack_newer_messages(self):
        profile = create_group_room(
            member_user_ids=[GROUP_MEMBER_USER_ID],
        )
        device = create_device(user_id=GROUP_MEMBER_USER_ID)

        member = RoomMember.objects.get(
            room=profile.room,
            user_id=GROUP_MEMBER_USER_ID,
        )
        member.is_active = False
        member.removed_by_user_id = GROUP_OWNER_USER_ID
        member.save(
            update_fields=[
                "is_active",
                "removed_by_user_id",
            ]
        )

        message = create_group_message(
            room=profile.room,
            sender_user_id=GROUP_OWNER_USER_ID,
        )

        authenticate_client(self.client, GROUP_MEMBER_USER_ID)

        response = self.client.post(
            self.delivered_url(),
            {
                "device_id": str(device.id),
                "message_ids": [str(message.id)],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(MessageReceipt.objects.count(), 0)

    def test_receipt_summary_is_returned(self):
        profile = create_group_room(
            member_user_ids=[GROUP_MEMBER_USER_ID],
        )
        device = create_device(user_id=GROUP_MEMBER_USER_ID)
        message = create_group_message(
            room=profile.room,
            sender_user_id=GROUP_OWNER_USER_ID,
        )

        MessageReceipt.objects.create(
            message=message,
            recipient_user_id=GROUP_MEMBER_USER_ID,
            recipient_device=device,
        )

        authenticate_client(self.client, GROUP_OWNER_USER_ID)

        response = self.client.get(
            self.summary_url(message.id),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["data"]["message_id"], str(message.id))
import uuid
from unittest.mock import patch

from rest_framework import status
from rest_framework.test import APITestCase

from apps.chat_messages.models import Message, MessageReceipt
from apps.chat_messages.tests.test_group_receipts_api import (
    create_device,
    create_group_message,
)
from apps.group_chat.tests.factories import (
    GROUP_MEMBER_USER_ID,
    GROUP_OWNER_USER_ID,
    authenticate_client,
    create_group_room,
)


class ReadReceiptRealtimePublishAPITests(APITestCase):
    def setUp(self):
        self.publish_patcher = patch(
            "apps.chat_messages.receipt_views.schedule_message_read_receipts_publish"
        )
        self.mock_schedule_publish = self.publish_patcher.start()
        self.addCleanup(self.publish_patcher.stop)

    def read_url(self):
        from django.urls import reverse

        return reverse("chat_messages:message-receipts-read")

    def test_new_read_receipts_schedule_realtime_publish(self):
        profile = create_group_room(
            member_user_ids=[
                GROUP_MEMBER_USER_ID,
            ],
        )
        device = create_device(
            user_id=GROUP_MEMBER_USER_ID,
        )

        first = create_group_message(
            room=profile.room,
            sender_user_id=GROUP_OWNER_USER_ID,
        )
        second = create_group_message(
            room=profile.room,
            sender_user_id=GROUP_OWNER_USER_ID,
        )

        authenticate_client(
            self.client,
            GROUP_MEMBER_USER_ID,
        )

        response = self.client.post(
            self.read_url(),
            {
                "device_id": str(device.id),
                "group_id": str(profile.room.id),
                "read_through_message_id": str(second.id),
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            response.json(),
        )

        self.assertEqual(response.json()["data"]["updated_count"], 2)
        self.assertEqual(MessageReceipt.objects.count(), 2)

        receipt_ids = list(
            MessageReceipt.objects
            .filter(
                message_id__in=[
                    first.id,
                    second.id,
                ],
            )
            .order_by("message__created_at", "message_id")
            .values_list(
                "id",
                flat=True,
            )
        )

        self.mock_schedule_publish.assert_called_once()

        call_kwargs = self.mock_schedule_publish.call_args.kwargs

        self.assertEqual(
            call_kwargs["receipt_ids"],
            receipt_ids,
        )

    def test_idempotent_read_receipt_does_not_schedule_duplicate_publish(self):
        profile = create_group_room(
            member_user_ids=[
                GROUP_MEMBER_USER_ID,
            ],
        )
        device = create_device(
            user_id=GROUP_MEMBER_USER_ID,
        )

        message = create_group_message(
            room=profile.room,
            sender_user_id=GROUP_OWNER_USER_ID,
        )

        payload = {
            "device_id": str(device.id),
            "group_id": str(profile.room.id),
            "read_through_message_id": str(message.id),
        }

        authenticate_client(
            self.client,
            GROUP_MEMBER_USER_ID,
        )

        first_response = self.client.post(
            self.read_url(),
            payload,
            format="json",
        )
        second_response = self.client.post(
            self.read_url(),
            payload,
            format="json",
        )

        self.assertEqual(first_response.status_code, status.HTTP_200_OK)
        self.assertEqual(second_response.status_code, status.HTTP_200_OK)

        self.assertEqual(first_response.json()["data"]["updated_count"], 1)
        self.assertEqual(second_response.json()["data"]["updated_count"], 0)

        self.assertEqual(MessageReceipt.objects.count(), 1)
        self.mock_schedule_publish.assert_called_once()

    def test_read_receipt_for_own_message_does_not_schedule_publish(self):
        profile = create_group_room(
            member_user_ids=[
                GROUP_MEMBER_USER_ID,
            ],
        )
        device = create_device(
            user_id=GROUP_MEMBER_USER_ID,
        )

        own_message = create_group_message(
            room=profile.room,
            sender_user_id=GROUP_MEMBER_USER_ID,
        )

        authenticate_client(
            self.client,
            GROUP_MEMBER_USER_ID,
        )

        response = self.client.post(
            self.read_url(),
            {
                "device_id": str(device.id),
                "group_id": str(profile.room.id),
                "read_through_message_id": str(own_message.id),
            },
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
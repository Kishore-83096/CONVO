from unittest.mock import patch

from rest_framework import status

from apps.chat_messages.models import GroupMessageEncryption, Message
from apps.chat_messages.tests.test_group_message_api import (
    GROUP_MEMBER_USER_ID,
    authenticate_client,
    create_sender_key,
    distribute_sender_key_to_device,
    create_device,
    group_message_payload,
)
from apps.group_chat.tests.factories import (
    GROUP_NEW_MEMBER_USER_ID,
    GROUP_OWNER_USER_ID,
    create_group_room,
)
from apps.e2ee_devices.models import Device
from .test_group_message_api import GroupMessageSendingAPITests


class GroupMessageRealtimePublishAPITests(GroupMessageSendingAPITests):
    def setUp(self):
        self.publish_patcher = patch(
            "apps.chat_messages.group_views.schedule_group_message_stored_publish"
        )
        self.mock_schedule_publish = self.publish_patcher.start()
        self.addCleanup(self.publish_patcher.stop)

    def test_new_group_message_schedules_realtime_publish(self):
        profile, sender_device, sender_key = self._ready_sender_setup()
        authenticate_client(self.client, GROUP_MEMBER_USER_ID)

        response = self.client.post(
            self.send_url(),
            group_message_payload(
                profile=profile,
                sender_device=sender_device,
                sender_key=sender_key,
            ),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
            response.json(),
        )

        self.assertEqual(Message.objects.count(), 1)
        self.assertEqual(GroupMessageEncryption.objects.count(), 1)

        self.mock_schedule_publish.assert_called_once()

        call_kwargs = self.mock_schedule_publish.call_args.kwargs

        self.assertEqual(
            str(call_kwargs["message_id"]),
            response.json()["data"]["message"]["message_id"],
        )
        self.assertEqual(
            str(call_kwargs["sender_device_id"]),
            str(sender_device.id),
        )

    def test_group_message_idempotent_retry_does_not_schedule_duplicate_realtime_publish(self):
        profile, sender_device, sender_key = self._ready_sender_setup()
        authenticate_client(self.client, GROUP_MEMBER_USER_ID)

        payload = group_message_payload(
            profile=profile,
            sender_device=sender_device,
            sender_key=sender_key,
        )

        first_response = self.client.post(
            self.send_url(),
            payload,
            format="json",
        )
        second_response = self.client.post(
            self.send_url(),
            payload,
            format="json",
        )

        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second_response.status_code, status.HTTP_200_OK)

        self.assertTrue(first_response.json()["data"]["message_created"])
        self.assertFalse(second_response.json()["data"]["message_created"])

        self.assertEqual(Message.objects.count(), 1)
        self.assertEqual(GroupMessageEncryption.objects.count(), 1)

        self.mock_schedule_publish.assert_called_once()

    def test_failed_group_message_does_not_schedule_realtime_publish(self):
        profile, sender_device, sender_key = self._ready_sender_setup()

        Device.objects.filter(
            id=sender_device.id,
        ).update(
            is_active=False,
        )

        authenticate_client(self.client, GROUP_MEMBER_USER_ID)

        response = self.client.post(
            self.send_url(),
            group_message_payload(
                profile=profile,
                sender_device=sender_device,
                sender_key=sender_key,
            ),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.mock_schedule_publish.assert_not_called()
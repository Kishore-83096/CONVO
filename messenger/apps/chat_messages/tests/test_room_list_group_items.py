from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.group_chat.tests.factories import (
    GROUP_MEMBER_USER_ID,
    GROUP_OWNER_USER_ID,
    authenticate_client,
    create_group_room,
)
from apps.rooms.models import Room, RoomMember


class RoomListGroupItemTests(APITestCase):
    def test_room_list_returns_group_items_with_group_discriminant(self):
        profile = create_group_room(
            owner_user_id=GROUP_OWNER_USER_ID,
            member_user_ids=[GROUP_MEMBER_USER_ID],
            name="Backend Engineering",
        )

        authenticate_client(self.client, GROUP_MEMBER_USER_ID)

        response = self.client.get(
            reverse("chat_messages:room-list")
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        rooms = response.json()["data"]
        self.assertEqual(len(rooms), 1)

        item = rooms[0]
        self.assertEqual(item["id"], str(profile.room.id))
        self.assertEqual(item["room_type"], "group")
        self.assertEqual(item["name"], "Backend Engineering")
        self.assertEqual(item["group"]["caller_role"], "member")
        self.assertEqual(item["group"]["member_count"], 2)
        self.assertFalse(item["group"]["security_ready"])
        self.assertEqual(item["group"]["active_epoch_number"], 1)
        self.assertIsNone(item["last_message"])

    def test_direct_room_items_keep_group_null(self):
        direct_room = Room.objects.create(
            room_type=Room.RoomType.DIRECT,
            created_by_user_id=GROUP_OWNER_USER_ID,
            direct_pair_key=(
                "11111111111111111111111111111111"
                "11111111111111111111111111111111"
            ),
            is_active=True,
        )

        RoomMember.objects.create(
            room=direct_room,
            user_id=GROUP_OWNER_USER_ID,
            role=RoomMember.Role.MEMBER,
            added_by_user_id=GROUP_OWNER_USER_ID,
            is_active=True,
        )
        RoomMember.objects.create(
            room=direct_room,
            user_id=GROUP_MEMBER_USER_ID,
            role=RoomMember.Role.MEMBER,
            added_by_user_id=GROUP_OWNER_USER_ID,
            is_active=True,
        )

        authenticate_client(self.client, GROUP_OWNER_USER_ID)

        response = self.client.get(
            reverse("chat_messages:room-list")
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        rooms = response.json()["data"]
        self.assertEqual(len(rooms), 1)

        item = rooms[0]
        self.assertEqual(item["id"], str(direct_room.id))
        self.assertEqual(item["room_type"], "direct")
        self.assertIsNone(item["group"])
        self.assertEqual(
            item["other_member_user_ids"],
            [GROUP_MEMBER_USER_ID],
        )
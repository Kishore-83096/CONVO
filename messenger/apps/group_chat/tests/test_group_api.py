from unittest.mock import patch

from django.db import IntegrityError
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.group_chat.models import GroupProfile
from apps.rooms.models import Room, RoomMember
from messenger_config.identity_client import UnknownIdentityUsersError

from .factories import (
    GROUP_MEMBER_USER_ID,
    GROUP_OUTSIDER_USER_ID,
    GROUP_OWNER_USER_ID,
    authenticate_client,
    create_group_room,
)


class GroupAPITests(APITestCase):
    def setUp(self):
        self.list_url = reverse("group_chat:group-list-create")

    def valid_payload(self):
        return {
            "name": "Backend Engineering",
            "description": "Myna backend team",
            "member_user_ids": ["2", "3"],
            "max_members": 100,
            "join_history_visible": False,
            "only_admins_can_send": False,
            "only_admins_can_edit_info": True,
        }

    def assert_nothing_stored(self):
        self.assertEqual(Room.objects.count(), 0)
        self.assertEqual(RoomMember.objects.count(), 0)
        self.assertEqual(GroupProfile.objects.count(), 0)

    def test_authentication_is_required(self):
        response = self.client.post(
            self.list_url,
            self.valid_payload(),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assert_nothing_stored()

    @patch("apps.group_chat.services.groups.validate_identity_user_ids")
    def test_group_can_be_created_with_owner_and_members(self, validate_users):
        authenticate_client(self.client, GROUP_OWNER_USER_ID)

        response = self.client.post(
            self.list_url,
            self.valid_payload(),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Room.objects.count(), 1)
        self.assertEqual(GroupProfile.objects.count(), 1)
        self.assertEqual(RoomMember.objects.count(), 3)

        room = Room.objects.get()
        self.assertEqual(room.room_type, Room.RoomType.GROUP)
        self.assertIsNone(room.direct_pair_key)
        self.assertEqual(room.name, "Backend Engineering")

        owner = RoomMember.objects.get(user_id=GROUP_OWNER_USER_ID)
        self.assertEqual(owner.role, RoomMember.Role.OWNER)

        validate_users.assert_called_once()
        called_user_ids = validate_users.call_args.kwargs["user_ids"]
        self.assertEqual(called_user_ids, ["1", "2", "3"])

        data = response.json()["data"]
        self.assertEqual(data["id"], str(room.id))
        self.assertEqual(data["room_type"], "group")
        self.assertEqual(data["caller_role"], "owner")
        self.assertEqual(data["member_count"], 3)

    @patch("apps.group_chat.services.groups.validate_identity_user_ids")
    def test_duplicate_member_ids_are_rejected(self, validate_users):
        authenticate_client(self.client, GROUP_OWNER_USER_ID)
        payload = self.valid_payload()
        payload["member_user_ids"] = ["2", "2"]

        response = self.client.post(
            self.list_url,
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assert_nothing_stored()
        validate_users.assert_not_called()

    @patch("apps.group_chat.services.groups.validate_identity_user_ids")
    def test_creator_cannot_be_repeated_as_initial_member(self, validate_users):
        authenticate_client(self.client, GROUP_OWNER_USER_ID)
        payload = self.valid_payload()
        payload["member_user_ids"] = [GROUP_OWNER_USER_ID, "2"]

        response = self.client.post(
            self.list_url,
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assert_nothing_stored()
        validate_users.assert_not_called()

    @patch("apps.group_chat.services.groups.validate_identity_user_ids")
    def test_unknown_identity_user_rolls_back(self, validate_users):
        validate_users.side_effect = UnknownIdentityUsersError(["99"])
        authenticate_client(self.client, GROUP_OWNER_USER_ID)
        payload = self.valid_payload()
        payload["member_user_ids"] = ["99"]

        response = self.client.post(
            self.list_url,
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assert_nothing_stored()

    @patch("apps.group_chat.services.groups.validate_identity_user_ids")
    def test_maximum_size_is_enforced(self, validate_users):
        authenticate_client(self.client, GROUP_OWNER_USER_ID)
        payload = self.valid_payload()
        payload["max_members"] = 2
        payload["member_user_ids"] = ["2", "3"]

        response = self.client.post(
            self.list_url,
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assert_nothing_stored()
        validate_users.assert_not_called()

    @patch("apps.group_chat.services.groups.RoomMember.objects.bulk_create")
    @patch("apps.group_chat.services.groups.validate_identity_user_ids")
    def test_database_error_rolls_back_group_create(
        self,
        validate_users,
        bulk_create,
    ):
        bulk_create.side_effect = IntegrityError("forced failure")
        authenticate_client(self.client, GROUP_OWNER_USER_ID)

        response = self.client.post(
            self.list_url,
            self.valid_payload(),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assert_nothing_stored()

    def test_list_returns_only_authenticated_users_active_groups(self):
        authenticate_client(self.client, GROUP_MEMBER_USER_ID)
        visible_profile = create_group_room(
            member_user_ids=[GROUP_MEMBER_USER_ID],
        )
        create_group_room(
            owner_user_id="9",
            name="Other Group",
            member_user_ids=["10"],
        )

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        groups = response.json()["data"]
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["id"], str(visible_profile.room.id))
        self.assertEqual(groups[0]["caller_role"], "member")

    def test_detail_requires_active_membership(self):
        authenticate_client(self.client, GROUP_OUTSIDER_USER_ID)
        profile = create_group_room()
        url = reverse(
            "group_chat:group-detail",
            kwargs={"group_id": profile.room.id},
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_owner_can_update_group_metadata(self):
        authenticate_client(self.client, GROUP_OWNER_USER_ID)
        profile = create_group_room()
        url = reverse(
            "group_chat:group-detail",
            kwargs={"group_id": profile.room.id},
        )

        response = self.client.patch(
            url,
            {
                "name": "Updated Backend Team",
                "description": "Updated description",
                "join_history_visible": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        profile.refresh_from_db()
        profile.room.refresh_from_db()
        self.assertEqual(profile.room.name, "Updated Backend Team")
        self.assertEqual(profile.description, "Updated description")
        self.assertTrue(profile.join_history_visible)

    def test_member_cannot_update_when_only_admins_can_edit_info(self):
        authenticate_client(self.client, GROUP_MEMBER_USER_ID)
        profile = create_group_room(
            member_user_ids=[GROUP_MEMBER_USER_ID],
            only_admins_can_edit_info=True,
        )
        url = reverse(
            "group_chat:group-detail",
            kwargs={"group_id": profile.room.id},
        )

        response = self.client.patch(
            url,
            {
                "name": "Blocked Update",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_member_can_update_when_info_edit_is_open(self):
        authenticate_client(self.client, GROUP_MEMBER_USER_ID)
        profile = create_group_room(
            member_user_ids=[GROUP_MEMBER_USER_ID],
            only_admins_can_edit_info=False,
        )
        url = reverse(
            "group_chat:group-detail",
            kwargs={"group_id": profile.room.id},
        )

        response = self.client.patch(
            url,
            {
                "description": "Member edited description",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        profile.refresh_from_db()
        self.assertEqual(profile.description, "Member edited description")

    def test_inactive_group_is_not_returned(self):
        authenticate_client(self.client, GROUP_OWNER_USER_ID)
        profile = create_group_room()
        profile.room.is_active = False
        profile.room.save(update_fields=["is_active", "updated_at"])

        list_response = self.client.get(self.list_url)
        detail_response = self.client.get(
            reverse(
                "group_chat:group-detail",
                kwargs={"group_id": profile.room.id},
            )
        )

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(list_response.json()["data"], [])
        self.assertEqual(detail_response.status_code, status.HTTP_404_NOT_FOUND)

    def test_direct_room_id_is_not_treated_as_group(self):
        authenticate_client(self.client, GROUP_OWNER_USER_ID)
        direct_room = Room.objects.create(
            room_type=Room.RoomType.DIRECT,
            created_by_user_id=GROUP_OWNER_USER_ID,
            direct_pair_key=(
                "0123456789abcdef"
                "0123456789abcdef"
                "0123456789abcdef"
                "0123456789abcdef"
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

        response = self.client.get(
            reverse(
                "group_chat:group-detail",
                kwargs={"group_id": direct_room.id},
            )
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
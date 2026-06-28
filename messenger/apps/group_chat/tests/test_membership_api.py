from unittest.mock import patch

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.rooms.models import Room, RoomMember
from messenger_config.identity_client import UnknownIdentityUsersError

from .factories import (
    GROUP_ADMIN_USER_ID,
    GROUP_MEMBER_USER_ID,
    GROUP_NEW_MEMBER_USER_ID,
    GROUP_OUTSIDER_USER_ID,
    GROUP_OWNER_USER_ID,
    GROUP_SECOND_MEMBER_USER_ID,
    authenticate_client,
    create_group_room,
)


class GroupMembershipAPITests(APITestCase):
    def members_url(self, group_id):
        return reverse(
            "group_chat:group-members",
            kwargs={"group_id": group_id},
        )

    def member_remove_url(self, group_id, user_id):
        return reverse(
            "group_chat:group-member-remove",
            kwargs={
                "group_id": group_id,
                "user_id": user_id,
            },
        )

    def role_url(self, group_id, user_id):
        return reverse(
            "group_chat:group-member-role",
            kwargs={
                "group_id": group_id,
                "user_id": user_id,
            },
        )

    def leave_url(self, group_id):
        return reverse(
            "group_chat:group-leave",
            kwargs={"group_id": group_id},
        )

    def transfer_url(self, group_id):
        return reverse(
            "group_chat:group-transfer-ownership",
            kwargs={"group_id": group_id},
        )

    def ban_url(self, group_id, user_id):
        return reverse(
            "group_chat:group-member-ban",
            kwargs={
                "group_id": group_id,
                "user_id": user_id,
            },
        )

    def unban_url(self, group_id, user_id):
        return reverse(
            "group_chat:group-member-unban",
            kwargs={
                "group_id": group_id,
                "user_id": user_id,
            },
        )

    def test_active_member_can_list_members(self):
        profile = create_group_room(
            admin_user_ids=[GROUP_ADMIN_USER_ID],
            member_user_ids=[GROUP_MEMBER_USER_ID],
        )
        authenticate_client(self.client, GROUP_MEMBER_USER_ID)

        response = self.client.get(self.members_url(profile.room.id))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()["data"]), 3)

    def test_non_member_cannot_list_members(self):
        profile = create_group_room()
        authenticate_client(self.client, GROUP_OUTSIDER_USER_ID)

        response = self.client.get(self.members_url(profile.room.id))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @patch("apps.group_chat.services.memberships.validate_identity_user_ids")
    def test_owner_can_add_member(self, validate_users):
        profile = create_group_room()
        authenticate_client(self.client, GROUP_OWNER_USER_ID)

        response = self.client.post(
            self.members_url(profile.room.id),
            {
                "member_user_ids": [GROUP_NEW_MEMBER_USER_ID],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            RoomMember.objects.filter(
                room=profile.room,
                user_id=GROUP_NEW_MEMBER_USER_ID,
                is_active=True,
            ).exists()
        )
        validate_users.assert_called_once()

    @patch("apps.group_chat.services.memberships.validate_identity_user_ids")
    def test_admin_can_add_member(self, validate_users):
        profile = create_group_room(
            admin_user_ids=[GROUP_ADMIN_USER_ID],
            member_user_ids=[GROUP_MEMBER_USER_ID],
        )
        authenticate_client(self.client, GROUP_ADMIN_USER_ID)

        response = self.client.post(
            self.members_url(profile.room.id),
            {
                "member_user_ids": [GROUP_NEW_MEMBER_USER_ID],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    @patch("apps.group_chat.services.memberships.validate_identity_user_ids")
    def test_normal_member_cannot_add_member(self, validate_users):
        profile = create_group_room()
        authenticate_client(self.client, GROUP_MEMBER_USER_ID)

        response = self.client.post(
            self.members_url(profile.room.id),
            {
                "member_user_ids": [GROUP_NEW_MEMBER_USER_ID],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch("apps.group_chat.services.memberships.validate_identity_user_ids")
    def test_duplicate_add_is_rejected(self, validate_users):
        profile = create_group_room()
        authenticate_client(self.client, GROUP_OWNER_USER_ID)

        response = self.client.post(
            self.members_url(profile.room.id),
            {
                "member_user_ids": [GROUP_MEMBER_USER_ID],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    @patch("apps.group_chat.services.memberships.validate_identity_user_ids")
    def test_unknown_identity_user_is_rejected(self, validate_users):
        validate_users.side_effect = UnknownIdentityUsersError(["404"])
        profile = create_group_room()
        authenticate_client(self.client, GROUP_OWNER_USER_ID)

        response = self.client.post(
            self.members_url(profile.room.id),
            {
                "member_user_ids": ["404"],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("apps.group_chat.services.memberships.validate_identity_user_ids")
    def test_removed_member_can_be_reactivated(self, validate_users):
        profile = create_group_room()
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
                "updated_at",
            ]
        )

        authenticate_client(self.client, GROUP_OWNER_USER_ID)

        response = self.client.post(
            self.members_url(profile.room.id),
            {
                "member_user_ids": [GROUP_MEMBER_USER_ID],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        member.refresh_from_db()
        self.assertTrue(member.is_active)
        self.assertIsNone(member.removed_by_user_id)
        self.assertGreater(member.membership_version, 1)

    def test_owner_can_remove_normal_member(self):
        profile = create_group_room()
        authenticate_client(self.client, GROUP_OWNER_USER_ID)

        response = self.client.delete(
            self.member_remove_url(
                profile.room.id,
                GROUP_MEMBER_USER_ID,
            )
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        member = RoomMember.objects.get(
            room=profile.room,
            user_id=GROUP_MEMBER_USER_ID,
        )
        self.assertFalse(member.is_active)
        self.assertIsNotNone(member.removed_at)
        self.assertEqual(member.removed_by_user_id, GROUP_OWNER_USER_ID)

    def test_admin_can_remove_normal_member(self):
        profile = create_group_room(
            admin_user_ids=[GROUP_ADMIN_USER_ID],
            member_user_ids=[GROUP_MEMBER_USER_ID],
        )
        authenticate_client(self.client, GROUP_ADMIN_USER_ID)

        response = self.client.delete(
            self.member_remove_url(
                profile.room.id,
                GROUP_MEMBER_USER_ID,
            )
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_admin_cannot_remove_owner(self):
        profile = create_group_room(
            admin_user_ids=[GROUP_ADMIN_USER_ID],
            member_user_ids=[GROUP_MEMBER_USER_ID],
        )
        authenticate_client(self.client, GROUP_ADMIN_USER_ID)

        response = self.client.delete(
            self.member_remove_url(
                profile.room.id,
                GROUP_OWNER_USER_ID,
            )
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_can_promote_member_to_admin(self):
        profile = create_group_room()
        authenticate_client(self.client, GROUP_OWNER_USER_ID)

        response = self.client.patch(
            self.role_url(
                profile.room.id,
                GROUP_MEMBER_USER_ID,
            ),
            {
                "role": "admin",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        member = RoomMember.objects.get(
            room=profile.room,
            user_id=GROUP_MEMBER_USER_ID,
        )
        self.assertEqual(member.role, RoomMember.Role.ADMIN)

    def test_admin_cannot_change_roles(self):
        profile = create_group_room(
            admin_user_ids=[GROUP_ADMIN_USER_ID],
            member_user_ids=[GROUP_MEMBER_USER_ID],
        )
        authenticate_client(self.client, GROUP_ADMIN_USER_ID)

        response = self.client.patch(
            self.role_url(
                profile.room.id,
                GROUP_MEMBER_USER_ID,
            ),
            {
                "role": "admin",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_member_can_leave_group(self):
        profile = create_group_room()
        authenticate_client(self.client, GROUP_MEMBER_USER_ID)

        response = self.client.post(self.leave_url(profile.room.id))

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        member = RoomMember.objects.get(
            room=profile.room,
            user_id=GROUP_MEMBER_USER_ID,
        )
        self.assertFalse(member.is_active)
        self.assertIsNotNone(member.left_at)

    def test_owner_must_transfer_before_leaving(self):
        profile = create_group_room()
        authenticate_client(self.client, GROUP_OWNER_USER_ID)

        response = self.client.post(self.leave_url(profile.room.id))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_can_transfer_ownership(self):
        profile = create_group_room(
            member_user_ids=[
                GROUP_MEMBER_USER_ID,
                GROUP_SECOND_MEMBER_USER_ID,
            ],
        )
        authenticate_client(self.client, GROUP_OWNER_USER_ID)

        response = self.client.post(
            self.transfer_url(profile.room.id),
            {
                "new_owner_user_id": GROUP_MEMBER_USER_ID,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        old_owner = RoomMember.objects.get(
            room=profile.room,
            user_id=GROUP_OWNER_USER_ID,
        )
        new_owner = RoomMember.objects.get(
            room=profile.room,
            user_id=GROUP_MEMBER_USER_ID,
        )

        self.assertEqual(old_owner.role, RoomMember.Role.ADMIN)
        self.assertEqual(new_owner.role, RoomMember.Role.OWNER)

        active_owners = RoomMember.objects.filter(
            room=profile.room,
            role=RoomMember.Role.OWNER,
            is_active=True,
        ).count()
        self.assertEqual(active_owners, 1)

    def test_non_owner_cannot_transfer_ownership(self):
        profile = create_group_room()
        authenticate_client(self.client, GROUP_MEMBER_USER_ID)

        response = self.client.post(
            self.transfer_url(profile.room.id),
            {
                "new_owner_user_id": GROUP_OWNER_USER_ID,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_can_ban_member(self):
        profile = create_group_room()
        authenticate_client(self.client, GROUP_OWNER_USER_ID)

        response = self.client.post(
            self.ban_url(
                profile.room.id,
                GROUP_MEMBER_USER_ID,
            )
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        member = RoomMember.objects.get(
            room=profile.room,
            user_id=GROUP_MEMBER_USER_ID,
        )
        self.assertFalse(member.is_active)
        self.assertIsNotNone(member.banned_at)

    @patch("apps.group_chat.services.memberships.validate_identity_user_ids")
    def test_banned_member_cannot_be_readded(self, validate_users):
        profile = create_group_room()
        member = RoomMember.objects.get(
            room=profile.room,
            user_id=GROUP_MEMBER_USER_ID,
        )
        member.is_active = False
        member.banned_at = member.updated_at
        member.save(
            update_fields=[
                "is_active",
                "banned_at",
                "updated_at",
            ]
        )

        authenticate_client(self.client, GROUP_OWNER_USER_ID)

        response = self.client.post(
            self.members_url(profile.room.id),
            {
                "member_user_ids": [GROUP_MEMBER_USER_ID],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_can_unban_member(self):
        profile = create_group_room()
        member = RoomMember.objects.get(
            room=profile.room,
            user_id=GROUP_MEMBER_USER_ID,
        )
        member.is_active = False
        member.banned_at = member.updated_at
        member.save(
            update_fields=[
                "is_active",
                "banned_at",
                "updated_at",
            ]
        )

        authenticate_client(self.client, GROUP_OWNER_USER_ID)

        response = self.client.post(
            self.unban_url(
                profile.room.id,
                GROUP_MEMBER_USER_ID,
            )
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        member.refresh_from_db()
        self.assertIsNone(member.banned_at)
        self.assertFalse(member.is_active)

    def test_cross_group_access_is_denied(self):
        visible_profile = create_group_room(
            owner_user_id=GROUP_OWNER_USER_ID,
            member_user_ids=[GROUP_MEMBER_USER_ID],
        )
        other_profile = create_group_room(
            owner_user_id="100",
            member_user_ids=["101"],
        )

        authenticate_client(self.client, GROUP_MEMBER_USER_ID)

        response = self.client.get(
            self.members_url(other_profile.room.id)
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        own_response = self.client.get(
            self.members_url(visible_profile.room.id)
        )
        self.assertEqual(own_response.status_code, status.HTTP_200_OK)

    def test_direct_room_is_not_treated_as_group(self):
        direct_room = Room.objects.create(
            room_type=Room.RoomType.DIRECT,
            created_by_user_id=GROUP_OWNER_USER_ID,
            direct_pair_key=(
                "abcdefabcdefabcdefabcdefabcdefab"
                "abcdefabcdefabcdefabcdefabcdefab"
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

        authenticate_client(self.client, GROUP_OWNER_USER_ID)

        response = self.client.get(
            self.members_url(direct_room.id)
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
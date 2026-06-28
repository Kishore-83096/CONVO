from django.test import TestCase

from apps.group_chat.permissions import (
    can_add_members,
    can_ban_member,
    can_change_role,
    can_leave_group,
    can_remove_member,
    can_transfer_ownership,
    can_update_group,
    can_view_group,
)
from apps.rooms.models import RoomMember

from .factories import (
    GROUP_ADMIN_USER_ID,
    GROUP_MEMBER_USER_ID,
    GROUP_OWNER_USER_ID,
    create_group_room,
)


class GroupPermissionTests(TestCase):
    def setUp(self):
        self.profile = create_group_room(
            admin_user_ids=[GROUP_ADMIN_USER_ID],
            member_user_ids=[GROUP_MEMBER_USER_ID],
        )
        self.owner = RoomMember.objects.get(
            room=self.profile.room,
            user_id=GROUP_OWNER_USER_ID,
        )
        self.admin = RoomMember.objects.get(
            room=self.profile.room,
            user_id=GROUP_ADMIN_USER_ID,
        )
        self.member = RoomMember.objects.get(
            room=self.profile.room,
            user_id=GROUP_MEMBER_USER_ID,
        )

    def test_active_members_can_view_group(self):
        self.assertTrue(can_view_group(self.owner))
        self.assertTrue(can_view_group(self.admin))
        self.assertTrue(can_view_group(self.member))

    def test_update_group_respects_metadata_setting(self):
        self.profile.only_admins_can_edit_info = True

        self.assertTrue(can_update_group(self.profile, self.owner))
        self.assertTrue(can_update_group(self.profile, self.admin))
        self.assertFalse(can_update_group(self.profile, self.member))

        self.profile.only_admins_can_edit_info = False

        self.assertTrue(can_update_group(self.profile, self.member))

    def test_add_member_permissions(self):
        self.assertTrue(can_add_members(self.owner))
        self.assertTrue(can_add_members(self.admin))
        self.assertFalse(can_add_members(self.member))

    def test_remove_member_permissions(self):
        self.assertTrue(can_remove_member(self.owner, self.member))
        self.assertTrue(can_remove_member(self.owner, self.admin))
        self.assertTrue(can_remove_member(self.admin, self.member))

        self.assertFalse(can_remove_member(self.admin, self.owner))
        self.assertFalse(can_remove_member(self.member, self.admin))

    def test_change_role_permissions(self):
        self.assertTrue(
            can_change_role(
                self.owner,
                self.member,
                RoomMember.Role.ADMIN,
            )
        )
        self.assertFalse(
            can_change_role(
                self.admin,
                self.member,
                RoomMember.Role.ADMIN,
            )
        )
        self.assertFalse(
            can_change_role(
                self.owner,
                self.owner,
                RoomMember.Role.MEMBER,
            )
        )

    def test_transfer_ownership_permissions(self):
        self.assertTrue(can_transfer_ownership(self.owner, self.member))
        self.assertFalse(can_transfer_ownership(self.admin, self.member))
        self.assertFalse(can_transfer_ownership(self.owner, self.owner))

    def test_leave_group_permissions(self):
        self.assertFalse(can_leave_group(self.owner))
        self.assertTrue(can_leave_group(self.admin))
        self.assertTrue(can_leave_group(self.member))

    def test_ban_permissions(self):
        self.assertTrue(can_ban_member(self.owner, self.member))
        self.assertFalse(can_ban_member(self.admin, self.member))
        self.assertFalse(can_ban_member(self.owner, self.owner))

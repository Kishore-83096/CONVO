from unittest.mock import patch

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.group_chat.constants import (
    GROUP_AUDIT_GROUP_CREATED,
    GROUP_AUDIT_GROUP_UPDATED,
    GROUP_AUDIT_MEMBER_REMOVED,
    GROUP_AUDIT_MEMBERS_ADDED,
    GROUP_AUDIT_OWNERSHIP_TRANSFERRED,
)
from apps.group_chat.models import GroupAuditEvent
from apps.rooms.models import RoomMember

from .factories import (
    GROUP_MEMBER_USER_ID,
    GROUP_NEW_MEMBER_USER_ID,
    GROUP_OWNER_USER_ID,
    authenticate_client,
    create_group_room,
)


class GroupAuditTests(APITestCase):
    @patch("apps.group_chat.services.groups.validate_identity_user_ids")
    def test_group_create_writes_audit_event(self, validate_users):
        authenticate_client(self.client, GROUP_OWNER_USER_ID)

        response = self.client.post(
            reverse("group_chat:group-list-create"),
            {
                "name": "Backend Engineering",
                "description": "Myna backend team",
                "member_user_ids": [GROUP_MEMBER_USER_ID],
                "max_members": 100,
                "join_history_visible": False,
                "only_admins_can_send": False,
                "only_admins_can_edit_info": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        event = GroupAuditEvent.objects.get(
            event_type=GROUP_AUDIT_GROUP_CREATED,
        )
        self.assertEqual(event.actor_user_id, GROUP_OWNER_USER_ID)
        self.assertEqual(event.metadata["initial_member_count"], 2)

    def test_group_update_writes_audit_event(self):
        profile = create_group_room()
        authenticate_client(self.client, GROUP_OWNER_USER_ID)

        response = self.client.patch(
            reverse(
                "group_chat:group-detail",
                kwargs={"group_id": profile.room.id},
            ),
            {
                "description": "Updated description",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        event = GroupAuditEvent.objects.get(
            event_type=GROUP_AUDIT_GROUP_UPDATED,
        )
        self.assertEqual(event.actor_user_id, GROUP_OWNER_USER_ID)
        self.assertEqual(
            event.metadata["changed_fields"],
            ["description"],
        )

    @patch("apps.group_chat.services.memberships.validate_identity_user_ids")
    def test_add_members_writes_audit_event(self, validate_users):
        profile = create_group_room()
        authenticate_client(self.client, GROUP_OWNER_USER_ID)

        response = self.client.post(
            reverse(
                "group_chat:group-members",
                kwargs={"group_id": profile.room.id},
            ),
            {
                "member_user_ids": [GROUP_NEW_MEMBER_USER_ID],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        event = GroupAuditEvent.objects.get(
            event_type=GROUP_AUDIT_MEMBERS_ADDED,
        )
        self.assertEqual(event.actor_user_id, GROUP_OWNER_USER_ID)
        self.assertEqual(
            event.metadata["member_user_ids"],
            [GROUP_NEW_MEMBER_USER_ID],
        )

    def test_remove_member_writes_audit_event(self):
        profile = create_group_room()
        authenticate_client(self.client, GROUP_OWNER_USER_ID)

        response = self.client.delete(
            reverse(
                "group_chat:group-member-remove",
                kwargs={
                    "group_id": profile.room.id,
                    "user_id": GROUP_MEMBER_USER_ID,
                },
            )
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        event = GroupAuditEvent.objects.get(
            event_type=GROUP_AUDIT_MEMBER_REMOVED,
        )
        self.assertEqual(event.target_user_id, GROUP_MEMBER_USER_ID)
        self.assertEqual(event.actor_user_id, GROUP_OWNER_USER_ID)

    def test_transfer_ownership_writes_audit_event(self):
        profile = create_group_room()
        authenticate_client(self.client, GROUP_OWNER_USER_ID)

        response = self.client.post(
            reverse(
                "group_chat:group-transfer-ownership",
                kwargs={"group_id": profile.room.id},
            ),
            {
                "new_owner_user_id": GROUP_MEMBER_USER_ID,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        event = GroupAuditEvent.objects.get(
            event_type=GROUP_AUDIT_OWNERSHIP_TRANSFERRED,
        )
        self.assertEqual(event.actor_user_id, GROUP_OWNER_USER_ID)
        self.assertEqual(event.target_user_id, GROUP_MEMBER_USER_ID)
        self.assertEqual(
            event.metadata["old_owner_user_id"],
            GROUP_OWNER_USER_ID,
        )
        self.assertEqual(
            event.metadata["new_owner_user_id"],
            GROUP_MEMBER_USER_ID,
        )

        self.assertEqual(
            RoomMember.objects.get(
                room=profile.room,
                user_id=GROUP_MEMBER_USER_ID,
            ).role,
            RoomMember.Role.OWNER,
        )

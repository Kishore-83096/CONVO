from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.group_chat.constants import (
    EPOCH_ROTATION_REASON_MEMBER_ADDED,
    GROUP_AUDIT_EPOCH_ROTATED,
)
from apps.group_chat.models import GroupAuditEvent, GroupEncryptionEpoch
from apps.rooms.models import Room, RoomMember

from .factories import (
    GROUP_ADMIN_USER_ID,
    GROUP_MEMBER_USER_ID,
    GROUP_NEW_MEMBER_USER_ID,
    GROUP_OUTSIDER_USER_ID,
    GROUP_OWNER_USER_ID,
    authenticate_client,
    create_group_room,
)


class GroupEpochAPITests(APITestCase):
    def current_url(self, group_id):
        return reverse(
            "group_chat:group-current-epoch",
            kwargs={"group_id": group_id},
        )

    def list_url(self, group_id):
        return reverse(
            "group_chat:group-epoch-list",
            kwargs={"group_id": group_id},
        )

    def rotate_url(self, group_id):
        return reverse(
            "group_chat:group-epoch-rotate",
            kwargs={"group_id": group_id},
        )

    def test_factory_group_has_initial_epoch(self):
        profile = create_group_room()
        epoch = GroupEncryptionEpoch.objects.get(
            group_room=profile.room,
            status=GroupEncryptionEpoch.Status.ACTIVE,
        )

        self.assertEqual(epoch.epoch_number, 1)
        self.assertEqual(epoch.rotation_reason, "initial")
        self.assertEqual(len(epoch.membership_snapshot_hash), 64)

    def test_current_epoch_requires_active_membership(self):
        profile = create_group_room()
        authenticate_client(self.client, GROUP_OUTSIDER_USER_ID)

        response = self.client.get(self.current_url(profile.room.id))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_current_epoch_returns_epoch_one(self):
        profile = create_group_room()
        authenticate_client(self.client, GROUP_MEMBER_USER_ID)

        response = self.client.get(self.current_url(profile.room.id))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()["data"]
        self.assertEqual(data["epoch_number"], 1)
        self.assertEqual(data["status"], "active")
        self.assertEqual(data["rotation_reason"], "initial")

    def test_epoch_list_returns_closed_and_active_epochs(self):
        profile = create_group_room(
            admin_user_ids=[GROUP_ADMIN_USER_ID],
            member_user_ids=[GROUP_MEMBER_USER_ID],
        )
        authenticate_client(self.client, GROUP_ADMIN_USER_ID)

        rotate_response = self.client.post(
            self.rotate_url(profile.room.id),
            {
                "reason": "security_incident",
            },
            format="json",
        )

        self.assertEqual(rotate_response.status_code, status.HTTP_200_OK)

        list_response = self.client.get(self.list_url(profile.room.id))

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        epochs = list_response.json()["data"]
        self.assertEqual(len(epochs), 2)
        self.assertEqual(epochs[0]["epoch_number"], 2)
        self.assertEqual(epochs[0]["status"], "active")
        self.assertEqual(epochs[1]["epoch_number"], 1)
        self.assertEqual(epochs[1]["status"], "closed")

    def test_owner_can_rotate_epoch(self):
        profile = create_group_room()
        authenticate_client(self.client, GROUP_OWNER_USER_ID)

        response = self.client.post(
            self.rotate_url(profile.room.id),
            {
                "reason": "security_incident",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["data"]["epoch_number"], 2)

        active_epochs = GroupEncryptionEpoch.objects.filter(
            group_room=profile.room,
            status=GroupEncryptionEpoch.Status.ACTIVE,
        )
        self.assertEqual(active_epochs.count(), 1)

        old_epoch = GroupEncryptionEpoch.objects.get(
            group_room=profile.room,
            epoch_number=1,
        )
        self.assertEqual(old_epoch.status, GroupEncryptionEpoch.Status.CLOSED)
        self.assertIsNotNone(old_epoch.closed_at)

    def test_admin_can_rotate_epoch(self):
        profile = create_group_room(
            admin_user_ids=[GROUP_ADMIN_USER_ID],
            member_user_ids=[GROUP_MEMBER_USER_ID],
        )
        authenticate_client(self.client, GROUP_ADMIN_USER_ID)

        response = self.client.post(
            self.rotate_url(profile.room.id),
            {
                "reason": "manual",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["data"]["epoch_number"], 2)

    def test_member_cannot_rotate_epoch(self):
        profile = create_group_room()
        authenticate_client(self.client, GROUP_MEMBER_USER_ID)

        response = self.client.post(
            self.rotate_url(profile.room.id),
            {
                "reason": "security_incident",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch("apps.group_chat.services.groups.validate_identity_user_ids")
    def test_group_create_api_creates_initial_epoch(self, validate_users):
        authenticate_client(self.client, GROUP_OWNER_USER_ID)

        response = self.client.post(
            reverse("group_chat:group-list-create"),
            {
                "name": "Backend Engineering",
                "description": "Myna backend team",
                "member_user_ids": [GROUP_MEMBER_USER_ID],
                "max_members": 100,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        room_id = response.json()["data"]["room_id"]

        epoch = GroupEncryptionEpoch.objects.get(
            group_room_id=room_id,
            status=GroupEncryptionEpoch.Status.ACTIVE,
        )
        self.assertEqual(epoch.epoch_number, 1)

    @patch("apps.group_chat.services.memberships.validate_identity_user_ids")
    def test_adding_member_rotates_epoch_and_changes_snapshot(
        self,
        validate_users,
    ):
        profile = create_group_room()
        old_epoch = GroupEncryptionEpoch.objects.get(
            group_room=profile.room,
            status=GroupEncryptionEpoch.Status.ACTIVE,
        )
        old_hash = old_epoch.membership_snapshot_hash

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

        old_epoch.refresh_from_db()
        self.assertEqual(old_epoch.status, GroupEncryptionEpoch.Status.CLOSED)

        new_epoch = GroupEncryptionEpoch.objects.get(
            group_room=profile.room,
            status=GroupEncryptionEpoch.Status.ACTIVE,
        )
        self.assertEqual(new_epoch.epoch_number, 2)
        self.assertEqual(
            new_epoch.rotation_reason,
            EPOCH_ROTATION_REASON_MEMBER_ADDED,
        )
        self.assertNotEqual(
            old_hash,
            new_epoch.membership_snapshot_hash,
        )

    def test_rotation_writes_audit_event(self):
        profile = create_group_room()
        authenticate_client(self.client, GROUP_OWNER_USER_ID)

        response = self.client.post(
            self.rotate_url(profile.room.id),
            {
                "reason": "security_incident",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        event = GroupAuditEvent.objects.get(
            event_type=GROUP_AUDIT_EPOCH_ROTATED,
            metadata__rotation_reason="security_incident",
        )
        self.assertEqual(event.actor_user_id, GROUP_OWNER_USER_ID)
        self.assertEqual(event.metadata["old_epoch_number"], 1)
        self.assertEqual(event.metadata["new_epoch_number"], 2)

    def test_direct_room_cannot_have_epoch(self):
        direct_room = Room.objects.create(
            room_type=Room.RoomType.DIRECT,
            created_by_user_id=GROUP_OWNER_USER_ID,
            direct_pair_key=(
                "22222222222222222222222222222222"
                "22222222222222222222222222222222"
            ),
            is_active=True,
        )

        epoch = GroupEncryptionEpoch(
            group_room=direct_room,
            epoch_number=1,
            status=GroupEncryptionEpoch.Status.ACTIVE,
            rotation_reason="initial",
            created_by_user_id=GROUP_OWNER_USER_ID,
            membership_snapshot_hash="a" * 64,
        )

        with self.assertRaises(ValidationError):
            epoch.full_clean()

    def test_one_active_epoch_constraint_is_enforced(self):
        profile = create_group_room()

        with self.assertRaises(IntegrityError):
            GroupEncryptionEpoch.objects.create(
                group_room=profile.room,
                epoch_number=99,
                status=GroupEncryptionEpoch.Status.ACTIVE,
                rotation_reason="manual",
                created_by_user_id=GROUP_OWNER_USER_ID,
                membership_snapshot_hash="b" * 64,
            )

    def test_closed_epoch_cannot_reactivate(self):
        profile = create_group_room()
        epoch = GroupEncryptionEpoch.objects.get(
            group_room=profile.room,
            status=GroupEncryptionEpoch.Status.ACTIVE,
        )

        epoch.status = GroupEncryptionEpoch.Status.CLOSED
        epoch.closed_at = timezone.now()
        epoch.full_clean()
        epoch.save()

        epoch.status = GroupEncryptionEpoch.Status.ACTIVE

        with self.assertRaises(ValidationError):
            epoch.full_clean()
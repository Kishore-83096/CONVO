from unittest.mock import patch

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.group_chat.constants import (
    GROUP_SECURITY_TRANSITION_REASON_MEMBER_ADDED,
    GROUP_SECURITY_TRANSITION_REASON_MEMBER_BANNED,
    GROUP_SECURITY_TRANSITION_REASON_MEMBER_LEFT,
    GROUP_SECURITY_TRANSITION_REASON_MEMBER_REMOVED,
)
from apps.group_chat.models import (
    GroupEncryptionEpoch,
    GroupSecurityTransition,
    GroupSenderKey,
)
from apps.group_chat.tests.factories import (
    GROUP_ADMIN_USER_ID,
    GROUP_MEMBER_USER_ID,
    GROUP_NEW_MEMBER_USER_ID,
    GROUP_OWNER_USER_ID,
    authenticate_client,
    create_group_room,
)
from apps.e2ee_devices.models import Device


def create_device(
    *,
    user_id: str,
) -> Device:
    return Device.objects.create(
        user_id=user_id,
        device_name="Web",
        platform=Device.Platform.WEB,
        registration_id=12345,
        identity_key_public="identity-public-key",
        signed_prekey_id=1,
        signed_prekey_public="signed-prekey-public",
        signed_prekey_signature="signed-prekey-signature",
        key_algorithm="curve25519",
        key_bundle_version=1,
        is_active=True,
    )


def create_sender_key(profile, user_id):
    device = create_device(user_id=user_id)
    epoch = GroupEncryptionEpoch.objects.get(
        group_room=profile.room,
        status=GroupEncryptionEpoch.Status.ACTIVE,
    )

    return GroupSenderKey.objects.create(
        group_room=profile.room,
        epoch=epoch,
        sender_user_id=user_id,
        sender_device=device,
        sender_key_id="11111111-1111-4111-8111-111111111111",
        signing_public_key="public-signing-key",
        key_algorithm="group-sender-key-v1",
        signing_algorithm="ed25519",
        key_version=1,
        highest_accepted_iteration=0,
        is_active=True,
    )


class MembershipEpochRotationTests(APITestCase):
    @patch("apps.group_chat.services.memberships.validate_identity_user_ids")
    def test_member_add_creates_transition_and_rotates_epoch(
        self,
        validate_users,
    ):
        profile = create_group_room()
        initial_epoch = GroupEncryptionEpoch.objects.get(
            group_room=profile.room,
            status=GroupEncryptionEpoch.Status.ACTIVE,
        )

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

        initial_epoch.refresh_from_db()
        self.assertEqual(initial_epoch.status, GroupEncryptionEpoch.Status.CLOSED)

        new_epoch = GroupEncryptionEpoch.objects.get(
            group_room=profile.room,
            status=GroupEncryptionEpoch.Status.ACTIVE,
        )
        self.assertEqual(new_epoch.epoch_number, 2)

        transition = GroupSecurityTransition.objects.get(
            group_room=profile.room,
            reason=GROUP_SECURITY_TRANSITION_REASON_MEMBER_ADDED,
        )
        self.assertEqual(transition.status, "applied")
        self.assertEqual(transition.old_epoch_number, 1)
        self.assertEqual(transition.new_epoch_number, 2)

    def test_member_remove_creates_transition_and_invalidates_old_sender_key(self):
        profile = create_group_room()
        sender_key = create_sender_key(profile, GROUP_MEMBER_USER_ID)

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

        sender_key.refresh_from_db()
        self.assertFalse(sender_key.is_active)
        self.assertIsNotNone(sender_key.revoked_at)

        transition = GroupSecurityTransition.objects.get(
            group_room=profile.room,
            reason=GROUP_SECURITY_TRANSITION_REASON_MEMBER_REMOVED,
        )
        self.assertEqual(transition.status, "applied")

    def test_member_leave_creates_transition(self):
        profile = create_group_room()

        authenticate_client(self.client, GROUP_MEMBER_USER_ID)

        response = self.client.post(
            reverse(
                "group_chat:group-leave",
                kwargs={"group_id": profile.room.id},
            ),
            {},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        transition = GroupSecurityTransition.objects.get(
            group_room=profile.room,
            reason=GROUP_SECURITY_TRANSITION_REASON_MEMBER_LEFT,
        )
        self.assertEqual(transition.status, "applied")
        self.assertEqual(transition.target_user_id, GROUP_MEMBER_USER_ID)

    def test_ban_creates_transition(self):
        profile = create_group_room(
            admin_user_ids=[GROUP_ADMIN_USER_ID],
            member_user_ids=[GROUP_MEMBER_USER_ID],
        )

        authenticate_client(self.client, GROUP_OWNER_USER_ID)

        response = self.client.post(
            reverse(
                "group_chat:group-member-ban",
                kwargs={
                    "group_id": profile.room.id,
                    "user_id": GROUP_MEMBER_USER_ID,
                },
            ),
            {},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        transition = GroupSecurityTransition.objects.get(
            group_room=profile.room,
            reason=GROUP_SECURITY_TRANSITION_REASON_MEMBER_BANNED,
        )
        self.assertEqual(transition.status, "applied")

    def test_manual_rotation_keeps_transition_free_path(self):
        profile = create_group_room()

        authenticate_client(self.client, GROUP_OWNER_USER_ID)

        response = self.client.post(
            reverse(
                "group_chat:group-epoch-rotate",
                kwargs={"group_id": profile.room.id},
            ),
            {
                "reason": "manual",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            GroupEncryptionEpoch.objects.filter(group_room=profile.room).count(),
            2,
        )
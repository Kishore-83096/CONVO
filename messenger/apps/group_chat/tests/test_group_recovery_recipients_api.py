from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.utils import timezone
from apps.e2ee_devices.models import RecoveryBundle
from apps.group_chat.tests.factories import (
    GROUP_MEMBER_USER_ID,
    GROUP_NEW_MEMBER_USER_ID,
    GROUP_OUTSIDER_USER_ID,
    GROUP_OWNER_USER_ID,
    authenticate_client,
    create_group_room,
)
from apps.rooms.models import RoomMember

def create_recovery_bundle(
    *,
    user_id: str,
    recovery_version: int = 1,
    is_active: bool = True,
) -> RecoveryBundle:
    return RecoveryBundle.objects.create(
        user_id=user_id,
        recovery_public_key=f"recovery-public-{user_id}",
        encrypted_recovery_private_key=f"encrypted-private-{user_id}",
        encryption_metadata={
            "algorithm": "recovery-box-v1",
        },
        recovery_version=recovery_version,
        is_active=is_active,
        disabled_at=None if is_active else timezone.now(),
    )

    

class GroupRecoveryRecipientsAPITests(APITestCase):
    def url(self, group_id):
        return reverse(
            "group_chat:group-recovery-recipients",
            kwargs={"group_id": group_id},
        )

    def test_authentication_is_required(self):
        profile = create_group_room()

        response = self.client.get(
            self.url(profile.room.id),
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_active_member_can_fetch_recovery_recipients(self):
        profile = create_group_room(
            member_user_ids=[
                GROUP_MEMBER_USER_ID,
                GROUP_NEW_MEMBER_USER_ID,
            ],
        )

        create_recovery_bundle(
            user_id=GROUP_OWNER_USER_ID,
            recovery_version=2,
        )
        create_recovery_bundle(
            user_id=GROUP_MEMBER_USER_ID,
            recovery_version=1,
        )

        authenticate_client(self.client, GROUP_MEMBER_USER_ID)

        response = self.client.get(
            self.url(profile.room.id),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()["data"]
        self.assertEqual(data["group_id"], str(profile.room.id))
        self.assertEqual(data["epoch_number"], 1)

        recipients = data["recipients"]
        self.assertEqual(len(recipients), 2)

        user_ids = {
            item["user_id"]
            for item in recipients
        }

        self.assertEqual(
            user_ids,
            {
                GROUP_OWNER_USER_ID,
                GROUP_MEMBER_USER_ID,
            },
        )

        first = recipients[0]
        self.assertIn("recovery_public_key", first)
        self.assertIn("recovery_version", first)
        self.assertNotIn("encrypted_recovery_private_key", first)

    def test_users_without_recovery_are_omitted(self):
        profile = create_group_room(
            member_user_ids=[
                GROUP_MEMBER_USER_ID,
                GROUP_NEW_MEMBER_USER_ID,
            ],
        )

        create_recovery_bundle(
            user_id=GROUP_OWNER_USER_ID,
        )

        authenticate_client(self.client, GROUP_MEMBER_USER_ID)

        response = self.client.get(
            self.url(profile.room.id),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        recipients = response.json()["data"]["recipients"]

        self.assertEqual(len(recipients), 1)
        self.assertEqual(
            recipients[0]["user_id"],
            GROUP_OWNER_USER_ID,
        )

    def test_inactive_recovery_bundle_is_omitted(self):
        profile = create_group_room(
            member_user_ids=[GROUP_MEMBER_USER_ID],
        )

        create_recovery_bundle(
            user_id=GROUP_OWNER_USER_ID,
            is_active=False,
        )
        create_recovery_bundle(
            user_id=GROUP_MEMBER_USER_ID,
            is_active=True,
        )

        authenticate_client(self.client, GROUP_MEMBER_USER_ID)

        response = self.client.get(
            self.url(profile.room.id),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        recipients = response.json()["data"]["recipients"]
        self.assertEqual(len(recipients), 1)
        self.assertEqual(
            recipients[0]["user_id"],
            GROUP_MEMBER_USER_ID,
        )

    def test_removed_member_is_excluded(self):
        profile = create_group_room(
            member_user_ids=[
                GROUP_MEMBER_USER_ID,
                GROUP_NEW_MEMBER_USER_ID,
            ],
        )

        create_recovery_bundle(user_id=GROUP_OWNER_USER_ID)
        create_recovery_bundle(user_id=GROUP_MEMBER_USER_ID)
        create_recovery_bundle(user_id=GROUP_NEW_MEMBER_USER_ID)

        removed_member = RoomMember.objects.get(
            room=profile.room,
            user_id=GROUP_NEW_MEMBER_USER_ID,
        )
        removed_member.is_active = False
        removed_member.removed_by_user_id = GROUP_OWNER_USER_ID
        removed_member.save(
            update_fields=[
                "is_active",
                "removed_by_user_id",
            ]
        )

        authenticate_client(self.client, GROUP_MEMBER_USER_ID)

        response = self.client.get(
            self.url(profile.room.id),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        user_ids = {
            item["user_id"]
            for item in response.json()["data"]["recipients"]
        }

        self.assertNotIn(GROUP_NEW_MEMBER_USER_ID, user_ids)

    def test_non_member_cannot_fetch_recipients(self):
        profile = create_group_room(
            member_user_ids=[GROUP_MEMBER_USER_ID],
        )

        authenticate_client(self.client, GROUP_OUTSIDER_USER_ID)

        response = self.client.get(
            self.url(profile.room.id),
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
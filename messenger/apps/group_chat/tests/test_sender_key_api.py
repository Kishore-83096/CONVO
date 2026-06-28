import uuid

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.e2ee_devices.models import Device
from apps.group_chat.constants import (
    GROUP_AUDIT_SENDER_KEY_REGISTERED,
    GROUP_AUDIT_SENDER_KEY_REVOKED,
)
from apps.group_chat.models import (
    GroupAuditEvent,
    GroupEncryptionEpoch,
    GroupSenderKey,
)
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


def create_device(
    *,
    user_id: str,
    is_active: bool = True,
    device_name: str = "Web",
) -> Device:
    return Device.objects.create(
        user_id=user_id,
        device_name=device_name,
        platform=Device.Platform.WEB,
        registration_id=12345,
        identity_key_public=f"identity-public-{uuid.uuid4()}",
        signed_prekey_id=1,
        signed_prekey_public=f"signed-prekey-public-{uuid.uuid4()}",
        signed_prekey_signature=f"signature-{uuid.uuid4()}",
        key_algorithm="curve25519",
        key_bundle_version=1,
        is_active=is_active,
    )


def sender_key_payload(
    *,
    device: Device,
    epoch_number: int = 1,
    sender_key_id=None,
    signing_public_key: str = "sender-signing-public-key",
):
    return {
        "sender_device_id": str(device.id),
        "epoch_number": epoch_number,
        "sender_key_id": str(sender_key_id or uuid.uuid4()),
        "signing_public_key": signing_public_key,
        "key_algorithm": "group-sender-key-v1",
        "signing_algorithm": "ed25519",
        "key_version": 1,
    }


class GroupSenderKeyAPITests(APITestCase):
    def register_url(self, group_id):
        return reverse(
            "group_chat:group-sender-key-register",
            kwargs={"group_id": group_id},
        )

    def mine_url(self, group_id):
        return reverse(
            "group_chat:group-sender-key-mine",
            kwargs={"group_id": group_id},
        )

    def revoke_url(self, group_id, sender_key_id):
        return reverse(
            "group_chat:group-sender-key-revoke",
            kwargs={
                "group_id": group_id,
                "sender_key_id": sender_key_id,
            },
        )

    def test_authentication_is_required(self):
        profile = create_group_room()
        device = create_device(user_id=GROUP_MEMBER_USER_ID)

        response = self.client.post(
            self.register_url(profile.room.id),
            sender_key_payload(device=device),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_active_member_device_can_register_sender_key(self):
        profile = create_group_room()
        device = create_device(user_id=GROUP_MEMBER_USER_ID)
        authenticate_client(self.client, GROUP_MEMBER_USER_ID)

        response = self.client.post(
            self.register_url(profile.room.id),
            sender_key_payload(device=device),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        data = response.json()["data"]
        self.assertEqual(data["sender_user_id"], GROUP_MEMBER_USER_ID)
        self.assertEqual(data["sender_device_id"], str(device.id))
        self.assertEqual(data["epoch_number"], 1)
        self.assertTrue(data["is_active"])

        self.assertEqual(GroupSenderKey.objects.count(), 1)

    def test_non_member_cannot_register_sender_key(self):
        profile = create_group_room()
        device = create_device(user_id=GROUP_OUTSIDER_USER_ID)
        authenticate_client(self.client, GROUP_OUTSIDER_USER_ID)

        response = self.client.post(
            self.register_url(profile.room.id),
            sender_key_payload(device=device),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_device_must_belong_to_authenticated_user(self):
        profile = create_group_room()
        device = create_device(user_id=GROUP_OWNER_USER_ID)
        authenticate_client(self.client, GROUP_MEMBER_USER_ID)

        response = self.client.post(
            self.register_url(profile.room.id),
            sender_key_payload(device=device),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_inactive_device_cannot_register_sender_key(self):
        profile = create_group_room()
        device = create_device(
            user_id=GROUP_MEMBER_USER_ID,
            is_active=False,
        )
        authenticate_client(self.client, GROUP_MEMBER_USER_ID)

        response = self.client.post(
            self.register_url(profile.room.id),
            sender_key_payload(device=device),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_sender_key_must_target_current_active_epoch(self):
        profile = create_group_room()
        device = create_device(user_id=GROUP_OWNER_USER_ID)
        authenticate_client(self.client, GROUP_OWNER_USER_ID)

        rotate_response = self.client.post(
            reverse(
                "group_chat:group-epoch-rotate",
                kwargs={"group_id": profile.room.id},
            ),
            {
                "reason": "manual",
            },
            format="json",
        )
        self.assertEqual(rotate_response.status_code, status.HTTP_200_OK)

        response = self.client.post(
            self.register_url(profile.room.id),
            sender_key_payload(
                device=device,
                epoch_number=1,
            ),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_exact_retry_returns_existing_registration(self):
        profile = create_group_room()
        device = create_device(user_id=GROUP_MEMBER_USER_ID)
        sender_key_id = uuid.uuid4()
        payload = sender_key_payload(
            device=device,
            sender_key_id=sender_key_id,
        )

        authenticate_client(self.client, GROUP_MEMBER_USER_ID)

        first_response = self.client.post(
            self.register_url(profile.room.id),
            payload,
            format="json",
        )
        second_response = self.client.post(
            self.register_url(profile.room.id),
            payload,
            format="json",
        )

        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second_response.status_code, status.HTTP_200_OK)
        self.assertEqual(GroupSenderKey.objects.count(), 1)

    def test_changed_retry_returns_conflict(self):
        profile = create_group_room()
        device = create_device(user_id=GROUP_MEMBER_USER_ID)
        sender_key_id = uuid.uuid4()
        first_payload = sender_key_payload(
            device=device,
            sender_key_id=sender_key_id,
            signing_public_key="original-public-key",
        )
        changed_payload = sender_key_payload(
            device=device,
            sender_key_id=sender_key_id,
            signing_public_key="changed-public-key",
        )

        authenticate_client(self.client, GROUP_MEMBER_USER_ID)

        first_response = self.client.post(
            self.register_url(profile.room.id),
            first_payload,
            format="json",
        )
        changed_response = self.client.post(
            self.register_url(profile.room.id),
            changed_payload,
            format="json",
        )

        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(changed_response.status_code, status.HTTP_409_CONFLICT)

    def test_one_active_key_per_device_per_epoch(self):
        profile = create_group_room()
        device = create_device(user_id=GROUP_MEMBER_USER_ID)

        authenticate_client(self.client, GROUP_MEMBER_USER_ID)

        first_response = self.client.post(
            self.register_url(profile.room.id),
            sender_key_payload(
                device=device,
                signing_public_key="first-public-key",
            ),
            format="json",
        )
        second_response = self.client.post(
            self.register_url(profile.room.id),
            sender_key_payload(
                device=device,
                signing_public_key="second-public-key",
            ),
            format="json",
        )

        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second_response.status_code, status.HTTP_409_CONFLICT)

    def test_multi_device_user_can_register_one_key_per_device(self):
        profile = create_group_room()
        first_device = create_device(
            user_id=GROUP_MEMBER_USER_ID,
            device_name="Phone",
        )
        second_device = create_device(
            user_id=GROUP_MEMBER_USER_ID,
            device_name="Browser",
        )

        authenticate_client(self.client, GROUP_MEMBER_USER_ID)

        first_response = self.client.post(
            self.register_url(profile.room.id),
            sender_key_payload(
                device=first_device,
                signing_public_key="phone-public-key",
            ),
            format="json",
        )
        second_response = self.client.post(
            self.register_url(profile.room.id),
            sender_key_payload(
                device=second_device,
                signing_public_key="browser-public-key",
            ),
            format="json",
        )

        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(GroupSenderKey.objects.count(), 2)

    def test_mine_returns_registered_sender_key(self):
        profile = create_group_room()
        device = create_device(user_id=GROUP_MEMBER_USER_ID)

        authenticate_client(self.client, GROUP_MEMBER_USER_ID)

        register_response = self.client.post(
            self.register_url(profile.room.id),
            sender_key_payload(device=device),
            format="json",
        )
        self.assertEqual(register_response.status_code, status.HTTP_201_CREATED)

        response = self.client.get(
            self.mine_url(profile.room.id),
            {
                "device_id": str(device.id),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(response.json()["data"])
        self.assertEqual(
            response.json()["data"]["sender_device_id"],
            str(device.id),
        )

    def test_mine_returns_null_when_not_registered(self):
        profile = create_group_room()
        device = create_device(user_id=GROUP_MEMBER_USER_ID)

        authenticate_client(self.client, GROUP_MEMBER_USER_ID)

        response = self.client.get(
            self.mine_url(profile.room.id),
            {
                "device_id": str(device.id),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.json()["data"])

    def test_sender_owner_can_revoke_sender_key(self):
        profile = create_group_room()
        device = create_device(user_id=GROUP_MEMBER_USER_ID)

        authenticate_client(self.client, GROUP_MEMBER_USER_ID)

        register_response = self.client.post(
            self.register_url(profile.room.id),
            sender_key_payload(device=device),
            format="json",
        )
        sender_key_id = register_response.json()["data"]["sender_key_id"]

        revoke_response = self.client.delete(
            self.revoke_url(profile.room.id, sender_key_id)
        )

        self.assertEqual(revoke_response.status_code, status.HTTP_200_OK)

        sender_key = GroupSenderKey.objects.get(
            sender_key_id=sender_key_id,
        )
        self.assertFalse(sender_key.is_active)
        self.assertIsNotNone(sender_key.revoked_at)

    def test_group_admin_can_revoke_another_sender_key(self):
        profile = create_group_room(
            admin_user_ids=[GROUP_ADMIN_USER_ID],
            member_user_ids=[GROUP_MEMBER_USER_ID],
        )
        device = create_device(user_id=GROUP_MEMBER_USER_ID)

        authenticate_client(self.client, GROUP_MEMBER_USER_ID)
        register_response = self.client.post(
            self.register_url(profile.room.id),
            sender_key_payload(device=device),
            format="json",
        )
        sender_key_id = register_response.json()["data"]["sender_key_id"]

        authenticate_client(self.client, GROUP_ADMIN_USER_ID)
        revoke_response = self.client.delete(
            self.revoke_url(profile.room.id, sender_key_id)
        )

        self.assertEqual(revoke_response.status_code, status.HTTP_200_OK)

    def test_normal_member_cannot_revoke_another_sender_key(self):
        profile = create_group_room(
            member_user_ids=[
                GROUP_MEMBER_USER_ID,
                GROUP_NEW_MEMBER_USER_ID,
            ],
        )
        owner_device = create_device(user_id=GROUP_OWNER_USER_ID)

        authenticate_client(self.client, GROUP_OWNER_USER_ID)
        register_response = self.client.post(
            self.register_url(profile.room.id),
            sender_key_payload(device=owner_device),
            format="json",
        )
        sender_key_id = register_response.json()["data"]["sender_key_id"]

        authenticate_client(self.client, GROUP_MEMBER_USER_ID)
        revoke_response = self.client.delete(
            self.revoke_url(profile.room.id, sender_key_id)
        )

        self.assertEqual(revoke_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_epoch_rotation_revokes_old_sender_keys(self):
        profile = create_group_room()
        device = create_device(user_id=GROUP_MEMBER_USER_ID)

        authenticate_client(self.client, GROUP_MEMBER_USER_ID)
        register_response = self.client.post(
            self.register_url(profile.room.id),
            sender_key_payload(device=device),
            format="json",
        )
        self.assertEqual(register_response.status_code, status.HTTP_201_CREATED)

        authenticate_client(self.client, GROUP_OWNER_USER_ID)
        rotate_response = self.client.post(
            reverse(
                "group_chat:group-epoch-rotate",
                kwargs={"group_id": profile.room.id},
            ),
            {
                "reason": "manual",
            },
            format="json",
        )

        self.assertEqual(rotate_response.status_code, status.HTTP_200_OK)

        sender_key = GroupSenderKey.objects.get(
            sender_key_id=register_response.json()["data"]["sender_key_id"],
        )
        self.assertFalse(sender_key.is_active)
        self.assertIsNotNone(sender_key.revoked_at)

    def test_sender_key_register_writes_audit_event(self):
        profile = create_group_room()
        device = create_device(user_id=GROUP_MEMBER_USER_ID)

        authenticate_client(self.client, GROUP_MEMBER_USER_ID)

        response = self.client.post(
            self.register_url(profile.room.id),
            sender_key_payload(device=device),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        event = GroupAuditEvent.objects.get(
            event_type=GROUP_AUDIT_SENDER_KEY_REGISTERED,
        )
        self.assertEqual(event.actor_user_id, GROUP_MEMBER_USER_ID)
        self.assertEqual(event.metadata["epoch_number"], 1)

    def test_sender_key_revoke_writes_audit_event(self):
        profile = create_group_room()
        device = create_device(user_id=GROUP_MEMBER_USER_ID)

        authenticate_client(self.client, GROUP_MEMBER_USER_ID)

        register_response = self.client.post(
            self.register_url(profile.room.id),
            sender_key_payload(device=device),
            format="json",
        )
        sender_key_id = register_response.json()["data"]["sender_key_id"]

        response = self.client.delete(
            self.revoke_url(profile.room.id, sender_key_id)
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        event = GroupAuditEvent.objects.get(
            event_type=GROUP_AUDIT_SENDER_KEY_REVOKED,
        )
        self.assertEqual(event.actor_user_id, GROUP_MEMBER_USER_ID)
        self.assertEqual(event.metadata["epoch_number"], 1)

    def test_direct_room_cannot_have_sender_key(self):
        direct_room = Room.objects.create(
            room_type=Room.RoomType.DIRECT,
            created_by_user_id=GROUP_OWNER_USER_ID,
            direct_pair_key=(
                "33333333333333333333333333333333"
                "33333333333333333333333333333333"
            ),
            is_active=True,
        )
        device = create_device(user_id=GROUP_OWNER_USER_ID)
        epoch = GroupEncryptionEpoch.objects.create(
            group_room=create_group_room().room,
            epoch_number=99,
            status=GroupEncryptionEpoch.Status.CLOSED,
            rotation_reason="manual",
            created_by_user_id=GROUP_OWNER_USER_ID,
            membership_snapshot_hash="a" * 64,
            closed_at="2026-01-01T00:00:00Z",
        )

        sender_key = GroupSenderKey(
            group_room=direct_room,
            epoch=epoch,
            sender_user_id=GROUP_OWNER_USER_ID,
            sender_device=device,
            sender_key_id=uuid.uuid4(),
            signing_public_key="public-key",
            key_algorithm="group-sender-key-v1",
            signing_algorithm="ed25519",
            key_version=1,
        )

        with self.assertRaises(ValidationError):
            sender_key.full_clean()

    def test_database_unique_sender_key_id_constraint(self):
        profile = create_group_room()
        epoch = GroupEncryptionEpoch.objects.get(
            group_room=profile.room,
            status=GroupEncryptionEpoch.Status.ACTIVE,
        )
        first_device = create_device(user_id=GROUP_OWNER_USER_ID)
        second_device = create_device(user_id=GROUP_OWNER_USER_ID)
        sender_key_id = uuid.uuid4()

        GroupSenderKey.objects.create(
            group_room=profile.room,
            epoch=epoch,
            sender_user_id=GROUP_OWNER_USER_ID,
            sender_device=first_device,
            sender_key_id=sender_key_id,
            signing_public_key="first-public-key",
            key_algorithm="group-sender-key-v1",
            signing_algorithm="ed25519",
            key_version=1,
        )

        with self.assertRaises(IntegrityError):
            GroupSenderKey.objects.create(
                group_room=profile.room,
                epoch=epoch,
                sender_user_id=GROUP_OWNER_USER_ID,
                sender_device=second_device,
                sender_key_id=sender_key_id,
                signing_public_key="second-public-key",
                key_algorithm="group-sender-key-v1",
                signing_algorithm="ed25519",
                key_version=1,
            )

    def test_model_has_no_secret_sender_key_fields(self):
        field_names = {
            field.name
            for field in GroupSenderKey._meta.fields
        }

        forbidden = {
            "sender_chain_secret",
            "signing_private_key",
            "private_key",
            "message_key",
            "plaintext",
            "ratchet_state",
            "recovery_key",
        }

        self.assertTrue(field_names.isdisjoint(forbidden))
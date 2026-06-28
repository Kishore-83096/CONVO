import uuid

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.chat_messages.models import GroupMessageEncryption, Message
from apps.e2ee_devices.models import Device
from apps.group_chat.models import (
    GroupEncryptionEpoch,
    GroupSenderKey,
    GroupSenderKeyDistribution,
)
from apps.group_chat.tests.factories import (
    GROUP_ADMIN_USER_ID,
    GROUP_MEMBER_USER_ID,
    GROUP_NEW_MEMBER_USER_ID,
    GROUP_OUTSIDER_USER_ID,
    GROUP_OWNER_USER_ID,
    authenticate_client,
    create_group_room,
)
from apps.rooms.models import Room, RoomMember


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


def create_sender_key(
    *,
    profile,
    sender_user_id: str,
    sender_device: Device,
) -> GroupSenderKey:
    epoch = GroupEncryptionEpoch.objects.get(
        group_room=profile.room,
        status=GroupEncryptionEpoch.Status.ACTIVE,
    )

    return GroupSenderKey.objects.create(
        group_room=profile.room,
        epoch=epoch,
        sender_user_id=sender_user_id,
        sender_device=sender_device,
        sender_key_id=uuid.uuid4(),
        signing_public_key=f"signing-public-{uuid.uuid4()}",
        key_algorithm="group-sender-key-v1",
        signing_algorithm="ed25519",
        key_version=1,
        highest_accepted_iteration=0,
        is_active=True,
    )


def distribute_sender_key_to_device(
    *,
    sender_key: GroupSenderKey,
    recipient_device: Device,
):
    return GroupSenderKeyDistribution.objects.create(
        sender_key=sender_key,
        recipient_user_id=recipient_device.user_id,
        recipient_device=recipient_device,
        encrypted_sender_key=f"encrypted-sender-key-{uuid.uuid4()}",
        distribution_metadata={
            "algorithm": "double-ratchet",
            "session_reference": f"session-{recipient_device.id}",
            "message_number": 1,
            "nonce": "base64-nonce",
        },
        distribution_version=1,
        status="stored",
    )


def group_message_payload(
    *,
    profile,
    sender_device: Device,
    sender_key: GroupSenderKey,
    client_message_id=None,
    chain_iteration: int = 1,
    encrypted_payload: str = "base64-group-ciphertext",
    reply_to_message_id=None,
):
    return {
        "group_id": str(profile.room.id),
        "sender_device_id": str(sender_device.id),
        "client_message_id": str(client_message_id or uuid.uuid4()),
        "epoch_number": sender_key.epoch.epoch_number,
        "sender_key_id": str(sender_key.sender_key_id),
        "chain_iteration": chain_iteration,
        "message_type": "text",
        "encrypted_payload": encrypted_payload,
        "encryption_metadata": {
            "algorithm": "group-sender-key-v1",
            "nonce": "base64-nonce",
            "content_encoding": "myna-message-v1",
        },
        "signature": "base64-signature",
        "reply_to_message_id": (
            str(reply_to_message_id)
            if reply_to_message_id is not None
            else None
        ),
        "client_sent_at": "2026-06-27T00:00:00Z",
    }


class GroupMessageSendingAPITests(APITestCase):
    def send_url(self):
        return reverse("chat_messages:group-message-send")

    def _ready_sender_setup(
        self,
        *,
        only_admins_can_send: bool = False,
        sender_user_id: str = GROUP_MEMBER_USER_ID,
        include_admin: bool = False,
    ):
        admin_user_ids = [GROUP_ADMIN_USER_ID] if include_admin else []

        profile = create_group_room(
            admin_user_ids=admin_user_ids,
            member_user_ids=[
                GROUP_MEMBER_USER_ID,
                GROUP_NEW_MEMBER_USER_ID,
            ],
            only_admins_can_edit_info=True,
        )
        profile.only_admins_can_send = only_admins_can_send
        profile.save(update_fields=["only_admins_can_send"])

        owner_device = create_device(user_id=GROUP_OWNER_USER_ID)
        member_device = create_device(user_id=GROUP_MEMBER_USER_ID)
        second_member_device = create_device(user_id=GROUP_NEW_MEMBER_USER_ID)

        sender_device = (
            owner_device
            if sender_user_id == GROUP_OWNER_USER_ID
            else member_device
        )

        sender_key = create_sender_key(
            profile=profile,
            sender_user_id=sender_user_id,
            sender_device=sender_device,
        )

        for device in [
            owner_device,
            member_device,
            second_member_device,
        ]:
            if device.id == sender_device.id:
                continue

            distribute_sender_key_to_device(
                sender_key=sender_key,
                recipient_device=device,
            )

        return profile, sender_device, sender_key

    def test_authentication_is_required(self):
        profile, sender_device, sender_key = self._ready_sender_setup()

        response = self.client.post(
            self.send_url(),
            group_message_payload(
                profile=profile,
                sender_device=sender_device,
                sender_key=sender_key,
            ),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_active_member_can_send_group_message(self):
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

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        data = response.json()["data"]
        self.assertTrue(data["message_created"])
        self.assertEqual(data["message"]["room_id"], str(profile.room.id))
        self.assertEqual(
            data["message"]["sender_key_id"],
            str(sender_key.sender_key_id),
        )
        self.assertEqual(data["message"]["chain_iteration"], 1)

        self.assertEqual(Message.objects.count(), 1)
        self.assertEqual(GroupMessageEncryption.objects.count(), 1)

        sender_key.refresh_from_db()
        self.assertEqual(sender_key.highest_accepted_iteration, 1)

    def test_non_member_cannot_send(self):
        profile, sender_device, sender_key = self._ready_sender_setup()
        outsider_device = create_device(user_id=GROUP_OUTSIDER_USER_ID)

        authenticate_client(self.client, GROUP_OUTSIDER_USER_ID)

        response = self.client.post(
            self.send_url(),
            group_message_payload(
                profile=profile,
                sender_device=outsider_device,
                sender_key=sender_key,
            ),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_admin_only_send_blocks_normal_member(self):
        profile, sender_device, sender_key = self._ready_sender_setup(
            only_admins_can_send=True,
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

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_only_send_allows_owner(self):
        profile, sender_device, sender_key = self._ready_sender_setup(
            only_admins_can_send=True,
            sender_user_id=GROUP_OWNER_USER_ID,
        )
        authenticate_client(self.client, GROUP_OWNER_USER_ID)

        response = self.client.post(
            self.send_url(),
            group_message_payload(
                profile=profile,
                sender_device=sender_device,
                sender_key=sender_key,
            ),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_sender_device_must_belong_to_authenticated_user(self):
        profile, sender_device, sender_key = self._ready_sender_setup()
        authenticate_client(self.client, GROUP_OWNER_USER_ID)

        response = self.client.post(
            self.send_url(),
            group_message_payload(
                profile=profile,
                sender_device=sender_device,
                sender_key=sender_key,
            ),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_inactive_device_cannot_send(self):
        profile, sender_device, sender_key = self._ready_sender_setup()
        sender_device.is_active = False
        sender_device.save(update_fields=["is_active"])

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

    def test_stale_epoch_is_rejected(self):
        profile, sender_device, sender_key = self._ready_sender_setup()

        sender_key.epoch.status = GroupEncryptionEpoch.Status.CLOSED
        sender_key.epoch.closed_at = "2026-01-01T00:00:00Z"
        sender_key.epoch.save(
            update_fields=[
                "status",
                "closed_at",
                "active_epoch_key",
            ]
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

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_inactive_sender_key_is_rejected(self):
        profile, sender_device, sender_key = self._ready_sender_setup()
        sender_key.is_active = False
        sender_key.revoked_at = "2026-01-01T00:00:00Z"
        sender_key.save(
            update_fields=[
                "is_active",
                "revoked_at",
                "active_sender_device_epoch_key",
            ]
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

    def test_complete_distribution_coverage_is_required(self):
        profile, sender_device, sender_key = self._ready_sender_setup()

        GroupSenderKeyDistribution.objects.filter(
            sender_key=sender_key,
        ).delete()

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

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_exact_retry_returns_existing_message(self):
        profile, sender_device, sender_key = self._ready_sender_setup()
        client_message_id = uuid.uuid4()
        payload = group_message_payload(
            profile=profile,
            sender_device=sender_device,
            sender_key=sender_key,
            client_message_id=client_message_id,
            chain_iteration=1,
        )

        authenticate_client(self.client, GROUP_MEMBER_USER_ID)

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
        self.assertFalse(second_response.json()["data"]["message_created"])
        self.assertEqual(Message.objects.count(), 1)
        self.assertEqual(GroupMessageEncryption.objects.count(), 1)

    def test_changed_retry_returns_conflict(self):
        profile, sender_device, sender_key = self._ready_sender_setup()
        client_message_id = uuid.uuid4()

        first_payload = group_message_payload(
            profile=profile,
            sender_device=sender_device,
            sender_key=sender_key,
            client_message_id=client_message_id,
            encrypted_payload="ciphertext-one",
        )
        changed_payload = group_message_payload(
            profile=profile,
            sender_device=sender_device,
            sender_key=sender_key,
            client_message_id=client_message_id,
            encrypted_payload="ciphertext-two",
        )

        authenticate_client(self.client, GROUP_MEMBER_USER_ID)

        first_response = self.client.post(
            self.send_url(),
            first_payload,
            format="json",
        )
        changed_response = self.client.post(
            self.send_url(),
            changed_payload,
            format="json",
        )

        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(changed_response.status_code, status.HTTP_409_CONFLICT)

    def test_chain_iteration_must_increase(self):
        profile, sender_device, sender_key = self._ready_sender_setup()

        authenticate_client(self.client, GROUP_MEMBER_USER_ID)

        first_response = self.client.post(
            self.send_url(),
            group_message_payload(
                profile=profile,
                sender_device=sender_device,
                sender_key=sender_key,
                chain_iteration=1,
            ),
            format="json",
        )
        replay_response = self.client.post(
            self.send_url(),
            group_message_payload(
                profile=profile,
                sender_device=sender_device,
                sender_key=sender_key,
                chain_iteration=1,
            ),
            format="json",
        )

        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(replay_response.status_code, status.HTTP_409_CONFLICT)

    def test_reply_target_must_be_same_group(self):
        profile, sender_device, sender_key = self._ready_sender_setup()

        other_profile = create_group_room(
            owner_user_id="98",
            member_user_ids=["99"],
            name="Other Group",
        )

        other_message = Message.objects.create(
            room=other_profile.room,
            sender_user_id="98",
            sender_device_id=str(uuid.uuid4()),
            client_message_id=uuid.uuid4(),
            message_type="text",
            encrypted_payload="other-ciphertext",
            encryption_metadata={
                "algorithm": "group-sender-key-v1",
            },
            encryption_version=1,
        )

        authenticate_client(self.client, GROUP_MEMBER_USER_ID)

        response = self.client.post(
            self.send_url(),
            group_message_payload(
                profile=profile,
                sender_device=sender_device,
                sender_key=sender_key,
                reply_to_message_id=other_message.id,
            ),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_valid_same_group_reply_is_allowed(self):
        profile, sender_device, sender_key = self._ready_sender_setup()

        authenticate_client(self.client, GROUP_MEMBER_USER_ID)

        first_response = self.client.post(
            self.send_url(),
            group_message_payload(
                profile=profile,
                sender_device=sender_device,
                sender_key=sender_key,
                chain_iteration=1,
            ),
            format="json",
        )

        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)

        reply_to_id = first_response.json()["data"]["message"]["message_id"]

        second_response = self.client.post(
            self.send_url(),
            group_message_payload(
                profile=profile,
                sender_device=sender_device,
                sender_key=sender_key,
                chain_iteration=2,
                reply_to_message_id=reply_to_id,
            ),
            format="json",
        )

        self.assertEqual(second_response.status_code, status.HTTP_201_CREATED)

    def test_group_message_does_not_create_message_key_envelopes(self):
        from apps.chat_messages.models import MessageKeyEnvelope

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

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(MessageKeyEnvelope.objects.count(), 0)

    def test_group_message_model_has_no_secret_fields(self):
        field_names = {
            field.name
            for field in GroupMessageEncryption._meta.fields
        }

        forbidden = {
            "plaintext",
            "private_key",
            "sender_chain_secret",
            "message_key",
            "ratchet_state",
            "recovery_key",
        }

        self.assertTrue(field_names.isdisjoint(forbidden))

    def test_group_encryption_rejects_direct_room(self):
        direct_room = Room.objects.create(
            room_type=Room.RoomType.DIRECT,
            created_by_user_id=GROUP_OWNER_USER_ID,
            direct_pair_key=(
                "44444444444444444444444444444444"
                "44444444444444444444444444444444"
            ),
            is_active=True,
        )

        profile, sender_device, sender_key = self._ready_sender_setup()

        direct_message = Message.objects.create(
            room=direct_room,
            sender_user_id=GROUP_MEMBER_USER_ID,
            sender_device_id=str(sender_device.id),
            client_message_id=uuid.uuid4(),
            message_type="text",
            encrypted_payload="ciphertext",
            encryption_metadata={
                "algorithm": "group-sender-key-v1",
            },
            encryption_version=1,
        )

        group_encryption = GroupMessageEncryption(
            message=direct_message,
            group_room=direct_room,
            epoch=sender_key.epoch,
            sender_key=sender_key,
            chain_iteration=1,
            signature="signature",
            encryption_metadata={
                "algorithm": "group-sender-key-v1",
            },
        )

        with self.assertRaises(ValidationError):
            group_encryption.full_clean()

    def test_database_unique_sender_key_iteration_constraint(self):
        profile, sender_device, sender_key = self._ready_sender_setup()

        first_message = Message.objects.create(
            room=profile.room,
            sender_user_id=GROUP_MEMBER_USER_ID,
            sender_device_id=str(sender_device.id),
            client_message_id=uuid.uuid4(),
            message_type="text",
            encrypted_payload="ciphertext-one",
            encryption_metadata={
                "algorithm": "group-sender-key-v1",
            },
            encryption_version=1,
        )

        second_message = Message.objects.create(
            room=profile.room,
            sender_user_id=GROUP_MEMBER_USER_ID,
            sender_device_id=str(sender_device.id),
            client_message_id=uuid.uuid4(),
            message_type="text",
            encrypted_payload="ciphertext-two",
            encryption_metadata={
                "algorithm": "group-sender-key-v1",
            },
            encryption_version=1,
        )

        GroupMessageEncryption.objects.create(
            message=first_message,
            group_room=profile.room,
            epoch=sender_key.epoch,
            sender_key=sender_key,
            chain_iteration=1,
            signature="signature-one",
            encryption_metadata={
                "algorithm": "group-sender-key-v1",
            },
        )

        with self.assertRaises(IntegrityError):
            GroupMessageEncryption.objects.create(
                message=second_message,
                group_room=profile.room,
                epoch=sender_key.epoch,
                sender_key=sender_key,
                chain_iteration=1,
                signature="signature-two",
                encryption_metadata={
                    "algorithm": "group-sender-key-v1",
                },
            )
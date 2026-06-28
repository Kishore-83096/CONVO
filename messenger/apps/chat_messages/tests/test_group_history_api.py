import uuid
from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.chat_messages.models import (
    GroupMessageEncryption,
    Message,
    MessageKeyEnvelope,
)
from apps.e2ee_devices.models import Device
from apps.group_chat.models import (
    GroupEncryptionEpoch,
    GroupSenderKey,
    GroupSenderKeyDistribution,
)
from apps.group_chat.tests.factories import (
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


def create_group_history_message(
    *,
    profile,
    sender_user_id: str,
    sender_device: Device,
    sender_key: GroupSenderKey,
    chain_iteration: int,
    encrypted_payload: str,
    created_at=None,
    reply_to=None,
) -> GroupMessageEncryption:
    message = Message.objects.create(
        room=profile.room,
        sender_user_id=sender_user_id,
        sender_device_id=str(sender_device.id),
        client_message_id=uuid.uuid4(),
        message_type="text",
        encrypted_payload=encrypted_payload,
        encryption_metadata={
            "algorithm": "group-sender-key-v1",
            "nonce": f"nonce-{chain_iteration}",
            "content_encoding": "myna-message-v1",
        },
        encryption_version=1,
        reply_to=reply_to,
        client_sent_at=created_at,
    )

    encryption = GroupMessageEncryption.objects.create(
        message=message,
        group_room=profile.room,
        epoch=sender_key.epoch,
        sender_key=sender_key,
        chain_iteration=chain_iteration,
        signature=f"signature-{chain_iteration}",
        encryption_metadata={
            "algorithm": "group-sender-key-v1",
            "nonce": f"nonce-{chain_iteration}",
            "content_encoding": "myna-message-v1",
        },
    )

    if created_at is not None:
        Message.objects.filter(id=message.id).update(
            created_at=created_at,
        )
        GroupMessageEncryption.objects.filter(id=encryption.id).update(
            created_at=created_at,
        )
        message.refresh_from_db()
        encryption.refresh_from_db()

    return encryption


class GroupHistoryAPITests(APITestCase):
    def history_url(self, group_id):
        return reverse(
            "chat_messages:group-history",
            kwargs={"group_id": group_id},
        )

    def _setup_history_group(self):
        profile = create_group_room(
            member_user_ids=[
                GROUP_MEMBER_USER_ID,
                GROUP_NEW_MEMBER_USER_ID,
            ],
        )

        owner_device = create_device(user_id=GROUP_OWNER_USER_ID)
        member_device = create_device(user_id=GROUP_MEMBER_USER_ID)

        owner_key = create_sender_key(
            profile=profile,
            sender_user_id=GROUP_OWNER_USER_ID,
            sender_device=owner_device,
        )

        GroupSenderKeyDistribution.objects.create(
            sender_key=owner_key,
            recipient_user_id=GROUP_MEMBER_USER_ID,
            recipient_device=member_device,
            encrypted_sender_key="encrypted-sender-key",
            distribution_metadata={
                "algorithm": "double-ratchet",
                "session_reference": "opaque-session",
                "message_number": 1,
                "nonce": "distribution-nonce",
            },
            distribution_version=1,
            status="stored",
        )

        return profile, owner_device, member_device, owner_key

    def test_authentication_is_required(self):
        profile, owner_device, member_device, owner_key = (
            self._setup_history_group()
        )

        response = self.client.get(
            self.history_url(profile.room.id),
            {
                "device_id": str(member_device.id),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_owned_active_device_is_required(self):
        profile, owner_device, member_device, owner_key = (
            self._setup_history_group()
        )

        authenticate_client(self.client, GROUP_OWNER_USER_ID)

        response = self.client.get(
            self.history_url(profile.room.id),
            {
                "device_id": str(member_device.id),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_inactive_device_is_rejected(self):
        profile, owner_device, member_device, owner_key = (
            self._setup_history_group()
        )

        member_device.is_active = False
        member_device.save(update_fields=["is_active"])

        authenticate_client(self.client, GROUP_MEMBER_USER_ID)

        response = self.client.get(
            self.history_url(profile.room.id),
            {
                "device_id": str(member_device.id),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_active_member_can_fetch_group_ciphertext_history(self):
        profile, owner_device, member_device, owner_key = (
            self._setup_history_group()
        )

        encryption = create_group_history_message(
            profile=profile,
            sender_user_id=GROUP_OWNER_USER_ID,
            sender_device=owner_device,
            sender_key=owner_key,
            chain_iteration=1,
            encrypted_payload="ciphertext-one",
        )

        authenticate_client(self.client, GROUP_MEMBER_USER_ID)

        response = self.client.get(
            self.history_url(profile.room.id),
            {
                "device_id": str(member_device.id),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        items = response.json()["data"]["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["id"], str(encryption.message.id))
        self.assertEqual(items[0]["encrypted_payload"], "ciphertext-one")
        self.assertEqual(items[0]["epoch_number"], 1)
        self.assertEqual(
            items[0]["sender_key_id"],
            str(owner_key.sender_key_id),
        )
        self.assertEqual(
            items[0]["signing_public_key"],
            owner_key.signing_public_key,
        )

    def test_non_member_cannot_fetch_history(self):
        profile, owner_device, member_device, owner_key = (
            self._setup_history_group()
        )
        outsider_device = create_device(user_id=GROUP_OUTSIDER_USER_ID)

        authenticate_client(self.client, GROUP_OUTSIDER_USER_ID)

        response = self.client.get(
            self.history_url(profile.room.id),
            {
                "device_id": str(outsider_device.id),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_messages_before_join_are_hidden_when_join_history_false(self):
        profile, owner_device, member_device, owner_key = (
            self._setup_history_group()
        )

        membership = RoomMember.objects.get(
            room=profile.room,
            user_id=GROUP_MEMBER_USER_ID,
        )

        before_join = membership.joined_at - timedelta(minutes=5)
        after_join = membership.joined_at + timedelta(minutes=5)

        create_group_history_message(
            profile=profile,
            sender_user_id=GROUP_OWNER_USER_ID,
            sender_device=owner_device,
            sender_key=owner_key,
            chain_iteration=1,
            encrypted_payload="before-join",
            created_at=before_join,
        )
        create_group_history_message(
            profile=profile,
            sender_user_id=GROUP_OWNER_USER_ID,
            sender_device=owner_device,
            sender_key=owner_key,
            chain_iteration=2,
            encrypted_payload="after-join",
            created_at=after_join,
        )

        authenticate_client(self.client, GROUP_MEMBER_USER_ID)

        response = self.client.get(
            self.history_url(profile.room.id),
            {
                "device_id": str(member_device.id),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        payloads = [
            item["encrypted_payload"]
            for item in response.json()["data"]["items"]
        ]

        self.assertEqual(payloads, ["after-join"])
        self.assertNotIn("before-join", payloads)

    def test_join_history_true_allows_before_join_messages(self):
        profile, owner_device, member_device, owner_key = (
            self._setup_history_group()
        )

        profile.join_history_visible = True
        profile.save(update_fields=["join_history_visible"])

        membership = RoomMember.objects.get(
            room=profile.room,
            user_id=GROUP_MEMBER_USER_ID,
        )

        before_join = membership.joined_at - timedelta(minutes=5)

        create_group_history_message(
            profile=profile,
            sender_user_id=GROUP_OWNER_USER_ID,
            sender_device=owner_device,
            sender_key=owner_key,
            chain_iteration=1,
            encrypted_payload="before-join-visible",
            created_at=before_join,
        )

        authenticate_client(self.client, GROUP_MEMBER_USER_ID)

        response = self.client.get(
            self.history_url(profile.room.id),
            {
                "device_id": str(member_device.id),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        payloads = [
            item["encrypted_payload"]
            for item in response.json()["data"]["items"]
        ]

        self.assertIn("before-join-visible", payloads)

    def test_former_member_sees_only_membership_window(self):
        profile, owner_device, member_device, owner_key = (
            self._setup_history_group()
        )

        membership = RoomMember.objects.get(
            room=profile.room,
            user_id=GROUP_MEMBER_USER_ID,
        )

        before_left = membership.joined_at + timedelta(minutes=5)
        left_at = membership.joined_at + timedelta(minutes=10)
        after_left = membership.joined_at + timedelta(minutes=15)

        create_group_history_message(
            profile=profile,
            sender_user_id=GROUP_OWNER_USER_ID,
            sender_device=owner_device,
            sender_key=owner_key,
            chain_iteration=1,
            encrypted_payload="before-left",
            created_at=before_left,
        )
        create_group_history_message(
            profile=profile,
            sender_user_id=GROUP_OWNER_USER_ID,
            sender_device=owner_device,
            sender_key=owner_key,
            chain_iteration=2,
            encrypted_payload="after-left",
            created_at=after_left,
        )

        membership.is_active = False
        membership.left_at = left_at
        membership.save(
            update_fields=[
                "is_active",
                "left_at",
            ]
        )

        authenticate_client(self.client, GROUP_MEMBER_USER_ID)

        response = self.client.get(
            self.history_url(profile.room.id),
            {
                "device_id": str(member_device.id),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        payloads = [
            item["encrypted_payload"]
            for item in response.json()["data"]["items"]
        ]

        self.assertEqual(payloads, ["before-left"])
        self.assertNotIn("after-left", payloads)

    def test_other_group_messages_are_isolated(self):
        profile, owner_device, member_device, owner_key = (
            self._setup_history_group()
        )
        other_profile = create_group_room(
            owner_user_id="98",
            member_user_ids=["99"],
            name="Other Group",
        )
        other_device = create_device(user_id="98")
        other_key = create_sender_key(
            profile=other_profile,
            sender_user_id="98",
            sender_device=other_device,
        )

        create_group_history_message(
            profile=profile,
            sender_user_id=GROUP_OWNER_USER_ID,
            sender_device=owner_device,
            sender_key=owner_key,
            chain_iteration=1,
            encrypted_payload="wanted",
        )
        create_group_history_message(
            profile=other_profile,
            sender_user_id="98",
            sender_device=other_device,
            sender_key=other_key,
            chain_iteration=1,
            encrypted_payload="other-group",
        )

        authenticate_client(self.client, GROUP_MEMBER_USER_ID)

        response = self.client.get(
            self.history_url(profile.room.id),
            {
                "device_id": str(member_device.id),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        payloads = [
            item["encrypted_payload"]
            for item in response.json()["data"]["items"]
        ]

        self.assertEqual(payloads, ["wanted"])

    def test_cursor_pagination_is_stable(self):
        profile, owner_device, member_device, owner_key = (
            self._setup_history_group()
        )

        base_time = timezone.now()

        for index in range(5):
            create_group_history_message(
                profile=profile,
                sender_user_id=GROUP_OWNER_USER_ID,
                sender_device=owner_device,
                sender_key=owner_key,
                chain_iteration=index + 1,
                encrypted_payload=f"ciphertext-{index + 1}",
                created_at=base_time + timedelta(minutes=index),
            )

        authenticate_client(self.client, GROUP_MEMBER_USER_ID)

        first_response = self.client.get(
            self.history_url(profile.room.id),
            {
                "device_id": str(member_device.id),
                "page_size": 2,
            },
        )

        self.assertEqual(first_response.status_code, status.HTTP_200_OK)

        first_data = first_response.json()["data"]
        self.assertEqual(
            [
                item["encrypted_payload"]
                for item in first_data["items"]
            ],
            [
                "ciphertext-5",
                "ciphertext-4",
            ],
        )
        self.assertIsNotNone(first_data["next_cursor"])

        second_response = self.client.get(
            self.history_url(profile.room.id),
            {
                "device_id": str(member_device.id),
                "page_size": 2,
                "cursor": first_data["next_cursor"],
            },
        )

        self.assertEqual(second_response.status_code, status.HTTP_200_OK)

        second_data = second_response.json()["data"]
        self.assertEqual(
            [
                item["encrypted_payload"]
                for item in second_data["items"]
            ],
            [
                "ciphertext-3",
                "ciphertext-2",
            ],
        )
        self.assertIsNotNone(second_data["next_cursor"])

    def test_history_does_not_leak_distributions_or_secrets(self):
        profile, owner_device, member_device, owner_key = (
            self._setup_history_group()
        )

        create_group_history_message(
            profile=profile,
            sender_user_id=GROUP_OWNER_USER_ID,
            sender_device=owner_device,
            sender_key=owner_key,
            chain_iteration=1,
            encrypted_payload="ciphertext-one",
        )

        authenticate_client(self.client, GROUP_MEMBER_USER_ID)

        response = self.client.get(
            self.history_url(profile.room.id),
            {
                "device_id": str(member_device.id),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        item = response.json()["data"]["items"][0]
        forbidden_keys = {
            "distributions",
            "encrypted_sender_key",
            "sender_chain_secret",
            "message_key",
            "private_key",
            "plaintext",
            "ratchet_state",
            "recovery_key",
        }

        self.assertTrue(forbidden_keys.isdisjoint(set(item.keys())))

    def test_direct_room_history_is_not_available_from_group_history_api(self):
        direct_room = Room.objects.create(
            room_type=Room.RoomType.DIRECT,
            created_by_user_id=GROUP_OWNER_USER_ID,
            direct_pair_key=(
                "55555555555555555555555555555555"
                "55555555555555555555555555555555"
            ),
            is_active=True,
        )
        device = create_device(user_id=GROUP_OWNER_USER_ID)

        RoomMember.objects.create(
            room=direct_room,
            user_id=GROUP_OWNER_USER_ID,
            role=RoomMember.Role.MEMBER,
            added_by_user_id=GROUP_OWNER_USER_ID,
            is_active=True,
        )

        authenticate_client(self.client, GROUP_OWNER_USER_ID)

        response = self.client.get(
            self.history_url(direct_room.id),
            {
                "device_id": str(device.id),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_direct_message_key_envelope_regression(self):
        direct_room = Room.objects.create(
            room_type=Room.RoomType.DIRECT,
            created_by_user_id=GROUP_OWNER_USER_ID,
            direct_pair_key=(
                "66666666666666666666666666666666"
                "66666666666666666666666666666666"
            ),
            is_active=True,
        )
        owner_device = create_device(user_id=GROUP_OWNER_USER_ID)
        member_device = create_device(user_id=GROUP_MEMBER_USER_ID)

        message = Message.objects.create(
            room=direct_room,
            sender_user_id=GROUP_OWNER_USER_ID,
            sender_device_id=str(owner_device.id),
            client_message_id=uuid.uuid4(),
            message_type="text",
            encrypted_payload="direct-ciphertext",
            encryption_metadata={
                "algorithm": "xchacha20poly1305",
            },
            encryption_version=1,
        )

        envelope = MessageKeyEnvelope.objects.create(
            message=message,
            recipient_user_id=GROUP_MEMBER_USER_ID,
            recipient_device=member_device,
            protocol="sealed-box-v1",
            session_reference="direct-session",
            wrapped_message_key="wrapped-key",
            key_wrap_metadata={
                "algorithm": "sealed-box",
            },
            envelope_version=1,
        )

        self.assertEqual(MessageKeyEnvelope.objects.count(), 1)
        self.assertEqual(envelope.message_id, message.id)
import uuid

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.chat_messages.models import Message
from apps.e2ee_devices.models import Device
from apps.group_chat.models import (
    GroupEncryptionEpoch,
    GroupSenderKey,
    GroupSenderKeyDistribution,
)
from apps.group_chat.tests.factories import (
    GROUP_MEMBER_USER_ID,
    GROUP_OWNER_USER_ID,
    authenticate_client,
    create_group_room,
)


def create_device(
    *,
    user_id: str,
) -> Device:
    return Device.objects.create(
        user_id=user_id,
        device_name="Web",
        platform=Device.Platform.WEB,
        registration_id=12345,
        identity_key_public=f"identity-public-{uuid.uuid4()}",
        signed_prekey_id=1,
        signed_prekey_public=f"signed-prekey-public-{uuid.uuid4()}",
        signed_prekey_signature=f"signature-{uuid.uuid4()}",
        key_algorithm="curve25519",
        key_bundle_version=1,
        is_active=True,
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


class EncryptedMessageEventTests(APITestCase):
    def send_url(self):
        return reverse("chat_messages:group-message-send")

    def _ready_group(self):
        profile = create_group_room(
            member_user_ids=[GROUP_MEMBER_USER_ID],
        )

        owner_device = create_device(user_id=GROUP_OWNER_USER_ID)
        member_device = create_device(user_id=GROUP_MEMBER_USER_ID)

        sender_key = create_sender_key(
            profile=profile,
            sender_user_id=GROUP_OWNER_USER_ID,
            sender_device=owner_device,
        )

        distribute_sender_key_to_device(
            sender_key=sender_key,
            recipient_device=member_device,
        )

        target_message = Message.objects.create(
            room=profile.room,
            sender_user_id=GROUP_OWNER_USER_ID,
            sender_device_id=str(owner_device.id),
            client_message_id=uuid.uuid4(),
            message_type=Message.MessageType.TEXT,
            encrypted_payload="target-ciphertext",
            encryption_metadata={
                "algorithm": "group-sender-key-v1",
            },
            encryption_version=1,
        )

        return profile, owner_device, sender_key, target_message

    def payload(
        self,
        *,
        profile,
        sender_device,
        sender_key,
        target_message_id=None,
        message_type="reaction",
    ):
        metadata = {
            "algorithm": "group-sender-key-v1",
            "nonce": "event-nonce",
            "event_type": f"message.{message_type}",
        }

        if target_message_id is not None:
            metadata["target_message_id"] = str(target_message_id)

        return {
            "group_id": str(profile.room.id),
            "sender_device_id": str(sender_device.id),
            "client_message_id": str(uuid.uuid4()),
            "epoch_number": sender_key.epoch.epoch_number,
            "sender_key_id": str(sender_key.sender_key_id),
            "chain_iteration": 1,
            "message_type": message_type,
            "encrypted_payload": "encrypted-event-payload",
            "encryption_metadata": metadata,
            "signature": "event-signature",
            "reply_to_message_id": None,
            "client_sent_at": "2026-06-27T00:00:00Z",
            "recovery_envelopes": [],
        }

    def test_reaction_event_requires_same_room_target(self):
        profile, sender_device, sender_key, target_message = self._ready_group()

        authenticate_client(self.client, GROUP_OWNER_USER_ID)

        response = self.client.post(
            self.send_url(),
            self.payload(
                profile=profile,
                sender_device=sender_device,
                sender_key=sender_key,
                target_message_id=target_message.id,
                message_type="reaction",
            ),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_event_missing_target_is_rejected(self):
        profile, sender_device, sender_key, _ = self._ready_group()

        authenticate_client(self.client, GROUP_OWNER_USER_ID)

        response = self.client.post(
            self.send_url(),
            self.payload(
                profile=profile,
                sender_device=sender_device,
                sender_key=sender_key,
                target_message_id=None,
                message_type="reaction",
            ),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_delete_event_for_other_user_message_is_rejected(self):
        profile, sender_device, sender_key, target_message = self._ready_group()

        target_message.sender_user_id = GROUP_MEMBER_USER_ID
        target_message.save(update_fields=["sender_user_id"])

        authenticate_client(self.client, GROUP_OWNER_USER_ID)

        response = self.client.post(
            self.send_url(),
            self.payload(
                profile=profile,
                sender_device=sender_device,
                sender_key=sender_key,
                target_message_id=target_message.id,
                message_type="delete",
            ),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
import uuid
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

import jwt
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.chat_messages.models import (
    EncryptedAttachment,
    GroupMessageEncryption,
    Message,
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
    GROUP_OWNER_USER_ID,
    authenticate_client,
    create_group_room,
)


def create_device(
    *,
    user_id: str,
    is_active: bool = True,
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
        is_active=is_active,
    )


def create_completed_attachment(
    *,
    user_id: str,
    device: Device,
    status_value=EncryptedAttachment.UploadStatus.COMPLETED,
) -> EncryptedAttachment:
    return EncryptedAttachment.objects.create(
        uploader_user_id=user_id,
        uploader_device=device,
        storage_provider=EncryptedAttachment.StorageProvider.CLOUDINARY,
        storage_key=f"myna/test/attachments/{user_id}/{device.id}/{uuid.uuid4()}",
        resource_type="raw",
        ciphertext_size_hint=4096,
        ciphertext_sha256="a" * 64,
        ciphertext_size=4096,
        media_category=EncryptedAttachment.MediaCategory.FILE,
        upload_status=status_value,
        completed_at=(
            timezone.now()
            if status_value
            in {
                EncryptedAttachment.UploadStatus.COMPLETED,
                EncryptedAttachment.UploadStatus.ATTACHED,
            }
            else None
        ),
    )


def create_group_sender_key(
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


class DirectMessageAttachmentLinkingAPITests(APITestCase):
    def setUp(self):
        self.sender_user_id = "1"
        self.recipient_user_id = "2"

        self.sender_device = create_device(
            user_id=self.sender_user_id,
        )
        self.recipient_device = create_device(
            user_id=self.recipient_user_id,
        )

        self.url = reverse("chat_messages:send-direct-message")

        self.resolve_contact_patcher = patch(
            "apps.chat_messages.views.resolve_saved_contact_recipient"
        )
        self.mock_resolve_contact = self.resolve_contact_patcher.start()
        self.addCleanup(self.resolve_contact_patcher.stop)

        self.mock_resolve_contact.return_value = SimpleNamespace(
            contact_id="101",
            contact_user_id=self.recipient_user_id,
            saved_name="Recipient",
            contact_number="9999999999",
        )

    def authenticate_as(self, user_id: str):
        now = timezone.now()
        token = jwt.encode(
            {
                "sub": user_id,
                "type": "access",
                "jti": str(uuid.uuid4()),
                "iat": now,
                "nbf": now,
                "exp": now + timedelta(minutes=5),
            },
            settings.JWT_VERIFYING_KEY,
            algorithm=settings.JWT_ALGORITHM,
        )
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token}"
        )

    def valid_payload(
        self,
        *,
        client_message_id=None,
        attachment_ids=None,
    ):
        return {
            "recipient_contact_id": 101,
            "sender_device_id": str(self.sender_device.id),
            "client_message_id": str(
                client_message_id or uuid.uuid4()
            ),
            "message_type": "file",
            "encrypted_payload": "ENCRYPTED_DIRECT_PAYLOAD",
            "encryption_metadata": {
                "algorithm": "xchacha20poly1305",
                "nonce": "base64-nonce",
            },
            "encryption_version": 1,
            "envelopes": [
                {
                    "recipient_device_id": str(self.sender_device.id),
                    "protocol": "device_sync",
                    "session_reference": "sender-sync",
                    "wrapped_message_key": "WRAPPED_KEY_FOR_SENDER",
                    "key_wrap_metadata": {
                        "algorithm": "device-sync-v1",
                    },
                    "envelope_version": 1,
                },
                {
                    "recipient_device_id": str(self.recipient_device.id),
                    "protocol": "double_ratchet",
                    "session_reference": "recipient-session",
                    "wrapped_message_key": "WRAPPED_KEY_FOR_RECIPIENT",
                    "key_wrap_metadata": {
                        "algorithm": "double-ratchet",
                        "message_number": 1,
                    },
                    "envelope_version": 1,
                },
            ],
            "attachment_ids": [
                str(attachment_id)
                for attachment_id in (attachment_ids or [])
            ],
        }

    def test_direct_message_with_completed_attachment_links_attachment(self):
        self.authenticate_as(self.sender_user_id)

        attachment = create_completed_attachment(
            user_id=self.sender_user_id,
            device=self.sender_device,
        )

        response = self.client.post(
            self.url,
            self.valid_payload(
                attachment_ids=[attachment.id],
            ),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        attachment.refresh_from_db()

        self.assertEqual(
            attachment.upload_status,
            EncryptedAttachment.UploadStatus.ATTACHED,
        )
        self.assertIsNotNone(attachment.attached_message_id)
        self.assertIsNotNone(attachment.attached_room_id)
        self.assertIsNotNone(attachment.attached_at)

    def test_direct_message_rejects_initiated_attachment(self):
        self.authenticate_as(self.sender_user_id)

        attachment = EncryptedAttachment.objects.create(
            uploader_user_id=self.sender_user_id,
            uploader_device=self.sender_device,
            storage_provider=EncryptedAttachment.StorageProvider.CLOUDINARY,
            storage_key=f"myna/test/attachments/{uuid.uuid4()}",
            resource_type="raw",
            media_category=EncryptedAttachment.MediaCategory.FILE,
            upload_status=EncryptedAttachment.UploadStatus.INITIATED,
        )

        response = self.client.post(
            self.url,
            self.valid_payload(
                attachment_ids=[attachment.id],
            ),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_direct_idempotent_retry_with_same_attachment_ids_succeeds(self):
        self.authenticate_as(self.sender_user_id)

        client_message_id = uuid.uuid4()
        attachment = create_completed_attachment(
            user_id=self.sender_user_id,
            device=self.sender_device,
        )

        payload = self.valid_payload(
            client_message_id=client_message_id,
            attachment_ids=[attachment.id],
        )

        first_response = self.client.post(
            self.url,
            payload,
            format="json",
        )
        second_response = self.client.post(
            self.url,
            payload,
            format="json",
        )

        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second_response.status_code, status.HTTP_200_OK)

    def test_direct_idempotent_retry_with_different_attachment_ids_fails(self):
        self.authenticate_as(self.sender_user_id)

        client_message_id = uuid.uuid4()

        first_attachment = create_completed_attachment(
            user_id=self.sender_user_id,
            device=self.sender_device,
        )
        second_attachment = create_completed_attachment(
            user_id=self.sender_user_id,
            device=self.sender_device,
        )

        first_payload = self.valid_payload(
            client_message_id=client_message_id,
            attachment_ids=[first_attachment.id],
        )
        second_payload = self.valid_payload(
            client_message_id=client_message_id,
            attachment_ids=[second_attachment.id],
        )

        first_response = self.client.post(
            self.url,
            first_payload,
            format="json",
        )
        second_response = self.client.post(
            self.url,
            second_payload,
            format="json",
        )

        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second_response.status_code, status.HTTP_409_CONFLICT)


class GroupMessageAttachmentLinkingAPITests(APITestCase):
    def send_url(self):
        return reverse("chat_messages:group-message-send")

    def ready_group_setup(self):
        profile = create_group_room(
            member_user_ids=[
                GROUP_MEMBER_USER_ID,
                GROUP_NEW_MEMBER_USER_ID,
            ],
        )

        owner_device = create_device(user_id=GROUP_OWNER_USER_ID)
        member_device = create_device(user_id=GROUP_MEMBER_USER_ID)
        new_member_device = create_device(user_id=GROUP_NEW_MEMBER_USER_ID)

        sender_key = create_group_sender_key(
            profile=profile,
            sender_user_id=GROUP_MEMBER_USER_ID,
            sender_device=member_device,
        )

        for device in [
            owner_device,
            new_member_device,
        ]:
            distribute_sender_key_to_device(
                sender_key=sender_key,
                recipient_device=device,
            )

        return profile, member_device, sender_key

    def group_payload(
        self,
        *,
        profile,
        sender_device,
        sender_key,
        client_message_id=None,
        chain_iteration=1,
        attachment_ids=None,
    ):
        return {
            "group_id": str(profile.room.id),
            "sender_device_id": str(sender_device.id),
            "client_message_id": str(
                client_message_id or uuid.uuid4()
            ),
            "epoch_number": sender_key.epoch.epoch_number,
            "sender_key_id": str(sender_key.sender_key_id),
            "chain_iteration": chain_iteration,
            "message_type": "file",
            "encrypted_payload": "ENCRYPTED_GROUP_PAYLOAD",
            "encryption_metadata": {
                "algorithm": "group-sender-key-v1",
                "nonce": "base64-nonce",
                "content_encoding": "myna-message-v1",
            },
            "signature": "base64-signature",
            "client_sent_at": "2026-06-27T00:00:00Z",
            "attachment_ids": [
                str(attachment_id)
                for attachment_id in (attachment_ids or [])
            ],
        }

    def test_group_message_with_completed_attachment_links_attachment(self):
        profile, sender_device, sender_key = self.ready_group_setup()
        authenticate_client(self.client, GROUP_MEMBER_USER_ID)

        attachment = create_completed_attachment(
            user_id=GROUP_MEMBER_USER_ID,
            device=sender_device,
        )

        response = self.client.post(
            self.send_url(),
            self.group_payload(
                profile=profile,
                sender_device=sender_device,
                sender_key=sender_key,
                attachment_ids=[attachment.id],
            ),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        attachment.refresh_from_db()

        self.assertEqual(
            attachment.upload_status,
            EncryptedAttachment.UploadStatus.ATTACHED,
        )
        self.assertEqual(attachment.attached_room_id, profile.room.id)
        self.assertIsNotNone(attachment.attached_message_id)

        self.assertEqual(Message.objects.count(), 1)
        self.assertEqual(GroupMessageEncryption.objects.count(), 1)

    def test_group_message_rejects_attachment_owned_by_another_user(self):
        profile, sender_device, sender_key = self.ready_group_setup()
        authenticate_client(self.client, GROUP_MEMBER_USER_ID)

        other_device = create_device(user_id=GROUP_NEW_MEMBER_USER_ID)
        attachment = create_completed_attachment(
            user_id=GROUP_NEW_MEMBER_USER_ID,
            device=other_device,
        )

        response = self.client.post(
            self.send_url(),
            self.group_payload(
                profile=profile,
                sender_device=sender_device,
                sender_key=sender_key,
                attachment_ids=[attachment.id],
            ),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_group_idempotent_retry_with_same_attachment_ids_succeeds(self):
        profile, sender_device, sender_key = self.ready_group_setup()
        authenticate_client(self.client, GROUP_MEMBER_USER_ID)

        client_message_id = uuid.uuid4()
        attachment = create_completed_attachment(
            user_id=GROUP_MEMBER_USER_ID,
            device=sender_device,
        )

        payload = self.group_payload(
            profile=profile,
            sender_device=sender_device,
            sender_key=sender_key,
            client_message_id=client_message_id,
            chain_iteration=1,
            attachment_ids=[attachment.id],
        )

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

    def test_group_idempotent_retry_with_different_attachment_ids_fails(self):
        profile, sender_device, sender_key = self.ready_group_setup()
        authenticate_client(self.client, GROUP_MEMBER_USER_ID)

        client_message_id = uuid.uuid4()

        first_attachment = create_completed_attachment(
            user_id=GROUP_MEMBER_USER_ID,
            device=sender_device,
        )
        second_attachment = create_completed_attachment(
            user_id=GROUP_MEMBER_USER_ID,
            device=sender_device,
        )

        first_payload = self.group_payload(
            profile=profile,
            sender_device=sender_device,
            sender_key=sender_key,
            client_message_id=client_message_id,
            chain_iteration=1,
            attachment_ids=[first_attachment.id],
        )

        second_payload = self.group_payload(
            profile=profile,
            sender_device=sender_device,
            sender_key=sender_key,
            client_message_id=client_message_id,
            chain_iteration=1,
            attachment_ids=[second_attachment.id],
        )

        first_response = self.client.post(
            self.send_url(),
            first_payload,
            format="json",
        )
        second_response = self.client.post(
            self.send_url(),
            second_payload,
            format="json",
        )

        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second_response.status_code, status.HTTP_409_CONFLICT)
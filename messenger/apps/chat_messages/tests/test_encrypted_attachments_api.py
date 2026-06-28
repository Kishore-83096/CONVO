import uuid

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.chat_messages.models import EncryptedAttachment
from apps.e2ee_devices.models import Device
from apps.group_chat.tests.factories import (
    GROUP_MEMBER_USER_ID,
    GROUP_OWNER_USER_ID,
    authenticate_client,
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


class EncryptedAttachmentAPITests(APITestCase):
    def initiate_url(self):
        return reverse("chat_messages:encrypted-attachment-initiate")

    def complete_url(self, attachment_id):
        return reverse(
            "chat_messages:encrypted-attachment-complete",
            kwargs={"attachment_id": attachment_id},
        )

    def download_url(self, attachment_id):
        return reverse(
            "chat_messages:encrypted-attachment-download",
            kwargs={"attachment_id": attachment_id},
        )

    def delete_url(self, attachment_id):
        return reverse(
            "chat_messages:encrypted-attachment-delete",
            kwargs={"attachment_id": attachment_id},
        )

    def test_initiate_attachment(self):
        device = create_device(user_id=GROUP_OWNER_USER_ID)
        authenticate_client(self.client, GROUP_OWNER_USER_ID)

        response = self.client.post(
            self.initiate_url(),
            {
                "device_id": str(device.id),
                "storage_provider": "cloudinary",
                "media_category": "image",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(EncryptedAttachment.objects.count(), 1)

        attachment = EncryptedAttachment.objects.get()
        self.assertEqual(attachment.uploader_user_id, GROUP_OWNER_USER_ID)
        self.assertEqual(
            attachment.upload_status,
            EncryptedAttachment.UploadStatus.INITIATED,
        )

    def test_forbidden_plaintext_storage_key_is_rejected(self):
        device = create_device(user_id=GROUP_OWNER_USER_ID)
        authenticate_client(self.client, GROUP_OWNER_USER_ID)

        response = self.client.post(
            self.initiate_url(),
            {
                "device_id": str(device.id),
                "storage_key": "plaintext-secret-attachment-key",
                "media_category": "file",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(EncryptedAttachment.objects.count(), 0)

    def test_complete_attachment(self):
        device = create_device(user_id=GROUP_OWNER_USER_ID)
        authenticate_client(self.client, GROUP_OWNER_USER_ID)

        initiate_response = self.client.post(
            self.initiate_url(),
            {
                "device_id": str(device.id),
                "media_category": "file",
            },
            format="json",
        )

        attachment_id = initiate_response.json()["data"]["id"]

        response = self.client.post(
            self.complete_url(attachment_id),
            {
                "device_id": str(device.id),
                "ciphertext_sha256": "a" * 64,
                "ciphertext_size": 4096,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        attachment = EncryptedAttachment.objects.get(id=attachment_id)
        self.assertEqual(
            attachment.upload_status,
            EncryptedAttachment.UploadStatus.COMPLETED,
        )
        self.assertEqual(attachment.ciphertext_size, 4096)
        self.assertEqual(attachment.ciphertext_sha256, "a" * 64)

    def test_other_user_cannot_complete_attachment(self):
        owner_device = create_device(user_id=GROUP_OWNER_USER_ID)
        other_device = create_device(user_id=GROUP_MEMBER_USER_ID)

        authenticate_client(self.client, GROUP_OWNER_USER_ID)

        initiate_response = self.client.post(
            self.initiate_url(),
            {
                "device_id": str(owner_device.id),
                "media_category": "file",
            },
            format="json",
        )

        attachment_id = initiate_response.json()["data"]["id"]

        authenticate_client(self.client, GROUP_MEMBER_USER_ID)

        response = self.client.post(
            self.complete_url(attachment_id),
            {
                "device_id": str(other_device.id),
                "ciphertext_sha256": "b" * 64,
                "ciphertext_size": 100,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_download_completed_attachment_metadata(self):
        device = create_device(user_id=GROUP_OWNER_USER_ID)
        authenticate_client(self.client, GROUP_OWNER_USER_ID)

        initiate_response = self.client.post(
            self.initiate_url(),
            {
                "device_id": str(device.id),
                "media_category": "file",
            },
            format="json",
        )

        attachment_id = initiate_response.json()["data"]["id"]

        self.client.post(
            self.complete_url(attachment_id),
            {
                "device_id": str(device.id),
                "ciphertext_sha256": "c" * 64,
                "ciphertext_size": 200,
            },
            format="json",
        )

        response = self.client.get(
            self.download_url(attachment_id),
            {
                "device_id": str(device.id),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["data"]["id"], attachment_id)

    def test_delete_attachment_is_idempotent(self):
        device = create_device(user_id=GROUP_OWNER_USER_ID)
        authenticate_client(self.client, GROUP_OWNER_USER_ID)

        initiate_response = self.client.post(
            self.initiate_url(),
            {
                "device_id": str(device.id),
                "media_category": "file",
            },
            format="json",
        )

        attachment_id = initiate_response.json()["data"]["id"]

        first_response = self.client.delete(
            self.delete_url(attachment_id),
            {
                "device_id": str(device.id),
            },
            format="json",
        )
        second_response = self.client.delete(
            self.delete_url(attachment_id),
            {
                "device_id": str(device.id),
            },
            format="json",
        )

        self.assertEqual(first_response.status_code, status.HTTP_200_OK)
        self.assertEqual(second_response.status_code, status.HTTP_200_OK)

        attachment = EncryptedAttachment.objects.get(id=attachment_id)
        self.assertEqual(
            attachment.upload_status,
            EncryptedAttachment.UploadStatus.DELETED,
        )
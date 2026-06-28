import uuid

from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.chat_messages.models import EncryptedAttachment
from apps.chat_messages.tests.test_encrypted_attachments_api import create_device
from apps.group_chat.tests.factories import (
    GROUP_MEMBER_USER_ID,
    GROUP_OWNER_USER_ID,
    authenticate_client,
)


@override_settings(
    CLOUDINARY_URL="cloudinary://public-api-key:private-api-secret@test-cloud",
    CLOUDINARY_FOLDER="myna/test/attachments",
    ATTACHMENT_CLOUDINARY_RESOURCE_TYPE="raw",
    ATTACHMENT_MIN_TTL_SECONDS=60,
    ATTACHMENT_UPLOAD_MAX_TTL_SECONDS=900,
    ATTACHMENT_UPLOAD_SIGNATURE_TTL_SECONDS=900,
    ATTACHMENT_MAX_CIPHERTEXT_BYTES=50 * 1024 * 1024,
)
class CloudinarySignedUploadAPITests(APITestCase):
    def sign_upload_url(self):
        return reverse(
            "chat_messages:encrypted-attachment-cloudinary-sign-upload"
        )

    def test_jwt_required(self):
        response = self.client.post(
            self.sign_upload_url(),
            {
                "device_id": str(uuid.uuid4()),
                "media_category": "image",
                "ciphertext_size_hint": 4096,
                "expires_in_seconds": 900,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_active_device_required(self):
        device = create_device(
            user_id=GROUP_OWNER_USER_ID,
            is_active=False,
        )
        authenticate_client(self.client, GROUP_OWNER_USER_ID)

        response = self.client.post(
            self.sign_upload_url(),
            {
                "device_id": str(device.id),
                "media_category": "image",
                "ciphertext_size_hint": 4096,
                "expires_in_seconds": 900,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(EncryptedAttachment.objects.count(), 0)

    def test_other_user_device_is_rejected(self):
        other_user_device = create_device(user_id=GROUP_MEMBER_USER_ID)
        authenticate_client(self.client, GROUP_OWNER_USER_ID)

        response = self.client.post(
            self.sign_upload_url(),
            {
                "device_id": str(other_user_device.id),
                "media_category": "image",
                "ciphertext_size_hint": 4096,
                "expires_in_seconds": 900,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(EncryptedAttachment.objects.count(), 0)

    def test_ciphertext_size_hint_above_max_is_rejected(self):
        device = create_device(user_id=GROUP_OWNER_USER_ID)
        authenticate_client(self.client, GROUP_OWNER_USER_ID)

        response = self.client.post(
            self.sign_upload_url(),
            {
                "device_id": str(device.id),
                "media_category": "image",
                "ciphertext_size_hint": 50 * 1024 * 1024 + 1,
                "expires_in_seconds": 900,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(EncryptedAttachment.objects.count(), 0)

    def test_invalid_media_category_is_rejected(self):
        device = create_device(user_id=GROUP_OWNER_USER_ID)
        authenticate_client(self.client, GROUP_OWNER_USER_ID)

        response = self.client.post(
            self.sign_upload_url(),
            {
                "device_id": str(device.id),
                "media_category": "document",
                "ciphertext_size_hint": 4096,
                "expires_in_seconds": 900,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(EncryptedAttachment.objects.count(), 0)

    def test_returns_signed_payload_and_creates_initiated_row(self):
        device = create_device(user_id=GROUP_OWNER_USER_ID)
        authenticate_client(self.client, GROUP_OWNER_USER_ID)

        response = self.client.post(
            self.sign_upload_url(),
            {
                "device_id": str(device.id),
                "media_category": "image",
                "ciphertext_size_hint": 4096,
                "expires_in_seconds": 900,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        payload = response.json()["data"]

        self.assertEqual(payload["storage_provider"], "cloudinary")
        self.assertEqual(payload["cloud_name"], "test-cloud")
        self.assertEqual(payload["api_key"], "public-api-key")
        self.assertEqual(payload["resource_type"], "raw")
        self.assertEqual(
            payload["upload_url"],
            "https://api.cloudinary.com/v1_1/test-cloud/raw/upload",
        )
        self.assertTrue(payload["signature"])
        self.assertIn("timestamp", payload)
        self.assertIn("expires_at", payload)
        self.assertIn("attachment_id", payload)
        self.assertNotIn("api_secret", payload)
        self.assertNotIn("private-api-secret", str(payload))

        attachment = EncryptedAttachment.objects.get(
            id=payload["attachment_id"]
        )

        self.assertEqual(
            attachment.upload_status,
            EncryptedAttachment.UploadStatus.INITIATED,
        )
        self.assertEqual(attachment.uploader_user_id, GROUP_OWNER_USER_ID)
        self.assertEqual(attachment.uploader_device_id, device.id)
        self.assertEqual(attachment.storage_provider, "cloudinary")
        self.assertEqual(attachment.resource_type, "raw")
        self.assertEqual(attachment.ciphertext_size_hint, 4096)
        self.assertEqual(attachment.storage_key, payload["public_id"])
        self.assertEqual(attachment.storage_key, payload["storage_key"])
        self.assertIsNotNone(attachment.upload_signature_expires_at)

        self.assertTrue(
            payload["public_id"].startswith(
                f"myna/test/attachments/{GROUP_OWNER_USER_ID}/{device.id}/"
            )
        )

    def test_frontend_cannot_override_cloudinary_destination_or_signature(self):
        device = create_device(user_id=GROUP_OWNER_USER_ID)
        authenticate_client(self.client, GROUP_OWNER_USER_ID)

        response = self.client.post(
            self.sign_upload_url(),
            {
                "device_id": str(device.id),
                "media_category": "file",
                "ciphertext_size_hint": 4096,
                "expires_in_seconds": 900,
                "public_id": "evil/folder/attachment",
                "folder": "evil/folder",
                "storage_key": "evil/storage-key",
                "resource_type": "image",
                "cloud_name": "evil-cloud",
                "api_key": "evil-api-key",
                "signature": "evil-signature",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(EncryptedAttachment.objects.count(), 0)

    def test_plaintext_metadata_fields_are_rejected(self):
        device = create_device(user_id=GROUP_OWNER_USER_ID)
        authenticate_client(self.client, GROUP_OWNER_USER_ID)

        response = self.client.post(
            self.sign_upload_url(),
            {
                "device_id": str(device.id),
                "media_category": "image",
                "ciphertext_size_hint": 4096,
                "filename": "photo.png",
                "mime_type": "image/png",
                "caption": "hello",
                "dimensions": {
                    "width": 100,
                    "height": 100,
                },
                "attachment_key": "plaintext-key",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(EncryptedAttachment.objects.count(), 0)

    @override_settings(
        CLOUDINARY_URL="",
    )
    def test_missing_cloudinary_config_returns_503(self):
        device = create_device(user_id=GROUP_OWNER_USER_ID)
        authenticate_client(self.client, GROUP_OWNER_USER_ID)

        response = self.client.post(
            self.sign_upload_url(),
            {
                "device_id": str(device.id),
                "media_category": "file",
                "ciphertext_size_hint": 4096,
                "expires_in_seconds": 900,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_503_SERVICE_UNAVAILABLE,
        )
        self.assertEqual(EncryptedAttachment.objects.count(), 0)
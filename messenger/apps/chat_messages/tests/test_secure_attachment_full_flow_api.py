import uuid
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

import jwt
from django.conf import settings
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.chat_messages.models import EncryptedAttachment
from apps.chat_messages.tests.test_message_attachment_linking_api import create_device
from apps.group_chat.tests.factories import (
    GROUP_MEMBER_USER_ID,
    GROUP_OWNER_USER_ID,
)


@override_settings(
    CLOUDINARY_URL="cloudinary://public-api-key:private-api-secret@test-cloud",
    CLOUDINARY_FOLDER="myna/test/attachments",
    ATTACHMENT_CLOUDINARY_RESOURCE_TYPE="raw",
    ATTACHMENT_MIN_TTL_SECONDS=60,
    ATTACHMENT_UPLOAD_MAX_TTL_SECONDS=900,
    ATTACHMENT_UPLOAD_SIGNATURE_TTL_SECONDS=900,
    ATTACHMENT_MAX_CIPHERTEXT_BYTES=50 * 1024 * 1024,
    ATTACHMENT_VERIFY_CLOUDINARY_ON_COMPLETE=False,
    ATTACHMENT_DOWNLOAD_URL_TTL_SECONDS=300,
    ATTACHMENT_DOWNLOAD_URL_MAX_TTL_SECONDS=900,
)
class SecureAttachmentFullFlowAPITests(APITestCase):
    def setUp(self):
        self.sender_user_id = GROUP_OWNER_USER_ID
        self.recipient_user_id = GROUP_MEMBER_USER_ID

        self.sender_device = create_device(
            user_id=self.sender_user_id,
        )
        self.recipient_device = create_device(
            user_id=self.recipient_user_id,
        )

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

    def sign_upload_url(self):
        return reverse(
            "chat_messages:encrypted-attachment-cloudinary-sign-upload"
        )

    def complete_url(self, attachment_id):
        return reverse(
            "chat_messages:encrypted-attachment-complete",
            kwargs={
                "attachment_id": attachment_id,
            },
        )

    def send_direct_url(self):
        return reverse("chat_messages:send-direct-message")

    def download_url(self, attachment_id):
        return reverse(
            "chat_messages:encrypted-attachment-download",
            kwargs={
                "attachment_id": attachment_id,
            },
        )

    def direct_payload(
        self,
        *,
        attachment_id,
        client_message_id=None,
    ):
        return {
            "recipient_contact_id": 101,
            "sender_device_id": str(self.sender_device.id),
            "client_message_id": str(client_message_id or uuid.uuid4()),
            "message_type": "file",
            "encrypted_payload": "ENCRYPTED_DIRECT_PAYLOAD_WITH_ATTACHMENT_METADATA",
            "encryption_metadata": {
                "algorithm": "xchacha20poly1305",
                "nonce": "base64-nonce",
            },
            "encryption_version": 1,
            "envelopes": [
                {
                    "recipient_device_id": str(self.sender_device.id),
                    "protocol": "device_sync",
                    "session_reference": "sender-sync-session",
                    "wrapped_message_key": "WRAPPED_KEY_FOR_SENDER_DEVICE",
                    "key_wrap_metadata": {
                        "algorithm": "device-sync-v1",
                    },
                    "envelope_version": 1,
                },
                {
                    "recipient_device_id": str(self.recipient_device.id),
                    "protocol": "double_ratchet",
                    "session_reference": "recipient-session",
                    "wrapped_message_key": "WRAPPED_KEY_FOR_RECIPIENT_DEVICE",
                    "key_wrap_metadata": {
                        "algorithm": "double-ratchet",
                        "message_number": 1,
                    },
                    "envelope_version": 1,
                },
            ],
            "attachment_ids": [
                str(attachment_id),
            ],
        }

    def create_signed_upload(self):
        self.authenticate_as(self.sender_user_id)

        response = self.client.post(
            self.sign_upload_url(),
            {
                "device_id": str(self.sender_device.id),
                "media_category": "file",
                "ciphertext_size_hint": 4096,
                "expires_in_seconds": 900,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        payload = response.json()["data"]

        self.assertEqual(payload["resource_type"], "raw")
        self.assertEqual(payload["storage_provider"], "cloudinary")
        self.assertTrue(payload["public_id"])
        self.assertTrue(payload["signature"])
        self.assertNotIn("api_secret", payload)
        self.assertNotIn("private-api-secret", str(payload))

        return payload

    def complete_upload(self, *, attachment_id):
        self.authenticate_as(self.sender_user_id)

        response = self.client.post(
            self.complete_url(attachment_id),
            {
                "device_id": str(self.sender_device.id),
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
        self.assertEqual(attachment.ciphertext_sha256, "a" * 64)
        self.assertEqual(attachment.ciphertext_size, 4096)

    def send_direct_message_with_attachment(self, *, attachment_id):
        self.authenticate_as(self.sender_user_id)

        response = self.client.post(
            self.send_direct_url(),
            self.direct_payload(
                attachment_id=attachment_id,
            ),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        attachment = EncryptedAttachment.objects.get(id=attachment_id)

        self.assertEqual(
            attachment.upload_status,
            EncryptedAttachment.UploadStatus.ATTACHED,
        )
        self.assertIsNotNone(attachment.attached_room_id)
        self.assertIsNotNone(attachment.attached_message_id)
        self.assertIsNotNone(attachment.attached_at)

    def recipient_downloads_attachment(self, *, attachment_id):
        self.authenticate_as(self.recipient_user_id)

        response = self.client.get(
            self.download_url(attachment_id),
            {
                "device_id": str(self.recipient_device.id),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()["data"]

        self.assertEqual(
            data["attachment"]["id"],
            str(attachment_id),
        )
        self.assertEqual(
            data["attachment"]["ciphertext_sha256"],
            "a" * 64,
        )
        self.assertEqual(
            data["attachment"]["ciphertext_size"],
            4096,
        )
        self.assertEqual(
            data["attachment"]["media_category"],
            "file",
        )
        self.assertEqual(
            data["attachment"]["upload_status"],
            EncryptedAttachment.UploadStatus.ATTACHED,
        )

        self.assertIn("download_url", data)
        self.assertIn("expires_at", data)

        serialized_data = str(data)

        self.assertNotIn("api_secret", serialized_data)
        self.assertNotIn("private-api-secret", serialized_data)
        self.assertNotIn("filename", serialized_data)
        self.assertNotIn("mime_type", serialized_data)
        self.assertNotIn("caption", serialized_data)
        self.assertNotIn("thumbnail", serialized_data)
        self.assertNotIn("dimensions", serialized_data)
        self.assertNotIn("attachment_key", serialized_data)
        self.assertNotIn("decryption_key", serialized_data)

    def test_full_secure_attachment_flow(self):
        signed_upload_payload = self.create_signed_upload()

        attachment_id = signed_upload_payload["attachment_id"]

        self.complete_upload(
            attachment_id=attachment_id,
        )

        self.send_direct_message_with_attachment(
            attachment_id=attachment_id,
        )

        self.recipient_downloads_attachment(
            attachment_id=attachment_id,
        )

    def test_upload_signing_rejects_plaintext_and_frontend_controlled_fields(self):
        self.authenticate_as(self.sender_user_id)

        response = self.client.post(
            self.sign_upload_url(),
            {
                "device_id": str(self.sender_device.id),
                "media_category": "file",
                "ciphertext_size_hint": 4096,
                "filename": "photo.png",
                "mime_type": "image/png",
                "caption": "hello",
                "thumbnail": "base64-thumbnail",
                "dimensions": {
                    "width": 100,
                    "height": 100,
                },
                "attachment_key": "plaintext-secret-key",
                "public_id": "frontend/controlled/public-id",
                "folder": "frontend/controlled/folder",
                "storage_key": "frontend/controlled/storage-key",
                "resource_type": "image",
                "signature": "frontend-signature",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(EncryptedAttachment.objects.count(), 0)

    def test_recipient_cannot_download_unattached_completed_attachment(self):
        signed_upload_payload = self.create_signed_upload()
        attachment_id = signed_upload_payload["attachment_id"]

        self.complete_upload(
            attachment_id=attachment_id,
        )

        self.authenticate_as(self.recipient_user_id)

        response = self.client.get(
            self.download_url(attachment_id),
            {
                "device_id": str(self.recipient_device.id),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
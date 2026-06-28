from datetime import timedelta
from unittest.mock import patch

from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.chat_messages.cloudinary_attachment_services import (
    CloudinaryAttachmentConfigurationError,
    CloudinaryAttachmentVerificationError,
)
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
    ATTACHMENT_VERIFY_CLOUDINARY_ON_COMPLETE=False,
)
class CloudinaryCompleteHardeningAPITests(APITestCase):
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

    def create_signed_upload(
        self,
        *,
        user_id=GROUP_OWNER_USER_ID,
        device=None,
        ciphertext_size_hint=4096,
    ):
        if device is None:
            device = create_device(user_id=user_id)

        authenticate_client(self.client, user_id)

        response = self.client.post(
            self.sign_upload_url(),
            {
                "device_id": str(device.id),
                "media_category": "file",
                "ciphertext_size_hint": ciphertext_size_hint,
                "expires_in_seconds": 900,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        return {
            "device": device,
            "attachment_id": response.json()["data"]["attachment_id"],
        }

    def test_complete_succeeds_before_upload_signature_expiry(self):
        signed_upload = self.create_signed_upload()

        response = self.client.post(
            self.complete_url(signed_upload["attachment_id"]),
            {
                "device_id": str(signed_upload["device"].id),
                "ciphertext_sha256": "a" * 64,
                "ciphertext_size": 4096,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        attachment = EncryptedAttachment.objects.get(
            id=signed_upload["attachment_id"]
        )

        self.assertEqual(
            attachment.upload_status,
            EncryptedAttachment.UploadStatus.COMPLETED,
        )
        self.assertEqual(attachment.ciphertext_sha256, "a" * 64)
        self.assertEqual(attachment.ciphertext_size, 4096)
        self.assertIsNotNone(attachment.completed_at)

    def test_complete_fails_after_upload_signature_expiry(self):
        signed_upload = self.create_signed_upload()

        attachment = EncryptedAttachment.objects.get(
            id=signed_upload["attachment_id"]
        )
        attachment.upload_signature_expires_at = (
            timezone.now() - timedelta(seconds=1)
        )
        attachment.expires_at = attachment.upload_signature_expires_at
        attachment.save(
            update_fields=[
                "upload_signature_expires_at",
                "expires_at",
            ]
        )

        response = self.client.post(
            self.complete_url(signed_upload["attachment_id"]),
            {
                "device_id": str(signed_upload["device"].id),
                "ciphertext_sha256": "b" * 64,
                "ciphertext_size": 4096,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

        attachment.refresh_from_db()

        self.assertEqual(
            attachment.upload_status,
            EncryptedAttachment.UploadStatus.EXPIRED,
        )

    def test_complete_fails_for_wrong_user(self):
        owner_device = create_device(user_id=GROUP_OWNER_USER_ID)
        signed_upload = self.create_signed_upload(
            user_id=GROUP_OWNER_USER_ID,
            device=owner_device,
        )

        other_device = create_device(user_id=GROUP_MEMBER_USER_ID)
        authenticate_client(self.client, GROUP_MEMBER_USER_ID)

        response = self.client.post(
            self.complete_url(signed_upload["attachment_id"]),
            {
                "device_id": str(other_device.id),
                "ciphertext_sha256": "c" * 64,
                "ciphertext_size": 4096,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_complete_fails_for_wrong_device_same_user(self):
        original_device = create_device(user_id=GROUP_OWNER_USER_ID)
        other_device = create_device(user_id=GROUP_OWNER_USER_ID)

        signed_upload = self.create_signed_upload(
            user_id=GROUP_OWNER_USER_ID,
            device=original_device,
        )

        response = self.client.post(
            self.complete_url(signed_upload["attachment_id"]),
            {
                "device_id": str(other_device.id),
                "ciphertext_sha256": "d" * 64,
                "ciphertext_size": 4096,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_complete_fails_if_already_completed(self):
        signed_upload = self.create_signed_upload()

        first_response = self.client.post(
            self.complete_url(signed_upload["attachment_id"]),
            {
                "device_id": str(signed_upload["device"].id),
                "ciphertext_sha256": "e" * 64,
                "ciphertext_size": 4096,
            },
            format="json",
        )

        self.assertEqual(first_response.status_code, status.HTTP_200_OK)

        second_response = self.client.post(
            self.complete_url(signed_upload["attachment_id"]),
            {
                "device_id": str(signed_upload["device"].id),
                "ciphertext_sha256": "f" * 64,
                "ciphertext_size": 4096,
            },
            format="json",
        )

        self.assertEqual(second_response.status_code, status.HTTP_409_CONFLICT)

    def test_complete_rejects_oversized_ciphertext_size(self):
        signed_upload = self.create_signed_upload(
            ciphertext_size_hint=4096,
        )

        response = self.client.post(
            self.complete_url(signed_upload["attachment_id"]),
            {
                "device_id": str(signed_upload["device"].id),
                "ciphertext_sha256": "a" * 64,
                "ciphertext_size": 4097,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_complete_rejects_invalid_sha256(self):
        signed_upload = self.create_signed_upload()

        response = self.client.post(
            self.complete_url(signed_upload["attachment_id"]),
            {
                "device_id": str(signed_upload["device"].id),
                "ciphertext_sha256": "z" * 64,
                "ciphertext_size": 4096,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @override_settings(
        ATTACHMENT_VERIFY_CLOUDINARY_ON_COMPLETE=True,
    )
    @patch(
        "apps.chat_messages.attachment_services."
        "verify_cloudinary_raw_attachment"
    )
    def test_optional_cloudinary_verification_success_path(
        self,
        mocked_verify,
    ):
        mocked_verify.return_value = {
            "asset_id": "cloudinary-asset-id",
            "version": "123456",
        }

        signed_upload = self.create_signed_upload()

        response = self.client.post(
            self.complete_url(signed_upload["attachment_id"]),
            {
                "device_id": str(signed_upload["device"].id),
                "ciphertext_sha256": "a" * 64,
                "ciphertext_size": 4096,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        mocked_verify.assert_called_once()

        attachment = EncryptedAttachment.objects.get(
            id=signed_upload["attachment_id"]
        )

        self.assertEqual(
            attachment.cloudinary_asset_id,
            "cloudinary-asset-id",
        )
        self.assertEqual(attachment.cloudinary_version, "123456")
        self.assertIsNotNone(attachment.upload_completed_verified_at)

    @override_settings(
        ATTACHMENT_VERIFY_CLOUDINARY_ON_COMPLETE=True,
    )
    @patch(
        "apps.chat_messages.attachment_services."
        "verify_cloudinary_raw_attachment"
    )
    def test_optional_cloudinary_verification_failure_path(
        self,
        mocked_verify,
    ):
        mocked_verify.side_effect = CloudinaryAttachmentVerificationError(
            "Cloudinary asset byte size does not match ciphertext_size."
        )

        signed_upload = self.create_signed_upload()

        response = self.client.post(
            self.complete_url(signed_upload["attachment_id"]),
            {
                "device_id": str(signed_upload["device"].id),
                "ciphertext_sha256": "a" * 64,
                "ciphertext_size": 4096,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

        attachment = EncryptedAttachment.objects.get(
            id=signed_upload["attachment_id"]
        )

        self.assertEqual(
            attachment.upload_status,
            EncryptedAttachment.UploadStatus.INITIATED,
        )
        self.assertFalse(attachment.ciphertext_sha256)

    @override_settings(
        ATTACHMENT_VERIFY_CLOUDINARY_ON_COMPLETE=True,
    )
    @patch(
        "apps.chat_messages.attachment_services."
        "verify_cloudinary_raw_attachment"
    )
    def test_optional_cloudinary_configuration_failure_path(
        self,
        mocked_verify,
    ):
        mocked_verify.side_effect = CloudinaryAttachmentConfigurationError(
            "Could not verify Cloudinary encrypted attachment upload."
        )

        signed_upload = self.create_signed_upload()

        response = self.client.post(
            self.complete_url(signed_upload["attachment_id"]),
            {
                "device_id": str(signed_upload["device"].id),
                "ciphertext_sha256": "a" * 64,
                "ciphertext_size": 4096,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_503_SERVICE_UNAVAILABLE,
        )

        attachment = EncryptedAttachment.objects.get(
            id=signed_upload["attachment_id"]
        )

        self.assertEqual(
            attachment.upload_status,
            EncryptedAttachment.UploadStatus.INITIATED,
        )
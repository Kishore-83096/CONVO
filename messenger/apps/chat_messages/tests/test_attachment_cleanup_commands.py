import uuid
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.chat_messages.models import EncryptedAttachment
from apps.chat_messages.tests.test_encrypted_attachments_api import create_device
from apps.group_chat.tests.factories import GROUP_OWNER_USER_ID


def create_attachment(
    *,
    status_value,
    device,
    storage_key=None,
    completed_at=None,
    upload_signature_expires_at=None,
    expires_at=None,
    attached_message=None,
    attached_room=None,
):
    return EncryptedAttachment.objects.create(
        uploader_user_id=GROUP_OWNER_USER_ID,
        uploader_device=device,
        storage_provider=EncryptedAttachment.StorageProvider.CLOUDINARY,
        storage_key=storage_key
        or f"myna/test/attachments/{GROUP_OWNER_USER_ID}/{device.id}/{uuid.uuid4()}",
        resource_type="raw",
        ciphertext_size_hint=4096,
        ciphertext_sha256=(
            "a" * 64
            if status_value
            in {
                EncryptedAttachment.UploadStatus.COMPLETED,
                EncryptedAttachment.UploadStatus.ATTACHED,
                EncryptedAttachment.UploadStatus.DELETED,
                EncryptedAttachment.UploadStatus.EXPIRED,
            }
            else ""
        ),
        ciphertext_size=(
            4096
            if status_value
            in {
                EncryptedAttachment.UploadStatus.COMPLETED,
                EncryptedAttachment.UploadStatus.ATTACHED,
                EncryptedAttachment.UploadStatus.DELETED,
                EncryptedAttachment.UploadStatus.EXPIRED,
            }
            else 0
        ),
        media_category=EncryptedAttachment.MediaCategory.FILE,
        upload_status=status_value,
        completed_at=completed_at,
        upload_signature_expires_at=upload_signature_expires_at,
        expires_at=expires_at,
        attached_message=attached_message,
        attached_room=attached_room,
    )


@override_settings(
    CLOUDINARY_URL="cloudinary://public-api-key:private-api-secret@test-cloud",
    CLOUDINARY_FOLDER="myna/test/attachments",
    ATTACHMENT_CLOUDINARY_RESOURCE_TYPE="raw",
    ATTACHMENT_CLEANUP_DELETE_CLOUDINARY=False,
    ATTACHMENT_UNATTACHED_GRACE_HOURS=24,
)
class AttachmentCleanupCommandTests(TestCase):
    def setUp(self):
        self.device = create_device(
            user_id=GROUP_OWNER_USER_ID,
        )

    def test_cleanup_initiated_marks_expired_uploads_expired(self):
        expired_signature_attachment = create_attachment(
            status_value=EncryptedAttachment.UploadStatus.INITIATED,
            device=self.device,
            upload_signature_expires_at=timezone.now()
            - timedelta(minutes=1),
        )

        recent_attachment = create_attachment(
            status_value=EncryptedAttachment.UploadStatus.INITIATED,
            device=self.device,
            upload_signature_expires_at=timezone.now()
            + timedelta(minutes=10),
        )

        stdout = StringIO()

        call_command(
            "cleanup_initiated_attachments",
            "--limit",
            "100",
            stdout=stdout,
        )

        expired_signature_attachment.refresh_from_db()
        recent_attachment.refresh_from_db()

        self.assertEqual(
            expired_signature_attachment.upload_status,
            EncryptedAttachment.UploadStatus.EXPIRED,
        )
        self.assertEqual(
            recent_attachment.upload_status,
            EncryptedAttachment.UploadStatus.INITIATED,
        )
        self.assertIn(
            "attempted=1",
            stdout.getvalue(),
        )
        self.assertIn(
            "expired=1",
            stdout.getvalue(),
        )

    def test_cleanup_unattached_completed_expires_old_unattached_rows(self):
        old_completed = create_attachment(
            status_value=EncryptedAttachment.UploadStatus.COMPLETED,
            device=self.device,
            completed_at=timezone.now() - timedelta(hours=30),
        )

        recent_completed = create_attachment(
            status_value=EncryptedAttachment.UploadStatus.COMPLETED,
            device=self.device,
            completed_at=timezone.now() - timedelta(hours=1),
        )

        stdout = StringIO()

        call_command(
            "cleanup_unattached_completed_attachments",
            "--older-than-hours",
            "24",
            "--limit",
            "100",
            stdout=stdout,
        )

        old_completed.refresh_from_db()
        recent_completed.refresh_from_db()

        self.assertEqual(
            old_completed.upload_status,
            EncryptedAttachment.UploadStatus.EXPIRED,
        )
        self.assertEqual(
            recent_completed.upload_status,
            EncryptedAttachment.UploadStatus.COMPLETED,
        )
        self.assertIn(
            "attempted=1",
            stdout.getvalue(),
        )
        self.assertIn(
            "expired=1",
            stdout.getvalue(),
        )

    @override_settings(
        ATTACHMENT_CLEANUP_DELETE_CLOUDINARY=True,
    )
    @patch(
        "apps.chat_messages.management.commands.cleanup_initiated_attachments."
        "destroy_cloudinary_raw_attachment"
    )
    def test_cleanup_initiated_calls_cloudinary_destroy_when_enabled(
        self,
        mocked_destroy,
    ):
        mocked_destroy.return_value = {
            "result": "ok",
        }

        create_attachment(
            status_value=EncryptedAttachment.UploadStatus.INITIATED,
            device=self.device,
            upload_signature_expires_at=timezone.now()
            - timedelta(minutes=1),
        )

        stdout = StringIO()

        call_command(
            "cleanup_initiated_attachments",
            "--limit",
            "100",
            stdout=stdout,
        )

        mocked_destroy.assert_called_once()

        self.assertIn(
            "cloudinary_deleted=1",
            stdout.getvalue(),
        )

    @override_settings(
        ATTACHMENT_CLEANUP_DELETE_CLOUDINARY=False,
    )
    def test_cleanup_deleted_cloudinary_skips_when_disabled(self):
        create_attachment(
            status_value=EncryptedAttachment.UploadStatus.DELETED,
            device=self.device,
            completed_at=timezone.now() - timedelta(hours=1),
            expires_at=timezone.now(),
        )

        stdout = StringIO()

        call_command(
            "cleanup_deleted_cloudinary_attachments",
            "--limit",
            "100",
            stdout=stdout,
        )

        self.assertIn(
            "Cloudinary deletion is disabled",
            stdout.getvalue(),
        )

    @override_settings(
        ATTACHMENT_CLEANUP_DELETE_CLOUDINARY=True,
    )
    @patch(
        "apps.chat_messages.management.commands."
        "cleanup_deleted_cloudinary_attachments."
        "destroy_cloudinary_raw_attachment"
    )
    def test_cleanup_deleted_cloudinary_calls_destroy_when_enabled(
        self,
        mocked_destroy,
    ):
        mocked_destroy.return_value = {
            "result": "ok",
        }

        attachment = create_attachment(
            status_value=EncryptedAttachment.UploadStatus.DELETED,
            device=self.device,
            completed_at=timezone.now() - timedelta(hours=1),
            expires_at=timezone.now(),
        )

        stdout = StringIO()

        call_command(
            "cleanup_deleted_cloudinary_attachments",
            "--limit",
            "100",
            stdout=stdout,
        )

        mocked_destroy.assert_called_once_with(
            public_id=attachment.storage_key,
        )

        self.assertIn(
            "cloudinary_deleted=1",
            stdout.getvalue(),
        )
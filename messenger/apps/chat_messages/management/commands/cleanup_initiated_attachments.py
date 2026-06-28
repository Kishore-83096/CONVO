from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.chat_messages.cloudinary_attachment_services import (
    CloudinaryAttachmentConfigurationError,
    destroy_cloudinary_raw_attachment,
)
from apps.chat_messages.models import EncryptedAttachment


class Command(BaseCommand):
    help = (
        "Mark initiated encrypted attachments as expired after their "
        "signed upload payload expires."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=100,
            help="Maximum number of attachments to process.",
        )

    def handle(self, *args, **options):
        limit = max(1, int(options["limit"]))
        now = timezone.now()

        queryset = (
            EncryptedAttachment.objects.filter(
                upload_status=EncryptedAttachment.UploadStatus.INITIATED,
                upload_signature_expires_at__isnull=False,
                upload_signature_expires_at__lt=now,
            )
            .order_by("upload_signature_expires_at", "created_at")[:limit]
        )

        attempted = 0
        expired = 0
        cloudinary_deleted = 0
        failed = 0

        delete_cloudinary = bool(
            getattr(
                settings,
                "ATTACHMENT_CLEANUP_DELETE_CLOUDINARY",
                False,
            )
        )

        for attachment in queryset:
            attempted += 1
            error_message = ""

            if delete_cloudinary:
                try:
                    destroy_cloudinary_raw_attachment(
                        public_id=attachment.storage_key,
                    )
                    cloudinary_deleted += 1
                except CloudinaryAttachmentConfigurationError as error:
                    failed += 1
                    error_message = str(error)

            attachment.upload_status = EncryptedAttachment.UploadStatus.EXPIRED
            attachment.expires_at = (
                attachment.expires_at
                or attachment.upload_signature_expires_at
                or now
            )
            attachment.last_cloudinary_error = error_message

            attachment.save(
                update_fields=[
                    "upload_status",
                    "expires_at",
                    "last_cloudinary_error",
                ]
            )

            expired += 1

        self.stdout.write(
            self.style.SUCCESS(
                "cleanup_initiated_attachments complete: "
                f"attempted={attempted}, "
                f"expired={expired}, "
                f"cloudinary_deleted={cloudinary_deleted}, "
                f"failed={failed}"
            )
        )
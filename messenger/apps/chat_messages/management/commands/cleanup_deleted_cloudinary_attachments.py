from django.conf import settings
from django.core.management.base import BaseCommand

from apps.chat_messages.cloudinary_attachment_services import (
    CloudinaryAttachmentConfigurationError,
    destroy_cloudinary_raw_attachment,
)
from apps.chat_messages.models import EncryptedAttachment


class Command(BaseCommand):
    help = (
        "Destroy Cloudinary assets for deleted or expired encrypted "
        "attachments when Cloudinary cleanup is enabled."
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

        delete_cloudinary = bool(
            getattr(
                settings,
                "ATTACHMENT_CLEANUP_DELETE_CLOUDINARY",
                False,
            )
        )

        if not delete_cloudinary:
            self.stdout.write(
                self.style.WARNING(
                    "Cloudinary deletion is disabled. Set "
                    "ATTACHMENT_CLEANUP_DELETE_CLOUDINARY=True to enable it."
                )
            )
            return

        queryset = (
            EncryptedAttachment.objects.filter(
                upload_status__in=[
                    EncryptedAttachment.UploadStatus.DELETED,
                    EncryptedAttachment.UploadStatus.EXPIRED,
                ],
                storage_provider=EncryptedAttachment.StorageProvider.CLOUDINARY,
            )
            .exclude(
                storage_key="",
            )
            .order_by("created_at")[:limit]
        )

        attempted = 0
        cloudinary_deleted = 0
        failed = 0

        for attachment in queryset:
            attempted += 1

            try:
                destroy_cloudinary_raw_attachment(
                    public_id=attachment.storage_key,
                )
            except CloudinaryAttachmentConfigurationError as error:
                failed += 1
                attachment.last_cloudinary_error = str(error)
                attachment.save(
                    update_fields=[
                        "last_cloudinary_error",
                    ]
                )
                continue

            cloudinary_deleted += 1
            attachment.last_cloudinary_error = ""
            attachment.save(
                update_fields=[
                    "last_cloudinary_error",
                ]
            )

        self.stdout.write(
            self.style.SUCCESS(
                "cleanup_deleted_cloudinary_attachments complete: "
                f"attempted={attempted}, "
                f"cloudinary_deleted={cloudinary_deleted}, "
                f"failed={failed}"
            )
        )
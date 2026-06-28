from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.e2ee_devices.models import Device

from .models import EncryptedAttachment


class AttachmentServiceError(Exception):
    """Base encrypted attachment error."""


class AttachmentValidationError(AttachmentServiceError):
    """Invalid attachment input."""


class AttachmentNotFoundError(AttachmentServiceError):
    """Attachment or device was not found."""


class AttachmentPermissionError(AttachmentServiceError):
    """User cannot access attachment."""


class AttachmentConflictError(AttachmentServiceError):
    """Attachment state conflict."""


@dataclass(frozen=True, slots=True)
class AttachmentDownloadResult:
    attachment: EncryptedAttachment


def _normalize_user_id(
    value: Any,
    *,
    field_name: str,
) -> str:
    user_id = str(value).strip()

    if not user_id:
        raise AttachmentValidationError(f"{field_name} is required.")

    return user_id


def _owned_active_device(
    *,
    device_id,
    user_id: str,
) -> Device:
    try:
        device_uuid = UUID(str(device_id))
    except (TypeError, ValueError, AttributeError) as error:
        raise AttachmentValidationError(
            "device_id must be a valid UUID."
        ) from error

    device = Device.objects.filter(
        id=device_uuid,
        user_id=user_id,
        is_active=True,
    ).first()

    if device is None:
        raise AttachmentNotFoundError("Device was not found.")

    return device


def _get_attachment_for_owner(
    *,
    attachment_id,
    user_id: str,
) -> EncryptedAttachment:
    try:
        attachment_uuid = UUID(str(attachment_id))
    except (TypeError, ValueError, AttributeError) as error:
        raise AttachmentValidationError(
            "attachment_id must be a valid UUID."
        ) from error

    attachment = EncryptedAttachment.objects.select_for_update().filter(
        id=attachment_uuid,
        uploader_user_id=user_id,
    ).first()

    if attachment is None:
        raise AttachmentNotFoundError("Attachment was not found.")

    return attachment


def _validate_storage_key(storage_key: str) -> str:
    normalized = str(storage_key or "").strip()

    forbidden_fragments = (
        "plaintext",
        "private",
        "secret",
        "raw_key",
        "attachment_key",
    )

    lowered = normalized.lower()

    if any(fragment in lowered for fragment in forbidden_fragments):
        raise AttachmentValidationError(
            "storage_key must not contain plaintext or secret material."
        )

    return normalized


@transaction.atomic
def initiate_encrypted_attachment(
    *,
    authenticated_user_id: Any,
    device_id,
    storage_provider: str = "cloudinary",
    storage_key: str = "",
    media_category: str = "file",
    expires_at=None,
) -> EncryptedAttachment:
    user_id = _normalize_user_id(
        authenticated_user_id,
        field_name="authenticated_user_id",
    )

    device = _owned_active_device(
        device_id=device_id,
        user_id=user_id,
    )

    normalized_storage_key = _validate_storage_key(storage_key)

    if not normalized_storage_key:
        normalized_storage_key = (
            f"encrypted-attachments/{user_id}/{uuid4()}"
        )

    attachment = EncryptedAttachment(
        uploader_user_id=user_id,
        uploader_device=device,
        storage_provider=storage_provider,
        storage_key=normalized_storage_key,
        media_category=media_category,
        upload_status=EncryptedAttachment.UploadStatus.INITIATED,
        expires_at=expires_at,
    )

    try:
        attachment.full_clean()
        attachment.save(force_insert=True)
    except DjangoValidationError as error:
        raise AttachmentValidationError(
            error.message_dict
            if hasattr(error, "message_dict")
            else str(error)
        ) from error
    except IntegrityError as error:
        raise AttachmentConflictError(
            "Could not initiate attachment because of a conflict."
        ) from error

    return attachment


@transaction.atomic
def complete_encrypted_attachment(
    *,
    authenticated_user_id: Any,
    attachment_id,
    device_id,
    ciphertext_sha256: str,
    ciphertext_size: int,
) -> EncryptedAttachment:
    user_id = _normalize_user_id(
        authenticated_user_id,
        field_name="authenticated_user_id",
    )

    device = _owned_active_device(
        device_id=device_id,
        user_id=user_id,
    )

    attachment = _get_attachment_for_owner(
        attachment_id=attachment_id,
        user_id=user_id,
    )

    if attachment.uploader_device_id != device.id:
        raise AttachmentPermissionError(
            "Only the upload device can complete this attachment."
        )

    if attachment.upload_status != EncryptedAttachment.UploadStatus.INITIATED:
        raise AttachmentConflictError(
            "Only initiated attachments can be completed."
        )

    attachment.ciphertext_sha256 = str(ciphertext_sha256).strip().lower()
    attachment.ciphertext_size = int(ciphertext_size)
    attachment.completed_at = timezone.now()
    attachment.upload_status = EncryptedAttachment.UploadStatus.COMPLETED

    try:
        attachment.full_clean()
        attachment.save(
            update_fields=[
                "ciphertext_sha256",
                "ciphertext_size",
                "completed_at",
                "upload_status",
            ]
        )
    except DjangoValidationError as error:
        raise AttachmentValidationError(
            error.message_dict
            if hasattr(error, "message_dict")
            else str(error)
        ) from error

    return attachment


@transaction.atomic
def get_encrypted_attachment_download(
    *,
    authenticated_user_id: Any,
    attachment_id,
    device_id,
) -> AttachmentDownloadResult:
    user_id = _normalize_user_id(
        authenticated_user_id,
        field_name="authenticated_user_id",
    )

    _owned_active_device(
        device_id=device_id,
        user_id=user_id,
    )

    attachment = _get_attachment_for_owner(
        attachment_id=attachment_id,
        user_id=user_id,
    )

    if attachment.upload_status != EncryptedAttachment.UploadStatus.COMPLETED:
        raise AttachmentConflictError(
            "Attachment is not completed."
        )

    if attachment.expires_at and attachment.expires_at <= timezone.now():
        attachment.upload_status = EncryptedAttachment.UploadStatus.EXPIRED
        attachment.save(update_fields=["upload_status"])

        raise AttachmentConflictError(
            "Attachment has expired."
        )

    return AttachmentDownloadResult(
        attachment=attachment,
    )


@transaction.atomic
def delete_encrypted_attachment(
    *,
    authenticated_user_id: Any,
    attachment_id,
    device_id,
) -> EncryptedAttachment:
    user_id = _normalize_user_id(
        authenticated_user_id,
        field_name="authenticated_user_id",
    )

    _owned_active_device(
        device_id=device_id,
        user_id=user_id,
    )

    attachment = _get_attachment_for_owner(
        attachment_id=attachment_id,
        user_id=user_id,
    )

    if attachment.upload_status == EncryptedAttachment.UploadStatus.DELETED:
        return attachment

    attachment.upload_status = EncryptedAttachment.UploadStatus.DELETED
    attachment.save(update_fields=["upload_status"])

    return attachment
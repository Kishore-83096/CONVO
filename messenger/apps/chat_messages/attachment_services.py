from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4
from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.e2ee_devices.models import Device
from apps.group_chat.models import GroupProfile
from apps.rooms.models import Room, RoomMember

from .models import (
    EncryptedAttachment,
    MessageKeyEnvelope,
)
from .cloudinary_attachment_services import (
    CloudinaryAttachmentConfigurationError,
    CloudinaryAttachmentVerificationError,
    build_attachment_public_id,
    build_signed_download_payload,
    build_signed_upload_payload,
    clamp_upload_ttl,
    verify_cloudinary_raw_attachment,
)



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

class AttachmentStorageConfigurationError(AttachmentServiceError):
    """Attachment storage provider is not configured correctly."""

@transaction.atomic
def create_signed_cloudinary_attachment_upload(
    *,
    authenticated_user_id: Any,
    device_id,
    media_category: str = "file",
    ciphertext_size_hint: int,
    expires_in_seconds: int | None = None,
) -> dict:
    user_id = _normalize_user_id(
        authenticated_user_id,
        field_name="authenticated_user_id",
    )

    device = _owned_active_device(
        device_id=device_id,
        user_id=user_id,
    )

    try:
        ciphertext_size_hint = int(ciphertext_size_hint)
    except (TypeError, ValueError) as error:
        raise AttachmentValidationError(
            "ciphertext_size_hint must be an integer."
        ) from error

    max_ciphertext_bytes = int(
        getattr(
            __import__("django.conf").conf.settings,
            "ATTACHMENT_MAX_CIPHERTEXT_BYTES",
            50 * 1024 * 1024,
        )
    )

    if ciphertext_size_hint < 1:
        raise AttachmentValidationError(
            "ciphertext_size_hint must be greater than 0."
        )

    if ciphertext_size_hint > max_ciphertext_bytes:
        raise AttachmentValidationError(
            "ciphertext_size_hint exceeds the maximum allowed encrypted size."
        )

    try:
        ttl_seconds = clamp_upload_ttl(expires_in_seconds)
    except CloudinaryAttachmentConfigurationError as error:
        raise AttachmentStorageConfigurationError(str(error)) from error

    attachment = EncryptedAttachment(
        uploader_user_id=user_id,
        uploader_device=device,
        storage_provider=EncryptedAttachment.StorageProvider.CLOUDINARY,
        storage_key="temporary-storage-key",
        resource_type="raw",
        ciphertext_size_hint=ciphertext_size_hint,
        media_category=media_category,
        upload_status=EncryptedAttachment.UploadStatus.INITIATED,
    )

    attachment.storage_key = build_attachment_public_id(
        user_id=user_id,
        device_id=device.id,
        attachment_id=attachment.id,
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
            "Could not create signed attachment upload because of a conflict."
        ) from error

    try:
        payload = build_signed_upload_payload(
            attachment=attachment,
            ttl_seconds=ttl_seconds,
        )
    except CloudinaryAttachmentConfigurationError as error:
        raise AttachmentStorageConfigurationError(str(error)) from error

    attachment.upload_signature_expires_at = payload["expires_at"]
    attachment.expires_at = payload["expires_at"]

    try:
        attachment.full_clean()
        attachment.save(
            update_fields=[
                "upload_signature_expires_at",
                "expires_at",
            ]
        )
    except DjangoValidationError as error:
        raise AttachmentValidationError(
            error.message_dict
            if hasattr(error, "message_dict")
            else str(error)
        ) from error

    return {
        "attachment": attachment,
        "payload": payload,
    }






@dataclass(frozen=True, slots=True)
class AttachmentDownloadResult:
    attachment: EncryptedAttachment
    download_url: str
    expires_at: Any


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

    now = timezone.now()

    if (
        attachment.upload_signature_expires_at
        and attachment.upload_signature_expires_at <= now
    ):
        attachment.upload_status = EncryptedAttachment.UploadStatus.EXPIRED
        attachment.expires_at = (
            attachment.expires_at
            or attachment.upload_signature_expires_at
        )
        attachment.save(
            update_fields=[
                "upload_status",
                "expires_at",
            ]
        )

        raise AttachmentConflictError(
            "Attachment upload signature has expired."
        )

    try:
        ciphertext_size = int(ciphertext_size)
    except (TypeError, ValueError) as error:
        raise AttachmentValidationError(
            "ciphertext_size must be an integer."
        ) from error

    max_ciphertext_bytes = int(
        getattr(
            settings,
            "ATTACHMENT_MAX_CIPHERTEXT_BYTES",
            50 * 1024 * 1024,
        )
    )

    if ciphertext_size < 1:
        raise AttachmentValidationError(
            "ciphertext_size must be greater than 0."
        )

    if ciphertext_size > max_ciphertext_bytes:
        raise AttachmentValidationError(
            "ciphertext_size exceeds the maximum allowed encrypted size."
        )

    if (
        attachment.ciphertext_size_hint
        and ciphertext_size > attachment.ciphertext_size_hint
    ):
        raise AttachmentValidationError(
            "ciphertext_size exceeds the original ciphertext_size_hint."
        )

    normalized_sha256 = str(ciphertext_sha256 or "").strip().lower()

    is_valid_sha256 = (
        len(normalized_sha256) == 64
        and all(
            character in "0123456789abcdef"
            for character in normalized_sha256
        )
    )

    if not is_valid_sha256:
        raise AttachmentValidationError(
            "ciphertext_sha256 must be a 64-character lowercase hex digest."
        )

    verified_cloudinary_asset_id = ""
    verified_cloudinary_version = ""
    upload_completed_verified_at = None

    if bool(
        getattr(
            settings,
            "ATTACHMENT_VERIFY_CLOUDINARY_ON_COMPLETE",
            False,
        )
    ):
        try:
            verification_result = verify_cloudinary_raw_attachment(
                public_id=attachment.storage_key,
                expected_size=ciphertext_size,
            )
        except CloudinaryAttachmentVerificationError as error:
            raise AttachmentConflictError(str(error)) from error
        except CloudinaryAttachmentConfigurationError as error:
            raise AttachmentStorageConfigurationError(str(error)) from error

        verified_cloudinary_asset_id = verification_result.get(
            "asset_id",
            "",
        )
        verified_cloudinary_version = verification_result.get(
            "version",
            "",
        )
        upload_completed_verified_at = now

    attachment.ciphertext_sha256 = normalized_sha256
    attachment.ciphertext_size = ciphertext_size
    attachment.completed_at = now
    attachment.upload_status = EncryptedAttachment.UploadStatus.COMPLETED

    if upload_completed_verified_at:
        attachment.upload_completed_verified_at = upload_completed_verified_at
        attachment.cloudinary_asset_id = verified_cloudinary_asset_id
        attachment.cloudinary_version = verified_cloudinary_version

    try:
        attachment.full_clean()

        with transaction.atomic():
            attachment.save(
                update_fields=[
                    "ciphertext_sha256",
                    "ciphertext_size",
                    "completed_at",
                    "upload_status",
                    "upload_completed_verified_at",
                    "cloudinary_asset_id",
                    "cloudinary_version",
                ]
            )
    except DjangoValidationError as error:
        raise AttachmentValidationError(
            error.message_dict
            if hasattr(error, "message_dict")
            else str(error)
        ) from error

    return attachment

def _get_attachment_by_id(
    *,
    attachment_id,
) -> EncryptedAttachment:
    try:
        attachment_uuid = UUID(str(attachment_id))
    except (TypeError, ValueError, AttributeError) as error:
        raise AttachmentValidationError(
            "attachment_id must be a valid UUID."
        ) from error

    attachment = (
        EncryptedAttachment.objects.select_related(
            "uploader_device",
            "attached_room",
            "attached_message",
        )
        .filter(
            id=attachment_uuid,
        )
        .first()
    )

    if attachment is None:
        raise AttachmentNotFoundError("Attachment was not found.")

    return attachment


def _is_attachment_expired(
    *,
    attachment: EncryptedAttachment,
    now,
) -> bool:
    if attachment.upload_status == EncryptedAttachment.UploadStatus.EXPIRED:
        return True

    if attachment.expires_at and attachment.expires_at <= now:
        attachment.upload_status = EncryptedAttachment.UploadStatus.EXPIRED
        attachment.save(
            update_fields=[
                "upload_status",
            ]
        )
        return True

    return False


def _direct_user_can_download_attachment(
    *,
    user_id: str,
    device: Device,
    attachment: EncryptedAttachment,
) -> bool:
    if not attachment.attached_room_id or not attachment.attached_message_id:
        return False

    is_room_member = RoomMember.objects.filter(
        room=attachment.attached_room,
        user_id=user_id,
        is_active=True,
    ).exists()

    if not is_room_member:
        return False

    return MessageKeyEnvelope.objects.filter(
        message=attachment.attached_message,
        recipient_user_id=user_id,
        recipient_device=device,
    ).exists()


def _group_user_can_download_attachment(
    *,
    user_id: str,
    attachment: EncryptedAttachment,
) -> bool:
    if not attachment.attached_room_id or not attachment.attached_message_id:
        return False

    membership = RoomMember.objects.filter(
        room=attachment.attached_room,
        user_id=user_id,
        is_active=True,
    ).first()

    if membership is None:
        return False

    if (
        membership.joined_at
        and attachment.attached_message.created_at
        and membership.joined_at > attachment.attached_message.created_at
    ):
        profile = GroupProfile.objects.filter(
            room=attachment.attached_room,
        ).first()

        if profile is None or not profile.join_history_visible:
            return False

    return True


def can_user_download_attachment(
    *,
    user_id: str,
    device: Device,
    attachment: EncryptedAttachment,
) -> bool:
    if user_id == attachment.uploader_user_id:
        return True

    if not attachment.attached_room_id or not attachment.attached_message_id:
        return False

    room = attachment.attached_room

    if room.room_type == Room.RoomType.DIRECT:
        return _direct_user_can_download_attachment(
            user_id=user_id,
            device=device,
            attachment=attachment,
        )

    if room.room_type == Room.RoomType.GROUP:
        return _group_user_can_download_attachment(
            user_id=user_id,
            attachment=attachment,
        )

    return False


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

    device = _owned_active_device(
        device_id=device_id,
        user_id=user_id,
    )

    attachment = _get_attachment_by_id(
        attachment_id=attachment_id,
    )

    now = timezone.now()

    if attachment.upload_status == EncryptedAttachment.UploadStatus.DELETED:
        raise AttachmentConflictError(
            "Deleted attachments cannot be downloaded."
        )

    if _is_attachment_expired(
        attachment=attachment,
        now=now,
    ):
        raise AttachmentConflictError(
            "Expired attachments cannot be downloaded."
        )

    allowed_download_statuses = {
        EncryptedAttachment.UploadStatus.COMPLETED,
        EncryptedAttachment.UploadStatus.ATTACHED,
    }

    if attachment.upload_status not in allowed_download_statuses:
        raise AttachmentConflictError(
            "Attachment is not ready for download."
        )

    if not can_user_download_attachment(
        user_id=user_id,
        device=device,
        attachment=attachment,
    ):
        raise AttachmentPermissionError(
            "You are not allowed to download this attachment."
        )

    try:
        signed_download = build_signed_download_payload(
            public_id=attachment.storage_key,
        )
    except CloudinaryAttachmentConfigurationError as error:
        raise AttachmentStorageConfigurationError(str(error)) from error

    return AttachmentDownloadResult(
        attachment=attachment,
        download_url=signed_download["download_url"],
        expires_at=signed_download["expires_at"],
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





MAX_ATTACHMENTS_PER_MESSAGE = 10


def normalize_attachment_ids(
    attachment_ids,
) -> list[UUID]:
    if attachment_ids is None:
        return []

    if not isinstance(attachment_ids, list):
        raise AttachmentValidationError(
            "attachment_ids must be a list."
        )

    if len(attachment_ids) > MAX_ATTACHMENTS_PER_MESSAGE:
        raise AttachmentValidationError(
            f"A maximum of {MAX_ATTACHMENTS_PER_MESSAGE} "
            "attachments can be linked to one message."
        )

    normalized_ids = []

    for attachment_id in attachment_ids:
        try:
            normalized_ids.append(UUID(str(attachment_id)))
        except (TypeError, ValueError, AttributeError) as error:
            raise AttachmentValidationError(
                "Every attachment_id must be a valid UUID."
            ) from error

    if len(normalized_ids) != len(set(normalized_ids)):
        raise AttachmentValidationError(
            "Duplicate attachment_ids are not allowed."
        )

    return normalized_ids


def get_message_attachment_id_strings(
    *,
    message,
) -> set[str]:
    return {
        str(attachment_id)
        for attachment_id in EncryptedAttachment.objects.filter(
            attached_message=message,
        ).values_list(
            "id",
            flat=True,
        )
    }


def validate_idempotent_message_attachments(
    *,
    message,
    attachment_ids,
) -> None:
    requested_ids = {
        str(attachment_id)
        for attachment_id in normalize_attachment_ids(
            attachment_ids,
        )
    }

    existing_ids = get_message_attachment_id_strings(
        message=message,
    )

    if requested_ids != existing_ids:
        raise AttachmentConflictError(
            "This client_message_id was already used with different "
            "attachment_ids."
        )


def validate_and_attach_message_attachments(
    *,
    authenticated_user_id: Any,
    sender_device_id,
    room,
    message,
    attachment_ids,
) -> list[EncryptedAttachment]:
    normalized_ids = normalize_attachment_ids(
        attachment_ids,
    )

    if not normalized_ids:
        return []

    user_id = _normalize_user_id(
        authenticated_user_id,
        field_name="authenticated_user_id",
    )

    try:
        sender_device_uuid = UUID(str(sender_device_id))
    except (TypeError, ValueError, AttributeError) as error:
        raise AttachmentValidationError(
            "sender_device_id must be a valid UUID."
        ) from error

    attachments = list(
        EncryptedAttachment.objects.select_for_update().filter(
            id__in=normalized_ids,
        )
    )

    attachments_by_id = {
        attachment.id: attachment
        for attachment in attachments
    }

    missing_ids = [
        str(attachment_id)
        for attachment_id in normalized_ids
        if attachment_id not in attachments_by_id
    ]

    if missing_ids:
        raise AttachmentNotFoundError(
            f"Attachment was not found: {missing_ids[0]}"
        )

    now = timezone.now()
    linked_attachments = []

    for attachment_id in normalized_ids:
        attachment = attachments_by_id[attachment_id]

        if attachment.uploader_user_id != user_id:
            raise AttachmentPermissionError(
                "Attachment does not belong to the authenticated user."
            )

        if attachment.uploader_device_id != sender_device_uuid:
            raise AttachmentPermissionError(
                "Attachment was uploaded by a different device."
            )

        if attachment.upload_status != EncryptedAttachment.UploadStatus.COMPLETED:
            raise AttachmentConflictError(
                "Only completed attachments can be linked to a message."
            )

        if attachment.deleted_at:
            raise AttachmentConflictError(
                "Deleted attachments cannot be linked to a message."
            )

        if (
            attachment.expires_at
            and attachment.expires_at <= now
        ):
            attachment.upload_status = EncryptedAttachment.UploadStatus.EXPIRED
            attachment.save(
                update_fields=[
                    "upload_status",
                ]
            )

            raise AttachmentConflictError(
                "Expired attachments cannot be linked to a message."
            )

        if attachment.attached_message_id or attachment.attached_room_id:
            raise AttachmentConflictError(
                "Attachment is already linked to another message."
            )

        if not attachment.ciphertext_sha256 or attachment.ciphertext_size < 1:
            raise AttachmentConflictError(
                "Attachment must have ciphertext hash and size before linking."
            )

        attachment.attached_room = room
        attachment.attached_message = message
        attachment.attached_at = now
        attachment.upload_status = EncryptedAttachment.UploadStatus.ATTACHED

        try:
            attachment.full_clean()
        except DjangoValidationError as error:
            raise AttachmentValidationError(
                error.message_dict
                if hasattr(error, "message_dict")
                else str(error)
            ) from error

        linked_attachments.append(attachment)

    for attachment in linked_attachments:
        attachment.save(
            update_fields=[
                "attached_room",
                "attached_message",
                "attached_at",
                "upload_status",
            ]
        )

    return linked_attachments

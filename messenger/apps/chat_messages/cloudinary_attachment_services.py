import re
import cloudinary
import cloudinary.api
import cloudinary.uploader
from dataclasses import dataclass
from datetime import timedelta
from typing import Any
from urllib.parse import unquote, urlparse

from cloudinary.utils import api_sign_request, cloudinary_url
from django.conf import settings
from django.utils import timezone


class CloudinaryAttachmentConfigurationError(Exception):
    """
    Raised when Cloudinary signing cannot be safely performed.
    """


class CloudinaryAttachmentVerificationError(Exception):
    """
    Raised when Cloudinary says the uploaded encrypted blob does not match
    the backend attachment metadata.
    """

@dataclass(frozen=True, slots=True)
class CloudinaryAttachmentConfig:
    cloud_name: str
    api_key: str
    api_secret: str


_SAFE_SEGMENT_PATTERN = re.compile(r"[^A-Za-z0-9_.=-]+")


def _safe_path_segment(
    value: Any,
    *,
    field_name: str,
) -> str:
    """
    Convert user/device/attachment identifiers into safe Cloudinary path segments.

    This prevents folder traversal or frontend-controlled folder injection.
    """

    normalized = str(value or "").strip()
    normalized = normalized.replace("\\", "/")
    normalized = normalized.strip("/")
    normalized = normalized.replace("..", "")
    normalized = _SAFE_SEGMENT_PATTERN.sub("_", normalized)
    normalized = normalized.strip("._-/")

    if not normalized:
        raise CloudinaryAttachmentConfigurationError(
            f"{field_name} could not be converted into a safe path segment."
        )

    return normalized[:120]


def _normalized_cloudinary_folder() -> str:
    folder = str(
        getattr(settings, "CLOUDINARY_FOLDER", "")
    ).strip().strip("/")

    if not folder:
        raise CloudinaryAttachmentConfigurationError(
            "CLOUDINARY_FOLDER must not be empty."
        )

    safe_parts = [
        _safe_path_segment(
            part,
            field_name="CLOUDINARY_FOLDER",
        )
        for part in folder.split("/")
        if part.strip()
    ]

    if not safe_parts:
        raise CloudinaryAttachmentConfigurationError(
            "CLOUDINARY_FOLDER must contain at least one safe path segment."
        )

    return "/".join(safe_parts)


def get_cloudinary_config() -> CloudinaryAttachmentConfig:
    cloudinary_url = str(
        getattr(settings, "CLOUDINARY_URL", "")
    ).strip()

    if not cloudinary_url:
        raise CloudinaryAttachmentConfigurationError(
            "CLOUDINARY_URL is not configured."
        )

    parsed_cloudinary_url = urlparse(cloudinary_url)

    if (
        parsed_cloudinary_url.scheme != "cloudinary"
        or not parsed_cloudinary_url.hostname
        or not parsed_cloudinary_url.username
        or not parsed_cloudinary_url.password
    ):
        raise CloudinaryAttachmentConfigurationError(
            "CLOUDINARY_URL must use the format "
            "cloudinary://API_KEY:API_SECRET@CLOUD_NAME"
        )

    return CloudinaryAttachmentConfig(
        cloud_name=parsed_cloudinary_url.hostname,
        api_key=unquote(parsed_cloudinary_url.username),
        api_secret=unquote(parsed_cloudinary_url.password),
    )


def get_attachment_resource_type() -> str:
    resource_type = str(
        getattr(settings, "ATTACHMENT_CLOUDINARY_RESOURCE_TYPE", "raw")
    ).strip()

    if resource_type != "raw":
        raise CloudinaryAttachmentConfigurationError(
            "Encrypted attachments must use Cloudinary resource_type='raw'."
        )

    return resource_type


def clamp_upload_ttl(
    expires_in_seconds: int | None,
) -> int:
    min_ttl = int(
        getattr(settings, "ATTACHMENT_MIN_TTL_SECONDS", 60)
    )
    max_ttl = int(
        getattr(settings, "ATTACHMENT_UPLOAD_MAX_TTL_SECONDS", 900)
    )
    default_ttl = int(
        getattr(settings, "ATTACHMENT_UPLOAD_SIGNATURE_TTL_SECONDS", 900)
    )

    if min_ttl < 1:
        raise CloudinaryAttachmentConfigurationError(
            "ATTACHMENT_MIN_TTL_SECONDS must be at least 1."
        )

    if max_ttl > 900:
        raise CloudinaryAttachmentConfigurationError(
            "ATTACHMENT_UPLOAD_MAX_TTL_SECONDS must not exceed 900."
        )

    if min_ttl > max_ttl:
        raise CloudinaryAttachmentConfigurationError(
            "ATTACHMENT_MIN_TTL_SECONDS must not exceed "
            "ATTACHMENT_UPLOAD_MAX_TTL_SECONDS."
        )

    if default_ttl > max_ttl:
        raise CloudinaryAttachmentConfigurationError(
            "ATTACHMENT_UPLOAD_SIGNATURE_TTL_SECONDS must not exceed "
            "ATTACHMENT_UPLOAD_MAX_TTL_SECONDS."
        )

    requested_ttl = default_ttl

    if expires_in_seconds is not None:
        try:
            requested_ttl = int(expires_in_seconds)
        except (TypeError, ValueError) as error:
            raise CloudinaryAttachmentConfigurationError(
                "expires_in_seconds must be an integer."
            ) from error

    return max(
        min_ttl,
        min(requested_ttl, max_ttl),
    )


def build_attachment_folder(
    *,
    user_id: Any,
    device_id: Any,
) -> str:
    base_folder = _normalized_cloudinary_folder()

    safe_user_id = _safe_path_segment(
        user_id,
        field_name="user_id",
    )
    safe_device_id = _safe_path_segment(
        device_id,
        field_name="device_id",
    )

    return f"{base_folder}/{safe_user_id}/{safe_device_id}"


def build_attachment_public_id(
    *,
    user_id: Any,
    device_id: Any,
    attachment_id: Any,
) -> str:
    folder = build_attachment_folder(
        user_id=user_id,
        device_id=device_id,
    )
    safe_attachment_id = _safe_path_segment(
        attachment_id,
        field_name="attachment_id",
    )

    return f"{folder}/{safe_attachment_id}"


def build_upload_url(
    *,
    cloud_name: str,
    resource_type: str,
) -> str:
    return (
        f"https://api.cloudinary.com/v1_1/"
        f"{cloud_name}/{resource_type}/upload"
    )


def sign_cloudinary_upload(
    *,
    public_id: str,
    timestamp: int,
) -> str:
    config = get_cloudinary_config()

    normalized_public_id = str(public_id or "").strip().strip("/")

    if not normalized_public_id:
        raise CloudinaryAttachmentConfigurationError(
            "public_id is required for Cloudinary upload signing."
        )

    return api_sign_request(
        {
            "public_id": normalized_public_id,
            "timestamp": int(timestamp),
        },
        config.api_secret,
    )


def build_signed_upload_payload(
    *,
    attachment,
    ttl_seconds: int | None = None,
) -> dict:
    """
    Build the payload React needs to upload encrypted bytes directly to Cloudinary.

    This function must never return api_secret.
    """

    config = get_cloudinary_config()
    resource_type = get_attachment_resource_type()
    ttl = clamp_upload_ttl(ttl_seconds)

    now = timezone.now()
    timestamp = int(now.timestamp())
    expires_at = now + timedelta(seconds=ttl)

    public_id = str(attachment.storage_key or "").strip().strip("/")

    if not public_id:
        raise CloudinaryAttachmentConfigurationError(
            "Attachment storage_key/public_id is required."
        )

    signature = sign_cloudinary_upload(
        public_id=public_id,
        timestamp=timestamp,
    )

    folder = public_id.rsplit("/", 1)[0] if "/" in public_id else ""

    return {
        "attachment_id": str(attachment.id),
        "storage_provider": str(attachment.storage_provider),
        "cloud_name": config.cloud_name,
        "api_key": config.api_key,
        "upload_url": build_upload_url(
            cloud_name=config.cloud_name,
            resource_type=resource_type,
        ),
        "resource_type": resource_type,
        "folder": folder,
        "public_id": public_id,
        "storage_key": public_id,
        "timestamp": timestamp,
        "signature": signature,
        "expires_at": expires_at,
        "metadata": {
            "attachment_id": str(attachment.id),
            "upload_preset": None,
        },
    }




def verify_cloudinary_raw_attachment(
    *,
    public_id: str,
    expected_size: int,
) -> dict:
    """
    Verify that the encrypted raw Cloudinary asset exists and its byte size
    matches the size reported by React.

    This does not verify plaintext. It only verifies Cloudinary metadata.
    The receiver client still verifies ciphertext_sha256 after download.
    """

    get_cloudinary_config()

    resource_type = get_attachment_resource_type()

    normalized_public_id = str(public_id or "").strip().strip("/")

    if not normalized_public_id:
        raise CloudinaryAttachmentVerificationError(
            "Cloudinary public_id is required for verification."
        )

    try:
        expected_size = int(expected_size)
    except (TypeError, ValueError) as error:
        raise CloudinaryAttachmentVerificationError(
            "Expected ciphertext size must be an integer."
        ) from error

    if expected_size < 1:
        raise CloudinaryAttachmentVerificationError(
            "Expected ciphertext size must be greater than 0."
        )

    try:
        resource = cloudinary.api.resource(
            normalized_public_id,
            resource_type=resource_type,
        )
    except Exception as error:
        raise CloudinaryAttachmentConfigurationError(
            "Could not verify Cloudinary encrypted attachment upload."
        ) from error

    returned_public_id = str(
        resource.get("public_id", "")
    ).strip().strip("/")

    if returned_public_id != normalized_public_id:
        raise CloudinaryAttachmentVerificationError(
            "Cloudinary public_id does not match attachment storage_key."
        )

    returned_resource_type = str(
        resource.get("resource_type", resource_type)
    ).strip()

    if returned_resource_type != "raw":
        raise CloudinaryAttachmentVerificationError(
            "Cloudinary resource_type must be raw for encrypted attachments."
        )

    returned_size = resource.get("bytes")

    if returned_size is None:
        raise CloudinaryAttachmentVerificationError(
            "Cloudinary response did not include asset byte size."
        )

    try:
        returned_size = int(returned_size)
    except (TypeError, ValueError) as error:
        raise CloudinaryAttachmentVerificationError(
            "Cloudinary asset byte size is invalid."
        ) from error

    if returned_size != expected_size:
        raise CloudinaryAttachmentVerificationError(
            "Cloudinary asset byte size does not match ciphertext_size."
        )

    return {
        "asset_id": str(resource.get("asset_id", "") or ""),
        "version": str(resource.get("version", "") or ""),
    }





def clamp_download_ttl(
    expires_in_seconds: int | None = None,
) -> int:
    max_ttl = int(
        getattr(settings, "ATTACHMENT_DOWNLOAD_URL_MAX_TTL_SECONDS", 900)
    )
    default_ttl = int(
        getattr(settings, "ATTACHMENT_DOWNLOAD_URL_TTL_SECONDS", 300)
    )

    if max_ttl > 900:
        raise CloudinaryAttachmentConfigurationError(
            "ATTACHMENT_DOWNLOAD_URL_MAX_TTL_SECONDS must not exceed 900."
        )

    if default_ttl < 1:
        raise CloudinaryAttachmentConfigurationError(
            "ATTACHMENT_DOWNLOAD_URL_TTL_SECONDS must be greater than 0."
        )

    if default_ttl > max_ttl:
        raise CloudinaryAttachmentConfigurationError(
            "ATTACHMENT_DOWNLOAD_URL_TTL_SECONDS must not exceed "
            "ATTACHMENT_DOWNLOAD_URL_MAX_TTL_SECONDS."
        )

    requested_ttl = default_ttl

    if expires_in_seconds is not None:
        try:
            requested_ttl = int(expires_in_seconds)
        except (TypeError, ValueError) as error:
            raise CloudinaryAttachmentConfigurationError(
                "expires_in_seconds must be an integer."
            ) from error

    return max(
        1,
        min(requested_ttl, max_ttl),
    )


def build_signed_download_payload(
    *,
    public_id: str,
    expires_in_seconds: int | None = None,
) -> dict:
    """
    Build a short-lived signed Cloudinary delivery URL for encrypted raw bytes.

    Never returns api_secret or plaintext attachment metadata.
    """

    config = get_cloudinary_config()
    resource_type = get_attachment_resource_type()
    ttl_seconds = clamp_download_ttl(expires_in_seconds)

    normalized_public_id = str(public_id or "").strip().strip("/")

    if not normalized_public_id:
        raise CloudinaryAttachmentConfigurationError(
            "public_id is required for signed download URL generation."
        )

    expires_at = timezone.now() + timedelta(seconds=ttl_seconds)
    expires_at_timestamp = int(expires_at.timestamp())

    cloudinary.config(
        cloud_name=config.cloud_name,
        api_key=config.api_key,
        api_secret=config.api_secret,
        secure=True,
    )

    download_url, _options = cloudinary_url(
        normalized_public_id,
        resource_type=resource_type,
        type="upload",
        secure=True,
        sign_url=True,
        expires_at=expires_at_timestamp,
    )

    if not download_url:
        raise CloudinaryAttachmentConfigurationError(
            "Could not create signed Cloudinary download URL."
        )

    return {
        "download_url": download_url,
        "expires_at": expires_at,
    }



def destroy_cloudinary_raw_attachment(
    *,
    public_id: str,
) -> dict:
    """
    Destroy an encrypted raw Cloudinary asset.

    This should be used only by cleanup commands or explicit delete flows.
    """

    config = get_cloudinary_config()
    resource_type = get_attachment_resource_type()

    normalized_public_id = str(public_id or "").strip().strip("/")

    if not normalized_public_id:
        raise CloudinaryAttachmentConfigurationError(
            "public_id is required for Cloudinary destroy."
        )

    cloudinary.config(
        cloud_name=config.cloud_name,
        api_key=config.api_key,
        api_secret=config.api_secret,
        secure=True,
    )

    try:
        result = cloudinary.uploader.destroy(
            normalized_public_id,
            resource_type=resource_type,
            invalidate=True,
        )
    except Exception as error:
        raise CloudinaryAttachmentConfigurationError(
            "Could not destroy Cloudinary encrypted attachment asset."
        ) from error

    return dict(result or {})
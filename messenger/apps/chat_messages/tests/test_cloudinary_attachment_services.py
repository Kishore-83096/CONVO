from types import SimpleNamespace
from uuid import uuid4

from django.test import SimpleTestCase, override_settings

from apps.chat_messages.cloudinary_attachment_services import (
    CloudinaryAttachmentConfigurationError,
    build_attachment_folder,
    build_attachment_public_id,
    build_signed_upload_payload,
    clamp_upload_ttl,
    get_attachment_resource_type,
    get_cloudinary_config,
    sign_cloudinary_upload,
)


class CloudinaryAttachmentServiceTests(SimpleTestCase):
    @override_settings(
        CLOUDINARY_FOLDER="myna/test/attachments",
    )
    def test_build_attachment_folder_uses_backend_folder_user_and_device(self):
        folder = build_attachment_folder(
            user_id="10",
            device_id="device-uuid",
        )

        self.assertEqual(
            folder,
            "myna/test/attachments/10/device-uuid",
        )

    @override_settings(
        CLOUDINARY_FOLDER="myna/test/attachments",
    )
    def test_build_public_id_uses_backend_folder_user_device_and_attachment(self):
        attachment_id = uuid4()

        public_id = build_attachment_public_id(
            user_id="10",
            device_id="device-uuid",
            attachment_id=attachment_id,
        )

        self.assertEqual(
            public_id,
            f"myna/test/attachments/10/device-uuid/{attachment_id}",
        )

    @override_settings(
        CLOUDINARY_FOLDER="myna/test/attachments",
    )
    def test_path_segments_are_sanitized_to_prevent_folder_injection(self):
        public_id = build_attachment_public_id(
            user_id="../10/../../evil",
            device_id="device/../../hack",
            attachment_id="../attachment-secret",
        )

        self.assertNotIn("..", public_id)
        self.assertNotIn("\\", public_id)
        self.assertTrue(
            public_id.startswith("myna/test/attachments/")
        )

    @override_settings(
        ATTACHMENT_MIN_TTL_SECONDS=60,
        ATTACHMENT_UPLOAD_MAX_TTL_SECONDS=900,
        ATTACHMENT_UPLOAD_SIGNATURE_TTL_SECONDS=300,
    )
    def test_clamp_upload_ttl_uses_safe_bounds(self):
        self.assertEqual(clamp_upload_ttl(None), 300)
        self.assertEqual(clamp_upload_ttl(1), 60)
        self.assertEqual(clamp_upload_ttl(9999), 900)

    @override_settings(
        ATTACHMENT_CLOUDINARY_RESOURCE_TYPE="raw",
    )
    def test_resource_type_is_raw(self):
        self.assertEqual(
            get_attachment_resource_type(),
            "raw",
        )

    @override_settings(
        ATTACHMENT_CLOUDINARY_RESOURCE_TYPE="image",
    )
    def test_non_raw_resource_type_is_rejected(self):
        with self.assertRaises(CloudinaryAttachmentConfigurationError):
            get_attachment_resource_type()

    @override_settings(
        CLOUDINARY_URL="cloudinary://public-api-key:private-api-secret@test-cloud",
    )
    def test_cloudinary_config_is_parsed_without_exposing_secret(self):
        config = get_cloudinary_config()

        self.assertEqual(config.cloud_name, "test-cloud")
        self.assertEqual(config.api_key, "public-api-key")
        self.assertEqual(config.api_secret, "private-api-secret")

    @override_settings(
        CLOUDINARY_URL="",
    )
    def test_missing_cloudinary_config_raises_safe_error(self):
        with self.assertRaises(CloudinaryAttachmentConfigurationError):
            get_cloudinary_config()

    @override_settings(
        CLOUDINARY_URL="cloudinary://public-api-key:private-api-secret@test-cloud",
    )
    def test_sign_cloudinary_upload_returns_signature(self):
        signature = sign_cloudinary_upload(
            public_id="myna/test/attachments/10/device/attachment",
            timestamp=1782734650,
        )

        self.assertTrue(signature)
        self.assertIsInstance(signature, str)

    @override_settings(
        CLOUDINARY_URL="cloudinary://public-api-key:private-api-secret@test-cloud",
        CLOUDINARY_FOLDER="myna/test/attachments",
        ATTACHMENT_CLOUDINARY_RESOURCE_TYPE="raw",
        ATTACHMENT_MIN_TTL_SECONDS=60,
        ATTACHMENT_UPLOAD_MAX_TTL_SECONDS=900,
        ATTACHMENT_UPLOAD_SIGNATURE_TTL_SECONDS=900,
    )
    def test_signed_payload_never_contains_api_secret(self):
        attachment_id = uuid4()

        attachment = SimpleNamespace(
            id=attachment_id,
            storage_provider="cloudinary",
            storage_key=f"myna/test/attachments/10/device/{attachment_id}",
        )

        payload = build_signed_upload_payload(
            attachment=attachment,
            ttl_seconds=900,
        )

        self.assertEqual(payload["attachment_id"], str(attachment_id))
        self.assertEqual(payload["storage_provider"], "cloudinary")
        self.assertEqual(payload["cloud_name"], "test-cloud")
        self.assertEqual(payload["api_key"], "public-api-key")
        self.assertEqual(payload["resource_type"], "raw")
        self.assertEqual(
            payload["upload_url"],
            "https://api.cloudinary.com/v1_1/test-cloud/raw/upload",
        )
        self.assertEqual(
            payload["public_id"],
            f"myna/test/attachments/10/device/{attachment_id}",
        )
        self.assertEqual(
            payload["storage_key"],
            f"myna/test/attachments/10/device/{attachment_id}",
        )
        self.assertTrue(payload["signature"])
        self.assertIn("expires_at", payload)
        self.assertNotIn("api_secret", payload)
        self.assertNotIn("private-api-secret", str(payload))
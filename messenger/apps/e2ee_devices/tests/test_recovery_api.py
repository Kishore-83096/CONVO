import uuid
from datetime import timedelta

import jwt
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.e2ee_devices.models import RecoveryBundle


class RecoveryBundleAPITests(APITestCase):
    def setUp(self):
        self.setup_url = reverse(
            "e2ee_devices:recovery-setup"
        )
        self.status_url = reverse(
            "e2ee_devices:recovery-status"
        )
        self.bundle_url = reverse(
            "e2ee_devices:recovery-bundle"
        )

    def authenticate_as(self, user_id: str):
        now = timezone.now()
        token = jwt.encode(
            {
                "sub": user_id,
                "type": "access",
                "iss": settings.JWT_ISSUER,
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

    def valid_setup_payload(self) -> dict:
        return {
            "recovery_public_key": (
                "BASE64_RECOVERY_PUBLIC_KEY"
            ),
            "encrypted_recovery_private_key": (
                "BASE64_ENCRYPTED_RECOVERY_PRIVATE_KEY"
            ),
            "encryption_metadata": {
                "algorithm": (
                    "xchacha20poly1305-ietf"
                ),
                "nonce": "BASE64_24_BYTE_NONCE",
                "unlock_method": (
                    "recovery_key_and_webauthn_prf"
                ),
                "kdf": "hkdf-sha256",
            },
        }

    def configure_recovery(self):
        self.authenticate_as("1")
        response = self.client.post(
            self.setup_url,
            self.valid_setup_payload(),
            format="json",
        )
        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )
        return response

    def test_setup_requires_authentication(self):
        response = self.client.post(
            self.setup_url,
            self.valid_setup_payload(),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(
            RecoveryBundle.objects.count(),
            0,
        )

    def test_recovery_can_be_configured(self):
        response = self.configure_recovery()

        self.assertTrue(response.json()["success"])
        self.assertEqual(
            response.json()["data"]["recovery_version"],
            1,
        )

        bundle = RecoveryBundle.objects.get(
            user_id="1",
        )
        self.assertTrue(bundle.is_active)
        self.assertEqual(
            bundle.recovery_public_key,
            "BASE64_RECOVERY_PUBLIC_KEY",
        )

    def test_active_recovery_cannot_be_overwritten_by_setup(
        self,
    ):
        self.configure_recovery()

        response = self.client.post(
            self.setup_url,
            self.valid_setup_payload(),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_409_CONFLICT,
        )
        self.assertEqual(
            RecoveryBundle.objects.filter(
                user_id="1"
            ).count(),
            1,
        )

    def test_status_reports_not_configured(self):
        self.authenticate_as("1")

        response = self.client.get(
            self.status_url,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            response.json()["data"],
            {
                "configured": False,
                "is_active": False,
                "recovery_version": None,
                "created_at": None,
                "updated_at": None,
                "rotated_at": None,
                "disabled_at": None,
            },
        )

    def test_status_reports_active_bundle(self):
        self.configure_recovery()

        response = self.client.get(
            self.status_url,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertTrue(
            response.json()["data"]["configured"]
        )
        self.assertTrue(
            response.json()["data"]["is_active"]
        )
        self.assertEqual(
            response.json()["data"]["recovery_version"],
            1,
        )

    def test_owner_can_download_encrypted_bundle(self):
        self.configure_recovery()

        response = self.client.get(
            self.bundle_url,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        data = response.json()["data"]
        self.assertEqual(
            data["recovery_public_key"],
            "BASE64_RECOVERY_PUBLIC_KEY",
        )
        self.assertEqual(
            data["encrypted_recovery_private_key"],
            "BASE64_ENCRYPTED_RECOVERY_PRIVATE_KEY",
        )

    def test_another_user_cannot_download_bundle(self):
        self.configure_recovery()
        self.authenticate_as("2")

        response = self.client.get(
            self.bundle_url,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(
            response.json(),
            {
                "success": False,
                "message": (
                    "Encrypted recovery is not available."
                ),
            },
        )

    def test_invalid_encryption_metadata_is_rejected(self):
        self.authenticate_as("1")
        payload = self.valid_setup_payload()
        payload["encryption_metadata"].pop("nonce")

        response = self.client.post(
            self.setup_url,
            payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertFalse(response.json()["success"])
        self.assertIn(
            "encryption_metadata",
            response.json()["errors"],
        )
        self.assertEqual(
            RecoveryBundle.objects.count(),
            0,
        )

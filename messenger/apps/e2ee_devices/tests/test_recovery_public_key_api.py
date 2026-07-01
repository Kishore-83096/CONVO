import uuid
from datetime import timedelta

import jwt
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.e2ee_devices.models import RecoveryBundle


class RecoveryPublicKeyResolveAPITests(APITestCase):
    def setUp(self):
        self.url = reverse(
            "e2ee_devices:recovery-public-key-resolve"
        )

        RecoveryBundle.objects.create(
            user_id="1",
            recovery_public_key="USER_1_PUBLIC_KEY",
            encrypted_recovery_private_key=(
                "USER_1_ENCRYPTED_PRIVATE_KEY"
            ),
            encryption_metadata={
                "algorithm": "xchacha20poly1305-ietf",
                "nonce": "USER_1_NONCE",
                "unlock_method": "recovery_key",
            },
            recovery_version=1,
            is_active=True,
        )

        RecoveryBundle.objects.create(
            user_id="2",
            recovery_public_key="USER_2_PUBLIC_KEY",
            encrypted_recovery_private_key=(
                "USER_2_ENCRYPTED_PRIVATE_KEY"
            ),
            encryption_metadata={
                "algorithm": "xchacha20poly1305-ietf",
                "nonce": "USER_2_NONCE",
                "unlock_method": "recovery_key",
            },
            recovery_version=3,
            is_active=True,
        )

        RecoveryBundle.objects.create(
            user_id="3",
            recovery_public_key="USER_3_PUBLIC_KEY",
            encrypted_recovery_private_key=(
                "USER_3_ENCRYPTED_PRIVATE_KEY"
            ),
            encryption_metadata={
                "algorithm": "xchacha20poly1305-ietf",
                "nonce": "USER_3_NONCE",
                "unlock_method": "recovery_key",
            },
            recovery_version=2,
            is_active=False,
            disabled_at=timezone.now(),
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

    def test_authentication_is_required(self):
        response = self.client.post(
            self.url,
            {
                "user_ids": [
                    "1",
                    "2",
                ],
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_active_public_keys_are_returned(self):
        self.authenticate_as("1")

        response = self.client.post(
            self.url,
            {
                "user_ids": [
                    "1",
                    "2",
                    "3",
                ],
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        public_keys = response.json()["data"][
            "public_keys"
        ]
        self.assertEqual(
            {
                item["user_id"]
                for item in public_keys
            },
            {
                "1",
                "2",
            },
        )

    def test_private_bundle_material_is_never_returned(self):
        self.authenticate_as("1")

        response = self.client.post(
            self.url,
            {
                "user_ids": [
                    "1",
                ],
            },
            format="json",
        )

        serialized = str(response.json())
        self.assertNotIn(
            "USER_1_ENCRYPTED_PRIVATE_KEY",
            serialized,
        )
        self.assertNotIn(
            "encrypted_recovery_private_key",
            serialized,
        )

    def test_duplicate_user_ids_are_rejected(self):
        self.authenticate_as("1")

        response = self.client.post(
            self.url,
            {
                "user_ids": [
                    "1",
                    "1",
                ],
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

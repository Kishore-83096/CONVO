import uuid
from collections import defaultdict
from datetime import timedelta
from unittest.mock import patch

import jwt
from asgiref.sync import async_to_sync
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from django.test import TransactionTestCase
from rest_framework.test import APIClient
from apps.chat_messages.models import ContactDeliveryPolicy
from apps.e2ee_devices.models import Device
from apps.realtime.presence import mark_device_online


class FakeAsyncRedis:
    def __init__(self):
        self.sets = defaultdict(set)
        self.values = {}
        self.expire_calls = []

    async def sadd(self, key, *values):
        before = len(self.sets[key])

        for value in values:
            self.sets[key].add(str(value))

        return len(self.sets[key]) - before

    async def srem(self, key, *values):
        removed = 0

        for value in values:
            value = str(value)

            if value in self.sets[key]:
                self.sets[key].remove(value)
                removed += 1

        return removed

    async def scard(self, key):
        return len(self.sets[key])

    async def smembers(self, key):
        return set(self.sets[key])

    async def expire(self, key, seconds):
        self.expire_calls.append((key, seconds))
        return True

    async def set(self, key, value, ex=None, nx=False):
        if nx and key in self.values:
            return False

        self.values[key] = str(value)

        if ex is not None:
            self.expire_calls.append((key, ex))

        return True

    async def delete(self, *keys):
        deleted = 0

        for key in keys:
            if key in self.values:
                del self.values[key]
                deleted += 1

            if key in self.sets:
                del self.sets[key]
                deleted += 1

        return deleted

    async def aclose(self):
        return None

class PresenceBatchAPITests(TransactionTestCase):
    reset_sequences = True
    subject_a_device_id = uuid.UUID(
        "11111111-1111-4111-8111-111111111111"
    )
    subject_b_device_id = uuid.UUID(
        "22222222-2222-4222-8222-222222222222"
    )

    def setUp(self):
        self.client = APIClient()
        self.url = reverse("realtime:presence-batch")
        self.redis = FakeAsyncRedis()
        self.subject_a_device = Device.objects.create(
            id=self.subject_a_device_id,
            user_id="A",
            device_name="A browser",
            platform=Device.Platform.WEB,
            registration_id=10001,
            identity_key_public="A_IDENTITY",
            signed_prekey_id=1,
            signed_prekey_public="A_SIGNED_PREKEY",
            signed_prekey_signature="A_SIGNATURE",
            key_algorithm="curve25519",
            key_bundle_version=1,
            is_active=True,
        )

        self.subject_b_device = Device.objects.create(
            id=self.subject_b_device_id,
            user_id="B",
            device_name="B browser",
            platform=Device.Platform.WEB,
            registration_id=20001,
            identity_key_public="B_IDENTITY",
            signed_prekey_id=1,
            signed_prekey_public="B_SIGNED_PREKEY",
            signed_prekey_signature="B_SIGNATURE",
            key_algorithm="curve25519",
            key_bundle_version=1,
            is_active=True,
        )

    def patch_redis(self):
        return patch(
            "apps.realtime.presence.get_redis_client",
            return_value=self.redis,
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
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

    def mark_online(self, *, user_id: str, device_id: uuid.UUID):
        async_to_sync(mark_device_online)(
            user_id=user_id,
            device_id=str(device_id),
            channel_name=f"{user_id}.channel.1",
        )

    def test_presence_batch_requires_authentication(self):
        response = self.client.post(
            self.url,
            {
                "user_ids": ["A"],
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_presence_batch_requires_user_ids(self):
        self.authenticate_as("viewer")

        response = self.client.post(
            self.url,
            {},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_presence_batch_returns_online_for_allowed_viewer(self):
        self.authenticate_as("viewer")

        with self.patch_redis():
            self.mark_online(
                user_id="A",
                device_id=self.subject_a_device_id,
            )

            response = self.client.post(
                self.url,
                {
                    "user_ids": ["A"],
                },
                format="json",
            )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            response.json(),
        )

        payload = response.json()

        self.assertTrue(payload["success"])
        self.assertEqual(
            payload["message"],
            "Presence batch fetched successfully.",
        )

        items = payload["data"]["items"]

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["user_id"], "A")
        self.assertEqual(items[0]["status"], "online")
        self.assertEqual(
            items[0]["online_device_ids"],
            [str(self.subject_a_device_id)],
        )
        self.assertIsNotNone(items[0]["last_seen_at"])

    def test_presence_batch_returns_offline_for_allowed_offline_subject(self):
        self.authenticate_as("viewer")

        seen_at = timezone.now() - timedelta(minutes=5)
        self.subject_a_device.last_seen_at = seen_at
        self.subject_a_device.save(
            update_fields=[
                "last_seen_at",
            ]
        )

        with self.patch_redis():
            response = self.client.post(
                self.url,
                {
                    "user_ids": ["A"],
                },
                format="json",
            )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            response.json(),
        )

        item = response.json()["data"]["items"][0]

        self.assertEqual(item["user_id"], "A")
        self.assertEqual(item["status"], "offline")
        self.assertEqual(item["online_device_ids"], [])
        self.assertEqual(item["last_seen_at"], seen_at.isoformat())

    def test_presence_batch_returns_unavailable_when_subject_blocked_viewer(self):
        """
        A blocks viewer.

        Viewer must not see A online/last_seen/device presence.
        Response must not reveal block reason.
        """

        self.authenticate_as("viewer")

        ContactDeliveryPolicy.objects.create(
            owner_user_id="A",
            target_user_id="viewer",
            is_blocked=True,
            policy_version=1,
        )

        with self.patch_redis():
            self.mark_online(
                user_id="A",
                device_id=self.subject_a_device_id,
            )

            response = self.client.post(
                self.url,
                {
                    "user_ids": ["A"],
                },
                format="json",
            )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            response.json(),
        )

        item = response.json()["data"]["items"][0]

        self.assertEqual(item["user_id"], "A")
        self.assertEqual(item["status"], "unavailable")
        self.assertEqual(item["online_device_ids"], [])
        self.assertIsNone(item["last_seen_at"])
        self.assertNotIn("reason", item)
        self.assertNotIn("blocked", item)

    def test_presence_batch_returns_unavailable_when_subject_ghosted_viewer(self):
        """
        A ghosts viewer.

        Viewer must not see A presence until ghost expiry.
        Response must not reveal ghost reason.
        """

        self.authenticate_as("viewer")

        ContactDeliveryPolicy.objects.create(
            owner_user_id="A",
            target_user_id="viewer",
            is_blocked=False,
            ghost_until=timezone.now() + timedelta(hours=1),
            ghost_permanent=False,
            ghost_duration_option="1h",
            policy_version=1,
        )

        with self.patch_redis():
            self.mark_online(
                user_id="A",
                device_id=self.subject_a_device_id,
            )

            response = self.client.post(
                self.url,
                {
                    "user_ids": ["A"],
                },
                format="json",
            )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            response.json(),
        )

        item = response.json()["data"]["items"][0]

        self.assertEqual(item["user_id"], "A")
        self.assertEqual(item["status"], "unavailable")
        self.assertEqual(item["online_device_ids"], [])
        self.assertIsNone(item["last_seen_at"])
        self.assertNotIn("reason", item)
        self.assertNotIn("ghost", item)

    def test_presence_batch_allows_visibility_after_ghost_expired(self):
        self.authenticate_as("viewer")

        ContactDeliveryPolicy.objects.create(
            owner_user_id="A",
            target_user_id="viewer",
            is_blocked=False,
            ghost_until=timezone.now() - timedelta(minutes=1),
            ghost_permanent=False,
            ghost_duration_option="1h",
            policy_version=1,
        )

        with self.patch_redis():
            self.mark_online(
                user_id="A",
                device_id=self.subject_a_device_id,
            )

            response = self.client.post(
                self.url,
                {
                    "user_ids": ["A"],
                },
                format="json",
            )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            response.json(),
        )

        item = response.json()["data"]["items"][0]

        self.assertEqual(item["user_id"], "A")
        self.assertEqual(item["status"], "online")
        self.assertEqual(
            item["online_device_ids"],
            [str(self.subject_a_device_id)],
        )

    def test_presence_batch_deduplicates_user_ids_and_preserves_order(self):
        self.authenticate_as("viewer")

        with self.patch_redis():
            self.mark_online(
                user_id="A",
                device_id=self.subject_a_device_id,
            )
            self.mark_online(
                user_id="B",
                device_id=self.subject_b_device_id,
            )

            response = self.client.post(
                self.url,
                {
                    "user_ids": ["A", "A", "B"],
                },
                format="json",
            )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            response.json(),
        )

        items = response.json()["data"]["items"]

        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["user_id"], "A")
        self.assertEqual(items[1]["user_id"], "B")
        self.assertEqual(items[0]["status"], "online")
        self.assertEqual(items[1]["status"], "online")
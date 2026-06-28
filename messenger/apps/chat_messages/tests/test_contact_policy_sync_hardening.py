from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.chat_messages.models import ContactDeliveryPolicy


@override_settings(CONTACT_POLICY_SYNC_SECRET="test-secret")
class ContactPolicySyncHardeningTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = "/api/v1/internal/contact-policies/"
        self.headers = {
            "HTTP_X_MYNA_INTERNAL_SECRET": "test-secret",
        }

    def test_sync_accepts_current_field_names(self):
        response = self.client.post(
            self.url,
            {
                "owner_user_id": "A",
                "target_user_id": "B",
                "is_blocked": True,
                "policy_version": 1,
            },
            format="json",
            **self.headers,
        )

        self.assertEqual(response.status_code, 200, response.json())

        policy = ContactDeliveryPolicy.objects.get(
            owner_user_id="A",
            target_user_id="B",
        )

        self.assertTrue(policy.is_blocked)

        data = response.json()["data"]
        self.assertEqual(data["owner_user_id"], "A")
        self.assertEqual(data["target_user_id"], "B")
        self.assertEqual(data["policy_owner_user_id"], "A")
        self.assertEqual(data["restricted_user_id"], "B")
        self.assertTrue(data["is_blocked"])
        self.assertIsNone(data["ghost_until"])
        self.assertFalse(data["ghost_permanent"])
        self.assertEqual(data["ghost_duration_option"], "")

    def test_sync_accepts_realtime_plan_field_names(self):
        ghost_until = timezone.now() + timedelta(hours=1)
        source_updated_at = timezone.now()

        response = self.client.post(
            self.url,
            {
                "policy_owner_user_id": "A",
                "restricted_user_id": "B",
                "is_blocked": False,
                "ghost_until": ghost_until.isoformat(),
                "ghost_permanent": False,
                "ghost_duration_option": "1h",
                "policy_version": 3,
                "source_updated_at": source_updated_at.isoformat(),
            },
            format="json",
            **self.headers,
        )

        self.assertEqual(response.status_code, 200, response.json())

        policy = ContactDeliveryPolicy.objects.get(
            owner_user_id="A",
            target_user_id="B",
        )

        self.assertFalse(policy.is_blocked)
        self.assertIsNotNone(policy.ghost_until)
        self.assertFalse(policy.ghost_permanent)
        self.assertEqual(policy.ghost_duration_option, "1h")
        self.assertEqual(policy.policy_version, 3)

        data = response.json()["data"]
        self.assertEqual(data["owner_user_id"], "A")
        self.assertEqual(data["target_user_id"], "B")
        self.assertEqual(data["policy_owner_user_id"], "A")
        self.assertEqual(data["restricted_user_id"], "B")
        self.assertFalse(data["is_blocked"])
        self.assertIsNotNone(data["ghost_until"])
        self.assertFalse(data["ghost_permanent"])
        self.assertEqual(data["ghost_duration_option"], "1h")
        self.assertEqual(data["policy_version"], 3)
        self.assertIsNotNone(data["source_updated_at"])
        self.assertIsNotNone(data["synced_at"])

    def test_sync_rejects_conflicting_owner_aliases(self):
        response = self.client.post(
            self.url,
            {
                "owner_user_id": "A",
                "policy_owner_user_id": "C",
                "target_user_id": "B",
                "is_blocked": True,
                "policy_version": 1,
            },
            format="json",
            **self.headers,
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(ContactDeliveryPolicy.objects.exists())

    def test_sync_rejects_conflicting_target_aliases(self):
        response = self.client.post(
            self.url,
            {
                "owner_user_id": "A",
                "target_user_id": "B",
                "restricted_user_id": "C",
                "is_blocked": True,
                "policy_version": 1,
            },
            format="json",
            **self.headers,
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(ContactDeliveryPolicy.objects.exists())

    def test_sync_ignores_lower_policy_version(self):
        ContactDeliveryPolicy.objects.create(
            owner_user_id="A",
            target_user_id="B",
            is_blocked=False,
            policy_version=5,
        )

        response = self.client.post(
            self.url,
            {
                "owner_user_id": "A",
                "target_user_id": "B",
                "is_blocked": True,
                "policy_version": 4,
            },
            format="json",
            **self.headers,
        )

        self.assertEqual(response.status_code, 200, response.json())

        policy = ContactDeliveryPolicy.objects.get(
            owner_user_id="A",
            target_user_id="B",
        )

        self.assertFalse(policy.is_blocked)
        self.assertEqual(policy.policy_version, 5)

        data = response.json()["data"]
        self.assertFalse(data["created"])
        self.assertFalse(data["updated"])
        self.assertTrue(data["ignored_stale_update"])

    def test_sync_ignores_same_version_with_older_source_updated_at(self):
        newer_source_time = timezone.now()
        older_source_time = newer_source_time - timedelta(minutes=5)

        ContactDeliveryPolicy.objects.create(
            owner_user_id="A",
            target_user_id="B",
            is_blocked=False,
            policy_version=5,
            source_updated_at=newer_source_time,
        )

        response = self.client.post(
            self.url,
            {
                "owner_user_id": "A",
                "target_user_id": "B",
                "is_blocked": True,
                "policy_version": 5,
                "source_updated_at": older_source_time.isoformat(),
            },
            format="json",
            **self.headers,
        )

        self.assertEqual(response.status_code, 200, response.json())

        policy = ContactDeliveryPolicy.objects.get(
            owner_user_id="A",
            target_user_id="B",
        )

        self.assertFalse(policy.is_blocked)
        self.assertEqual(policy.policy_version, 5)
        self.assertEqual(
            policy.source_updated_at,
            newer_source_time,
        )

        data = response.json()["data"]
        self.assertFalse(data["created"])
        self.assertFalse(data["updated"])
        self.assertTrue(data["ignored_stale_update"])

    def test_sync_accepts_same_version_with_newer_source_updated_at(self):
        older_source_time = timezone.now()
        newer_source_time = older_source_time + timedelta(minutes=5)

        ContactDeliveryPolicy.objects.create(
            owner_user_id="A",
            target_user_id="B",
            is_blocked=False,
            policy_version=5,
            source_updated_at=older_source_time,
        )

        response = self.client.post(
            self.url,
            {
                "owner_user_id": "A",
                "target_user_id": "B",
                "is_blocked": True,
                "policy_version": 5,
                "source_updated_at": newer_source_time.isoformat(),
            },
            format="json",
            **self.headers,
        )

        self.assertEqual(response.status_code, 200, response.json())

        policy = ContactDeliveryPolicy.objects.get(
            owner_user_id="A",
            target_user_id="B",
        )

        self.assertTrue(policy.is_blocked)
        self.assertEqual(policy.policy_version, 5)
        self.assertEqual(
            policy.source_updated_at,
            newer_source_time,
        )

        data = response.json()["data"]
        self.assertFalse(data["created"])
        self.assertTrue(data["updated"])
        self.assertFalse(data["ignored_stale_update"])

    def test_sync_accepts_block_plus_ghost_but_block_wins_later(self):
        """
        Messenger may store both block and ghost state if Identity sends both.

        Later realtime policy checks must treat block as the strongest rule:
        inbound delivery blocked, presence hidden, receipts suppressed.
        """

        response = self.client.post(
            self.url,
            {
                "owner_user_id": "A",
                "target_user_id": "B",
                "is_blocked": True,
                "ghost_until": (
                    timezone.now() + timedelta(hours=1)
                ).isoformat(),
                "ghost_permanent": False,
                "ghost_duration_option": "1h",
                "policy_version": 2,
            },
            format="json",
            **self.headers,
        )

        self.assertEqual(response.status_code, 200, response.json())

        policy = ContactDeliveryPolicy.objects.get(
            owner_user_id="A",
            target_user_id="B",
        )

        self.assertTrue(policy.is_blocked)
        self.assertIsNotNone(policy.ghost_until)
        self.assertEqual(policy.ghost_duration_option, "1h")
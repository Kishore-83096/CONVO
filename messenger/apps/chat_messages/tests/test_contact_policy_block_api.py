from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.chat_messages.models import ContactDeliveryPolicy


@override_settings(CONTACT_POLICY_SYNC_SECRET="test-secret")
class ContactPolicyBlockApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = "/api/v1/internal/contact-policies/"
        self.headers = {
            "HTTP_X_MYNA_INTERNAL_SECRET": "test-secret",
        }

    def test_internal_policy_sync_requires_secret(self):
        response = self.client.post(
            self.url,
            {
                "owner_user_id": "1",
                "target_user_id": "2",
                "is_blocked": True,
                "policy_version": 1,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            ContactDeliveryPolicy.objects.filter(
                owner_user_id="1",
                target_user_id="2",
            ).exists()
        )

    def test_internal_policy_sync_creates_block_policy(self):
        response = self.client.post(
            self.url,
            {
                "owner_user_id": "1",
                "target_user_id": "2",
                "is_blocked": True,
                "policy_version": 1,
            },
            format="json",
            **self.headers,
        )

        self.assertEqual(response.status_code, 200)

        policy = ContactDeliveryPolicy.objects.get(
            owner_user_id="1",
            target_user_id="2",
        )

        self.assertTrue(policy.is_blocked)
        self.assertEqual(policy.policy_version, 1)

        data = response.json()["data"]
        self.assertEqual(data["owner_user_id"], "1")
        self.assertEqual(data["target_user_id"], "2")
        self.assertTrue(data["is_blocked"])
        self.assertEqual(data["policy_version"], 1)
        self.assertTrue(data["created"])
        self.assertTrue(data["updated"])
        self.assertFalse(data["ignored_stale_update"])

    def test_internal_policy_sync_updates_block_policy(self):
        ContactDeliveryPolicy.objects.create(
            owner_user_id="1",
            target_user_id="2",
            is_blocked=True,
            policy_version=1,
        )

        response = self.client.post(
            self.url,
            {
                "owner_user_id": "1",
                "target_user_id": "2",
                "is_blocked": False,
                "policy_version": 2,
            },
            format="json",
            **self.headers,
        )

        self.assertEqual(response.status_code, 200)

        policy = ContactDeliveryPolicy.objects.get(
            owner_user_id="1",
            target_user_id="2",
        )

        self.assertFalse(policy.is_blocked)
        self.assertEqual(policy.policy_version, 2)

        data = response.json()["data"]
        self.assertFalse(data["created"])
        self.assertTrue(data["updated"])
        self.assertFalse(data["ignored_stale_update"])

    def test_internal_policy_sync_ignores_stale_policy_version(self):
        ContactDeliveryPolicy.objects.create(
            owner_user_id="1",
            target_user_id="2",
            is_blocked=False,
            policy_version=3,
        )

        response = self.client.post(
            self.url,
            {
                "owner_user_id": "1",
                "target_user_id": "2",
                "is_blocked": True,
                "policy_version": 2,
            },
            format="json",
            **self.headers,
        )

        self.assertEqual(response.status_code, 200)

        policy = ContactDeliveryPolicy.objects.get(
            owner_user_id="1",
            target_user_id="2",
        )

        self.assertFalse(policy.is_blocked)
        self.assertEqual(policy.policy_version, 3)

        data = response.json()["data"]
        self.assertFalse(data["created"])
        self.assertFalse(data["updated"])
        self.assertTrue(data["ignored_stale_update"])

    def test_internal_policy_sync_rejects_same_owner_and_target(self):
        response = self.client.post(
            self.url,
            {
                "owner_user_id": "1",
                "target_user_id": "1",
                "is_blocked": True,
                "policy_version": 1,
            },
            format="json",
            **self.headers,
        )

        self.assertEqual(response.status_code, 400)
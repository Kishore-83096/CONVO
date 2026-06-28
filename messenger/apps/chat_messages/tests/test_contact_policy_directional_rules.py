from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.chat_messages.models import ContactDeliveryPolicy
from apps.chat_messages.policy_services import (
    can_publish_receipt_to_sender,
    can_send_typing_to_viewer,
    can_view_presence,
)


class ContactPolicyDirectionalRuleTests(TestCase):
    def test_user_can_view_own_presence(self):
        self.assertTrue(
            can_view_presence(
                viewer_user_id="1",
                subject_user_id="1",
            )
        )

    def test_blank_viewer_or_subject_cannot_view_presence(self):
        self.assertFalse(
            can_view_presence(
                viewer_user_id="",
                subject_user_id="1",
            )
        )
        self.assertFalse(
            can_view_presence(
                viewer_user_id="1",
                subject_user_id="",
            )
        )

    def test_block_hides_owner_presence_from_restricted_user_only(self):
        """
        A blocks B.

        B cannot see A presence.
        A can still see B presence unless B also restricted A.
        """

        ContactDeliveryPolicy.objects.create(
            owner_user_id="A",
            target_user_id="B",
            is_blocked=True,
            policy_version=1,
        )

        self.assertFalse(
            can_view_presence(
                viewer_user_id="B",
                subject_user_id="A",
            )
        )

        self.assertTrue(
            can_view_presence(
                viewer_user_id="A",
                subject_user_id="B",
            )
        )

    def test_block_suppresses_receipts_from_owner_to_restricted_user_only(self):
        """
        A blocks B.

        If A reads B's message, B must not receive delivered/read.
        If B reads A's message, A can receive delivered/read unless
        B also restricted A.
        """

        ContactDeliveryPolicy.objects.create(
            owner_user_id="A",
            target_user_id="B",
            is_blocked=True,
            policy_version=1,
        )

        self.assertFalse(
            can_publish_receipt_to_sender(
                reader_user_id="A",
                sender_user_id="B",
            )
        )

        self.assertTrue(
            can_publish_receipt_to_sender(
                reader_user_id="B",
                sender_user_id="A",
            )
        )

    def test_active_ghost_hides_owner_presence_from_restricted_user_only(self):
        """
        A ghosts B.

        B cannot see A presence until ghost expiry.
        A can still see B presence unless B also restricted A.
        """

        ContactDeliveryPolicy.objects.create(
            owner_user_id="A",
            target_user_id="B",
            is_blocked=False,
            ghost_until=timezone.now() + timedelta(hours=1),
            ghost_permanent=False,
            ghost_duration_option="1h",
            policy_version=1,
        )

        self.assertFalse(
            can_view_presence(
                viewer_user_id="B",
                subject_user_id="A",
            )
        )

        self.assertTrue(
            can_view_presence(
                viewer_user_id="A",
                subject_user_id="B",
            )
        )

    def test_active_ghost_suppresses_receipts_from_owner_to_restricted_user_only(self):
        """
        A ghosts B.

        If A receives/reads B's message, B must not receive delivered/read.
        If B receives/reads A's message, A can receive delivered/read
        unless B also restricted A.
        """

        ContactDeliveryPolicy.objects.create(
            owner_user_id="A",
            target_user_id="B",
            is_blocked=False,
            ghost_until=timezone.now() + timedelta(hours=1),
            ghost_permanent=False,
            ghost_duration_option="1h",
            policy_version=1,
        )

        self.assertFalse(
            can_publish_receipt_to_sender(
                reader_user_id="A",
                sender_user_id="B",
            )
        )

        self.assertTrue(
            can_publish_receipt_to_sender(
                reader_user_id="B",
                sender_user_id="A",
            )
        )

    def test_expired_ghost_allows_presence_and_receipts_again(self):
        ContactDeliveryPolicy.objects.create(
            owner_user_id="A",
            target_user_id="B",
            is_blocked=False,
            ghost_until=timezone.now() - timedelta(minutes=1),
            ghost_permanent=False,
            ghost_duration_option="1h",
            policy_version=1,
        )

        self.assertTrue(
            can_view_presence(
                viewer_user_id="B",
                subject_user_id="A",
            )
        )

        self.assertTrue(
            can_publish_receipt_to_sender(
                reader_user_id="A",
                sender_user_id="B",
            )
        )

    def test_permanent_ghost_hides_presence_and_suppresses_receipts(self):
        ContactDeliveryPolicy.objects.create(
            owner_user_id="A",
            target_user_id="B",
            is_blocked=False,
            ghost_until=None,
            ghost_permanent=True,
            ghost_duration_option="permanent",
            policy_version=1,
        )

        self.assertFalse(
            can_view_presence(
                viewer_user_id="B",
                subject_user_id="A",
            )
        )

        self.assertFalse(
            can_publish_receipt_to_sender(
                reader_user_id="A",
                sender_user_id="B",
            )
        )

    def test_typing_visibility_reuses_presence_visibility(self):
        ContactDeliveryPolicy.objects.create(
            owner_user_id="A",
            target_user_id="B",
            is_blocked=True,
            policy_version=1,
        )

        self.assertFalse(
            can_send_typing_to_viewer(
                viewer_user_id="B",
                subject_user_id="A",
            )
        )

        self.assertTrue(
            can_send_typing_to_viewer(
                viewer_user_id="A",
                subject_user_id="B",
            )
        )

    def test_mutual_block_hides_presence_both_directions(self):
        ContactDeliveryPolicy.objects.create(
            owner_user_id="A",
            target_user_id="B",
            is_blocked=True,
            policy_version=1,
        )
        ContactDeliveryPolicy.objects.create(
            owner_user_id="B",
            target_user_id="A",
            is_blocked=True,
            policy_version=1,
        )

        self.assertFalse(
            can_view_presence(
                viewer_user_id="A",
                subject_user_id="B",
            )
        )

        self.assertFalse(
            can_view_presence(
                viewer_user_id="B",
                subject_user_id="A",
            )
        )
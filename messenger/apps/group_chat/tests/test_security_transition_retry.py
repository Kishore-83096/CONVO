from unittest.mock import patch

from django.test import TestCase

from apps.group_chat.constants import (
    GROUP_SECURITY_TRANSITION_REASON_MANUAL_SECURITY_ROTATION,
)
from apps.group_chat.models import GroupSecurityTransition
from apps.group_chat.services.security_transitions import (
    apply_security_transition,
    retry_failed_security_transition,
)
from apps.group_chat.tests.factories import (
    GROUP_OWNER_USER_ID,
    create_group_room,
)


class SecurityTransitionRetryTests(TestCase):
    def test_failed_transition_can_be_retried(self):
        profile = create_group_room()

        transition = GroupSecurityTransition.objects.create(
            group_room=profile.room,
            reason=GROUP_SECURITY_TRANSITION_REASON_MANUAL_SECURITY_ROTATION,
            actor_user_id=GROUP_OWNER_USER_ID,
            status="pending",
        )

        with patch(
            "apps.group_chat.services.security_transitions.rotate_group_epoch_system"
        ) as rotate:
            rotate.side_effect = RuntimeError("temporary failure")

            with self.assertRaises(RuntimeError):
                apply_security_transition(
                    transition_id=transition.id,
                )

        transition.refresh_from_db()
        self.assertEqual(transition.status, "failed")
        self.assertEqual(transition.attempt_count, 1)
        self.assertEqual(transition.last_error_code, "RuntimeError")

        retry_result = retry_failed_security_transition(
            transition_id=transition.id,
        )

        self.assertTrue(retry_result.applied)

        transition.refresh_from_db()
        self.assertEqual(transition.status, "applied")
        self.assertEqual(transition.attempt_count, 2)
        self.assertEqual(transition.old_epoch_number, 1)
        self.assertEqual(transition.new_epoch_number, 2)
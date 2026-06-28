from django.test import TestCase

from apps.e2ee_devices.models import Device
from apps.group_chat.constants import (
    GROUP_SECURITY_TRANSITION_REASON_DEVICE_ADDED,
    GROUP_SECURITY_TRANSITION_REASON_DEVICE_DEACTIVATED,
)
from apps.group_chat.models import GroupEncryptionEpoch, GroupSecurityTransition
from apps.group_chat.services.security_transitions import (
    create_device_security_transitions_for_user,
)
from apps.group_chat.tests.factories import (
    GROUP_MEMBER_USER_ID,
    GROUP_OWNER_USER_ID,
    create_group_room,
)


def create_device(
    *,
    user_id: str,
    is_active: bool = True,
) -> Device:
    return Device.objects.create(
        user_id=user_id,
        device_name="Web",
        platform=Device.Platform.WEB,
        registration_id=12345,
        identity_key_public="identity-public-key",
        signed_prekey_id=1,
        signed_prekey_public="signed-prekey-public",
        signed_prekey_signature="signed-prekey-signature",
        key_algorithm="curve25519",
        key_bundle_version=1,
        is_active=is_active,
    )


class DeviceEpochRotationTests(TestCase):
    def test_device_added_for_active_member_rotates_group_epoch(self):
        profile = create_group_room()
        device = create_device(user_id=GROUP_MEMBER_USER_ID)

        results = create_device_security_transitions_for_user(
            user_id=GROUP_MEMBER_USER_ID,
            device=device,
            reason=GROUP_SECURITY_TRANSITION_REASON_DEVICE_ADDED,
            actor_user_id=GROUP_MEMBER_USER_ID,
        )

        self.assertEqual(len(results), 1)

        active_epoch = GroupEncryptionEpoch.objects.get(
            group_room=profile.room,
            status=GroupEncryptionEpoch.Status.ACTIVE,
        )
        self.assertEqual(active_epoch.epoch_number, 2)

        transition = GroupSecurityTransition.objects.get(
            group_room=profile.room,
            reason=GROUP_SECURITY_TRANSITION_REASON_DEVICE_ADDED,
        )
        self.assertEqual(transition.status, "applied")
        self.assertEqual(str(transition.target_device_id), str(device.id))

    def test_device_deactivated_for_active_member_rotates_group_epoch(self):
        profile = create_group_room()
        device = create_device(user_id=GROUP_MEMBER_USER_ID)

        results = create_device_security_transitions_for_user(
            user_id=GROUP_MEMBER_USER_ID,
            device=device,
            reason=GROUP_SECURITY_TRANSITION_REASON_DEVICE_DEACTIVATED,
            actor_user_id=GROUP_MEMBER_USER_ID,
        )

        self.assertEqual(len(results), 1)

        active_epoch = GroupEncryptionEpoch.objects.get(
            group_room=profile.room,
            status=GroupEncryptionEpoch.Status.ACTIVE,
        )
        self.assertEqual(active_epoch.epoch_number, 2)

    def test_direct_only_device_registration_does_not_rotate_group_epoch(self):
        device = create_device(user_id="999")

        results = create_device_security_transitions_for_user(
            user_id="999",
            device=device,
            reason=GROUP_SECURITY_TRANSITION_REASON_DEVICE_ADDED,
            actor_user_id="999",
        )

        self.assertEqual(results, [])
        self.assertEqual(GroupSecurityTransition.objects.count(), 0)

    def test_device_added_for_multiple_groups_rotates_each_group(self):
        first_profile = create_group_room(
            name="First Group",
            member_user_ids=[GROUP_MEMBER_USER_ID],
        )
        second_profile = create_group_room(
            name="Second Group",
            owner_user_id=GROUP_OWNER_USER_ID,
            member_user_ids=[GROUP_MEMBER_USER_ID],
        )
        device = create_device(user_id=GROUP_MEMBER_USER_ID)

        results = create_device_security_transitions_for_user(
            user_id=GROUP_MEMBER_USER_ID,
            device=device,
            reason=GROUP_SECURITY_TRANSITION_REASON_DEVICE_ADDED,
            actor_user_id=GROUP_MEMBER_USER_ID,
        )

        self.assertEqual(len(results), 2)

        first_epoch = GroupEncryptionEpoch.objects.get(
            group_room=first_profile.room,
            status=GroupEncryptionEpoch.Status.ACTIVE,
        )
        second_epoch = GroupEncryptionEpoch.objects.get(
            group_room=second_profile.room,
            status=GroupEncryptionEpoch.Status.ACTIVE,
        )

        self.assertEqual(first_epoch.epoch_number, 2)
        self.assertEqual(second_epoch.epoch_number, 2)
from django.test import TestCase

from apps.e2ee_devices.group_device_hooks import (
    schedule_group_security_for_device_added,
    schedule_group_security_for_device_deactivated,
)
from apps.e2ee_devices.models import Device
from apps.group_chat.models import GroupEncryptionEpoch, GroupSecurityTransition
from apps.group_chat.tests.factories import (
    GROUP_MEMBER_USER_ID,
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


class GroupDeviceHookTests(TestCase):
    def test_device_added_hook_rotates_after_commit(self):
        profile = create_group_room()
        device = create_device(user_id=GROUP_MEMBER_USER_ID)

        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            schedule_group_security_for_device_added(
                device=device,
                actor_user_id=GROUP_MEMBER_USER_ID,
            )

        self.assertEqual(len(callbacks), 1)

        active_epoch = GroupEncryptionEpoch.objects.get(
            group_room=profile.room,
            status=GroupEncryptionEpoch.Status.ACTIVE,
        )

        self.assertEqual(active_epoch.epoch_number, 2)
        self.assertEqual(GroupSecurityTransition.objects.count(), 1)

    def test_inactive_device_added_hook_is_ignored(self):
        create_group_room()
        device = create_device(
            user_id=GROUP_MEMBER_USER_ID,
            is_active=False,
        )

        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            schedule_group_security_for_device_added(
                device=device,
                actor_user_id=GROUP_MEMBER_USER_ID,
            )

        self.assertEqual(len(callbacks), 0)
        self.assertEqual(GroupSecurityTransition.objects.count(), 0)

    def test_device_deactivated_hook_rotates_after_commit(self):
        profile = create_group_room()
        device = create_device(user_id=GROUP_MEMBER_USER_ID)

        device.is_active = False
        device.save(update_fields=["is_active"])

        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            schedule_group_security_for_device_deactivated(
                device=device,
                actor_user_id=GROUP_MEMBER_USER_ID,
            )

        self.assertEqual(len(callbacks), 1)

        active_epoch = GroupEncryptionEpoch.objects.get(
            group_room=profile.room,
            status=GroupEncryptionEpoch.Status.ACTIVE,
        )

        self.assertEqual(active_epoch.epoch_number, 2)
        self.assertEqual(GroupSecurityTransition.objects.count(), 1)
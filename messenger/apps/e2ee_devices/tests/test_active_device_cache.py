import uuid

from django.core.cache import cache
from django.test import TestCase

from apps.e2ee_devices.models import Device
from apps.e2ee_devices.services import (
    get_active_device_ids_cache_key,
    get_active_device_ids_for_user,
    get_active_device_user_ids_by_id,
)


class ActiveDeviceCacheTests(TestCase):
    first_device_id = uuid.UUID(
        "11111111-1111-4111-8111-111111111111"
    )
    second_device_id = uuid.UUID(
        "22222222-2222-4222-8222-222222222222"
    )

    def setUp(self):
        cache.clear()

    def create_device(
        self,
        *,
        device_id,
        user_id="1",
        is_active=True,
    ):
        return Device.objects.create(
            id=device_id,
            user_id=user_id,
            device_name="Browser",
            platform=Device.Platform.WEB,
            registration_id=10000 + Device.objects.count(),
            identity_key_public=f"IDENTITY_{device_id}",
            signed_prekey_id=1,
            signed_prekey_public=f"SIGNED_PREKEY_{device_id}",
            signed_prekey_signature=f"SIGNATURE_{device_id}",
            key_algorithm="curve25519",
            key_bundle_version=1,
            is_active=is_active,
        )

    def test_first_lookup_populates_active_device_cache(self):
        self.create_device(device_id=self.first_device_id)

        device_ids = get_active_device_ids_for_user("1")

        self.assertEqual(
            device_ids,
            [
                str(self.first_device_id),
            ],
        )
        self.assertEqual(
            cache.get(get_active_device_ids_cache_key("1")),
            {
                "device_ids": [
                    str(self.first_device_id),
                ],
            },
        )

    def test_second_lookup_uses_cache_without_database_query(self):
        self.create_device(device_id=self.first_device_id)

        self.assertEqual(
            get_active_device_ids_for_user("1"),
            [
                str(self.first_device_id),
            ],
        )

        with self.assertNumQueries(0):
            self.assertEqual(
                get_active_device_ids_for_user("1"),
                [
                    str(self.first_device_id),
                ],
            )

    def test_device_save_invalidates_active_device_cache(self):
        first_device = self.create_device(
            device_id=self.first_device_id,
        )

        self.assertEqual(
            get_active_device_ids_for_user("1"),
            [
                str(self.first_device_id),
            ],
        )

        self.create_device(device_id=self.second_device_id)

        self.assertEqual(
            set(get_active_device_ids_for_user("1")),
            {
                str(self.first_device_id),
                str(self.second_device_id),
            },
        )

        first_device.is_active = False
        first_device.save(update_fields=["is_active"])

        self.assertEqual(
            get_active_device_ids_for_user("1"),
            [
                str(self.second_device_id),
            ],
        )

    def test_active_device_user_map_contains_only_requested_active_devices(self):
        self.create_device(
            device_id=self.first_device_id,
            user_id="1",
        )
        self.create_device(
            device_id=self.second_device_id,
            user_id="2",
            is_active=False,
        )

        self.assertEqual(
            get_active_device_user_ids_by_id(
                user_ids=[
                    "1",
                    "2",
                ]
            ),
            {
                str(self.first_device_id): "1",
            },
        )
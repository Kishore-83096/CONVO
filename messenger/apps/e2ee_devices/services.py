from dataclasses import dataclass
from typing import Any
from uuid import UUID

from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import Device, OneTimePreKey
from .group_device_hooks import (
    schedule_group_security_for_device_added,
    schedule_group_security_for_device_deactivated,
)

class E2EEDeviceServiceError(Exception):
    """Base exception for E2EE device operations."""


class E2EEDeviceValidationError(E2EEDeviceServiceError):
    """Raised when device data is invalid."""


class DeviceNotFoundError(E2EEDeviceServiceError):
    """Raised when a requested device does not exist."""


class DeviceOwnershipError(E2EEDeviceServiceError):
    """Raised when a device belongs to another user."""


class DeviceIdentityConflictError(E2EEDeviceServiceError):
    """Raised when immutable device identity information changes."""


class PreKeyConflictError(E2EEDeviceServiceError):
    """Raised when a prekey ID is reused with another public key."""


class NoActiveRecipientDevicesError(E2EEDeviceServiceError):
    """Raised when the recipient has no registered active devices."""


@dataclass(frozen=True, slots=True)
class DeviceRegistrationResult:
    device: Device
    device_created: bool
    prekeys_created: int
    prekeys_unchanged: int


@dataclass(frozen=True, slots=True)
class PreKeyUploadResult:
    device: Device
    prekeys_created: int
    prekeys_unchanged: int


def _normalize_user_id(user_id: Any) -> str:
    normalized = str(user_id).strip()

    if not normalized:
        raise E2EEDeviceValidationError(
            "A valid authenticated user ID is required."
        )

    return normalized


def _validate_existing_device(
    *,
    device: Device,
    user_id: str,
    registration_id: int,
    identity_key_public: str,
    key_algorithm: str,
    signed_prekey_id: int,
    signed_prekey_public: str,
    signed_prekey_signature: str,
    key_bundle_version: int,
) -> None:
    if device.user_id != user_id:
        raise DeviceOwnershipError(
            "This device belongs to another user."
        )

    if device.registration_id != registration_id:
        raise DeviceIdentityConflictError(
            "The registration ID cannot be changed for an "
            "existing device."
        )

    if device.identity_key_public != identity_key_public:
        raise DeviceIdentityConflictError(
            "The identity public key cannot be silently changed. "
            "Register a new device ID for a new identity key."
        )

    if device.key_algorithm != key_algorithm:
        raise DeviceIdentityConflictError(
            "The key algorithm cannot be changed for an "
            "existing device."
        )

    if key_bundle_version < device.key_bundle_version:
        raise DeviceIdentityConflictError(
            "The key-bundle version cannot move backwards."
        )

    same_signed_prekey_id = (
        device.signed_prekey_id == signed_prekey_id
    )

    signed_prekey_changed = (
        device.signed_prekey_public != signed_prekey_public
        or device.signed_prekey_signature
        != signed_prekey_signature
    )

    if same_signed_prekey_id and signed_prekey_changed:
        raise DeviceIdentityConflictError(
            "The same signed_prekey_id cannot be reused with "
            "different signed-prekey material."
        )


def _store_one_time_prekeys(
    *,
    device: Device,
    prekeys: list[dict[str, Any]],
) -> tuple[int, int]:
    if not prekeys:
        return 0, 0

    key_ids = [
        item["key_id"]
        for item in prekeys
    ]

    existing_prekeys = {
        prekey.key_id: prekey
        for prekey in OneTimePreKey.objects.filter(
            device=device,
            key_id__in=key_ids,
        )
    }

    new_prekeys = []
    unchanged_count = 0

    for item in prekeys:
        key_id = item["key_id"]
        public_key = item["public_key"].strip()

        existing = existing_prekeys.get(key_id)

        if existing is not None:
            if existing.public_key != public_key:
                raise PreKeyConflictError(
                    f"One-time prekey ID {key_id} already exists "
                    "with different public-key material."
                )

            unchanged_count += 1
            continue

        prekey = OneTimePreKey(
            device=device,
            key_id=key_id,
            public_key=public_key,
        )

        prekey.full_clean()
        new_prekeys.append(prekey)

    OneTimePreKey.objects.bulk_create(
        new_prekeys,
    )

    return len(new_prekeys), unchanged_count


@transaction.atomic
def register_device(
    *,
    authenticated_user_id: str,
    validated_data: dict[str, Any],
) -> DeviceRegistrationResult:
    user_id = _normalize_user_id(
        authenticated_user_id
    )

    data = dict(validated_data)

    device_id: UUID = data.pop("device_id")
    prekeys = list(
        data.pop("one_time_prekeys", [])
    )

    data["identity_key_public"] = (
        data["identity_key_public"].strip()
    )
    data["signed_prekey_public"] = (
        data["signed_prekey_public"].strip()
    )
    data["signed_prekey_signature"] = (
        data["signed_prekey_signature"].strip()
    )
    data["key_algorithm"] = (
        data["key_algorithm"].strip().lower()
    )

    device = (
        Device.objects
        .select_for_update()
        .filter(id=device_id)
        .first()
    )

    device_created = False

    if device is None:
        device = Device(
            id=device_id,
            user_id=user_id,
            **data,
        )

        device.full_clean()

        try:
            with transaction.atomic():
                device.save(force_insert=True)
                schedule_group_security_for_device_added(
                    device=device,
                    actor_user_id=device.user_id,
                )

            device_created = True

        except IntegrityError:
            device = (
                Device.objects
                .select_for_update()
                .get(id=device_id)
            )

    if not device_created:
        _validate_existing_device(
            device=device,
            user_id=user_id,
            registration_id=data["registration_id"],
            identity_key_public=data[
                "identity_key_public"
            ],
            key_algorithm=data["key_algorithm"],
            signed_prekey_id=data[
                "signed_prekey_id"
            ],
            signed_prekey_public=data[
                "signed_prekey_public"
            ],
            signed_prekey_signature=data[
                "signed_prekey_signature"
            ],
            key_bundle_version=data[
                "key_bundle_version"
            ],
        )

        device.device_name = data["device_name"]
        device.platform = data["platform"]
        device.signed_prekey_id = data[
            "signed_prekey_id"
        ]
        device.signed_prekey_public = data[
            "signed_prekey_public"
        ]
        device.signed_prekey_signature = data[
            "signed_prekey_signature"
        ]
        device.key_bundle_version = data[
            "key_bundle_version"
        ]
        device.is_active = True

        device.full_clean()

        device.save(
            update_fields=[
                "device_name",
                "platform",
                "signed_prekey_id",
                "signed_prekey_public",
                "signed_prekey_signature",
                "key_bundle_version",
                "is_active",
                "updated_at",
            ]
        
        )
        schedule_group_security_for_device_added(
            device=device,
            actor_user_id=device.user_id,
        )
    created_count, unchanged_count = (
        _store_one_time_prekeys(
            device=device,
            prekeys=prekeys,
        )
    )

    return DeviceRegistrationResult(
        device=device,
        device_created=device_created,
        prekeys_created=created_count,
        prekeys_unchanged=unchanged_count,
    )


@transaction.atomic
def upload_one_time_prekeys(
    *,
    authenticated_user_id: str,
    device_id: UUID,
    prekeys: list[dict[str, Any]],
) -> PreKeyUploadResult:
    user_id = _normalize_user_id(
        authenticated_user_id
    )

    device = (
        Device.objects
        .select_for_update()
        .filter(id=device_id)
        .first()
    )

    if device is None:
        raise DeviceNotFoundError(
            "The requested device was not found."
        )

    if device.user_id != user_id:
        raise DeviceOwnershipError(
            "This device belongs to another user."
        )

    if not device.is_active:
        raise E2EEDeviceValidationError(
            "Prekeys cannot be uploaded to an inactive device."
        )

    created_count, unchanged_count = (
        _store_one_time_prekeys(
            device=device,
            prekeys=prekeys,
        )
    )

    return PreKeyUploadResult(
        device=device,
        prekeys_created=created_count,
        prekeys_unchanged=unchanged_count,
    )


@transaction.atomic
def claim_recipient_prekey_bundles(
    *,
    authenticated_user_id: str,
    recipient_user_id: str,
) -> list[dict[str, Any]]:
    requester_id = _normalize_user_id(
        authenticated_user_id
    )

    recipient_id = _normalize_user_id(
        recipient_user_id
    )

    if requester_id == recipient_id:
        raise E2EEDeviceValidationError(
            "A direct-chat recipient must be a different user."
        )

    devices = list(
        Device.objects
        .select_for_update()
        .filter(
            user_id=recipient_id,
            is_active=True,
        )
        .order_by(
            "created_at",
            "id",
        )
    )

    if not devices:
        raise NoActiveRecipientDevicesError(
            "The recipient has no active E2EE devices."
        )

    claimed_at = timezone.now()
    bundles = []

    for device in devices:
        one_time_prekey = (
            OneTimePreKey.objects
            .select_for_update()
            .filter(
                device=device,
                is_claimed=False,
            )
            .order_by(
                "key_id",
            )
            .first()
        )

        one_time_prekey_data = None

        if one_time_prekey is not None:
            one_time_prekey.is_claimed = True
            one_time_prekey.claimed_at = claimed_at

            one_time_prekey.save(
                update_fields=[
                    "is_claimed",
                    "claimed_at",
                ]
            )

            one_time_prekey_data = {
                "key_id": one_time_prekey.key_id,
                "public_key": one_time_prekey.public_key,
            }

        bundles.append(
            {
                "device_id": str(device.id),
                "registration_id": (
                    device.registration_id
                ),
                "identity_key_public": (
                    device.identity_key_public
                ),
                "signed_prekey": {
                    "key_id": device.signed_prekey_id,
                    "public_key": (
                        device.signed_prekey_public
                    ),
                    "signature": (
                        device.signed_prekey_signature
                    ),
                },
                "one_time_prekey": (
                    one_time_prekey_data
                ),
                "key_algorithm": (
                    device.key_algorithm
                ),
                "key_bundle_version": (
                    device.key_bundle_version
                ),
            }
        )

    return bundles
from rest_framework import serializers

from ..constants import (
    GROUP_SENDER_KEY_ALGORITHM,
    GROUP_SENDER_KEY_DISTRIBUTION_VERSION,
    GROUP_SENDER_KEY_SIGNING_ALGORITHM,
    GROUP_SENDER_KEY_VERSION,
)


FORBIDDEN_SECRET_FIELD_FRAGMENTS = (
    "private",
    "secret",
    "sender_chain",
    "message_key",
    "ratchet",
    "recovery_key",
    "plaintext",
)


def _reject_secret_field_names(initial_data):
    for field_name in initial_data.keys():
        normalized = str(field_name).lower()
        if any(
            fragment in normalized
            for fragment in FORBIDDEN_SECRET_FIELD_FRAGMENTS
        ):
            raise serializers.ValidationError(
                {
                    field_name: (
                        "Do not upload private keys, secrets, ratchet "
                        "state, message keys or plaintext."
                    )
                }
            )


class GroupSenderKeySerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    group_room_id = serializers.UUIDField(read_only=True)
    epoch_id = serializers.UUIDField(read_only=True)
    epoch_number = serializers.SerializerMethodField()
    sender_user_id = serializers.CharField(read_only=True)
    sender_device_id = serializers.UUIDField(read_only=True)
    sender_key_id = serializers.UUIDField(read_only=True)
    signing_public_key = serializers.CharField(read_only=True)
    key_algorithm = serializers.CharField(read_only=True)
    signing_algorithm = serializers.CharField(read_only=True)
    key_version = serializers.IntegerField(read_only=True)
    highest_accepted_iteration = serializers.IntegerField(read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    revoked_at = serializers.DateTimeField(read_only=True)

    def get_epoch_number(self, instance):
        return instance.epoch.epoch_number


class RegisterGroupSenderKeySerializer(serializers.Serializer):
    sender_device_id = serializers.UUIDField()
    epoch_number = serializers.IntegerField(min_value=1)
    sender_key_id = serializers.UUIDField()
    signing_public_key = serializers.CharField(
        allow_blank=False,
        trim_whitespace=True,
    )
    key_algorithm = serializers.CharField(
        default=GROUP_SENDER_KEY_ALGORITHM,
        required=False,
        trim_whitespace=True,
    )
    signing_algorithm = serializers.CharField(
        default=GROUP_SENDER_KEY_SIGNING_ALGORITHM,
        required=False,
        trim_whitespace=True,
    )
    key_version = serializers.IntegerField(
        min_value=1,
        default=GROUP_SENDER_KEY_VERSION,
        required=False,
    )

    def validate(self, attrs):
        _reject_secret_field_names(self.initial_data)

        attrs["key_algorithm"] = attrs["key_algorithm"].strip().lower()
        attrs["signing_algorithm"] = (
            attrs["signing_algorithm"].strip().lower()
        )
        attrs["signing_public_key"] = (
            attrs["signing_public_key"].strip()
        )

        if attrs["key_algorithm"] != GROUP_SENDER_KEY_ALGORITHM:
            raise serializers.ValidationError(
                {
                    "key_algorithm": (
                        f"Must be {GROUP_SENDER_KEY_ALGORITHM}."
                    )
                }
            )

        if attrs["signing_algorithm"] != GROUP_SENDER_KEY_SIGNING_ALGORITHM:
            raise serializers.ValidationError(
                {
                    "signing_algorithm": (
                        f"Must be {GROUP_SENDER_KEY_SIGNING_ALGORITHM}."
                    )
                }
            )

        if attrs["key_version"] != GROUP_SENDER_KEY_VERSION:
            raise serializers.ValidationError(
                {
                    "key_version": (
                        f"Must be {GROUP_SENDER_KEY_VERSION}."
                    )
                }
            )

        return attrs


class GroupDeviceRosterItemSerializer(serializers.Serializer):
    user_id = serializers.CharField(read_only=True)
    membership_version = serializers.IntegerField(read_only=True)
    device_id = serializers.UUIDField(read_only=True)
    device_name = serializers.CharField(read_only=True)
    platform = serializers.CharField(read_only=True)
    registration_id = serializers.IntegerField(read_only=True)
    identity_key_public = serializers.CharField(read_only=True)
    signed_prekey_id = serializers.IntegerField(read_only=True)
    signed_prekey_public = serializers.CharField(read_only=True)
    signed_prekey_signature = serializers.CharField(read_only=True)
    key_algorithm = serializers.CharField(read_only=True)
    key_bundle_version = serializers.IntegerField(read_only=True)
    epoch_number = serializers.IntegerField(read_only=True)
    membership_snapshot_hash = serializers.CharField(read_only=True)


class SenderKeyDistributionItemSerializer(serializers.Serializer):
    recipient_user_id = serializers.CharField(
        max_length=128,
        allow_blank=False,
        trim_whitespace=True,
    )
    recipient_device_id = serializers.UUIDField()
    encrypted_sender_key = serializers.CharField(
        allow_blank=False,
        trim_whitespace=True,
    )
    distribution_metadata = serializers.DictField()
    distribution_version = serializers.IntegerField(
        min_value=1,
        default=GROUP_SENDER_KEY_DISTRIBUTION_VERSION,
        required=False,
    )


class StoreSenderKeyDistributionsSerializer(serializers.Serializer):
    epoch_number = serializers.IntegerField(min_value=1)
    distributions = SenderKeyDistributionItemSerializer(
        many=True,
        allow_empty=False,
    )

    def validate(self, attrs):
        _reject_secret_field_names(self.initial_data)

        seen_device_ids = set()

        for distribution in attrs["distributions"]:
            recipient_device_id = distribution["recipient_device_id"]

            if recipient_device_id in seen_device_ids:
                raise serializers.ValidationError(
                    {
                        "distributions": (
                            "Duplicate recipient_device_id values are "
                            "not allowed."
                        )
                    }
                )

            seen_device_ids.add(recipient_device_id)

            metadata = distribution["distribution_metadata"]

            if not isinstance(metadata, dict):
                raise serializers.ValidationError(
                    {
                        "distribution_metadata": (
                            "Distribution metadata must be an object."
                        )
                    }
                )

            for field_name in metadata.keys():
                normalized = str(field_name).lower()
                if any(
                    fragment in normalized
                    for fragment in FORBIDDEN_SECRET_FIELD_FRAGMENTS
                ):
                    raise serializers.ValidationError(
                        {
                            "distribution_metadata": (
                                "Do not upload private keys, secrets, "
                                "ratchet state, message keys or plaintext."
                            )
                        }
                    )

        return attrs


class GroupSenderKeyDistributionSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    sender_key_id = serializers.UUIDField(read_only=True)
    sender_key_public_id = serializers.SerializerMethodField()
    group_room_id = serializers.SerializerMethodField()
    epoch_number = serializers.SerializerMethodField()
    sender_user_id = serializers.SerializerMethodField()
    sender_device_id = serializers.SerializerMethodField()
    recipient_user_id = serializers.CharField(read_only=True)
    recipient_device_id = serializers.UUIDField(read_only=True)
    encrypted_sender_key = serializers.CharField(read_only=True)
    distribution_metadata = serializers.JSONField(read_only=True)
    distribution_version = serializers.IntegerField(read_only=True)
    status = serializers.CharField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    acknowledged_at = serializers.DateTimeField(read_only=True)

    def get_sender_key_public_id(self, instance):
        return instance.sender_key.sender_key_id

    def get_group_room_id(self, instance):
        return instance.sender_key.group_room_id

    def get_epoch_number(self, instance):
        return instance.sender_key.epoch.epoch_number

    def get_sender_user_id(self, instance):
        return instance.sender_key.sender_user_id

    def get_sender_device_id(self, instance):
        return instance.sender_key.sender_device_id


class AcknowledgeSenderKeyDistributionsSerializer(serializers.Serializer):
    device_id = serializers.UUIDField()
    distribution_ids = serializers.ListField(
        child=serializers.UUIDField(),
        allow_empty=False,
    )

    def validate_distribution_ids(self, value):
        if len(value) != len(set(value)):
            raise serializers.ValidationError(
                "Duplicate distribution IDs are not allowed."
            )

        return value
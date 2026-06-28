from rest_framework import serializers

from .models import Device


MAX_PREKEYS_PER_REQUEST = 200
MAX_KEY_TEXT_LENGTH = 4096


class OneTimePreKeyInputSerializer(serializers.Serializer):
    key_id = serializers.IntegerField(
        min_value=1,
        max_value=2_147_483_647,
    )

    public_key = serializers.CharField(
        max_length=MAX_KEY_TEXT_LENGTH,
        trim_whitespace=True,
        allow_blank=False,
    )


class DeviceRegistrationSerializer(serializers.Serializer):
    device_id = serializers.UUIDField()

    device_name = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
        default="",
        trim_whitespace=True,
    )

    platform = serializers.ChoiceField(
        choices=Device.Platform.choices,
    )

    registration_id = serializers.IntegerField(
        min_value=1,
        max_value=2_147_483_647,
    )

    identity_key_public = serializers.CharField(
        max_length=MAX_KEY_TEXT_LENGTH,
        trim_whitespace=True,
        allow_blank=False,
    )

    signed_prekey_id = serializers.IntegerField(
        min_value=1,
        max_value=2_147_483_647,
    )

    signed_prekey_public = serializers.CharField(
        max_length=MAX_KEY_TEXT_LENGTH,
        trim_whitespace=True,
        allow_blank=False,
    )

    signed_prekey_signature = serializers.CharField(
        max_length=MAX_KEY_TEXT_LENGTH,
        trim_whitespace=True,
        allow_blank=False,
    )

    key_algorithm = serializers.CharField(
        max_length=50,
        required=False,
        default="curve25519",
        trim_whitespace=True,
        allow_blank=False,
    )

    key_bundle_version = serializers.IntegerField(
        min_value=1,
        max_value=32_767,
        required=False,
        default=1,
    )

    one_time_prekeys = OneTimePreKeyInputSerializer(
        many=True,
        required=False,
        default=list,
    )

    def validate_one_time_prekeys(self, value):
        if len(value) > MAX_PREKEYS_PER_REQUEST:
            raise serializers.ValidationError(
                f"A maximum of {MAX_PREKEYS_PER_REQUEST} "
                "one-time prekeys can be uploaded per request."
            )

        key_ids = [
            item["key_id"]
            for item in value
        ]

        if len(key_ids) != len(set(key_ids)):
            raise serializers.ValidationError(
                "Duplicate key_id values are not allowed."
            )

        return value


class OneTimePreKeyUploadSerializer(serializers.Serializer):
    one_time_prekeys = OneTimePreKeyInputSerializer(
        many=True,
    )

    def validate_one_time_prekeys(self, value):
        if not value:
            raise serializers.ValidationError(
                "At least one one-time prekey is required."
            )

        if len(value) > MAX_PREKEYS_PER_REQUEST:
            raise serializers.ValidationError(
                f"A maximum of {MAX_PREKEYS_PER_REQUEST} "
                "one-time prekeys can be uploaded per request."
            )

        key_ids = [
            item["key_id"]
            for item in value
        ]

        if len(key_ids) != len(set(key_ids)):
            raise serializers.ValidationError(
                "Duplicate key_id values are not allowed."
            )

        return value
    


class PreKeyBundleClaimSerializer(serializers.Serializer):
    recipient_contact_id = serializers.IntegerField(
        min_value=1,
    )
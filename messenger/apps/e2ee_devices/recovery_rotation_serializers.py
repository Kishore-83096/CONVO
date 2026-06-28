import json

from rest_framework import serializers

from .recovery_serializers import RecoverySetupSerializer


class RecoveryRotationEnvelopeSerializer(serializers.Serializer):
    message_id = serializers.UUIDField()
    wrapped_message_key = serializers.CharField(
        max_length=65535,
        trim_whitespace=False,
    )
    key_wrap_metadata = serializers.JSONField()
    envelope_version = serializers.IntegerField(
        min_value=1,
        max_value=65535,
        default=1,
    )

    def validate_wrapped_message_key(
        self,
        value: str,
    ) -> str:
        if not value.strip():
            raise serializers.ValidationError(
                "Wrapped message key cannot be empty."
            )
        return value

    def validate_key_wrap_metadata(self, value: dict) -> dict:
        if not isinstance(value, dict):
            raise serializers.ValidationError(
                "Key-wrap metadata must be a JSON object."
            )

        encoded = json.dumps(
            value,
            separators=(",", ":"),
            sort_keys=True,
        )

        if len(encoded.encode("utf-8")) > 8192:
            raise serializers.ValidationError(
                "Key-wrap metadata is too large."
            )

        if value.get("algorithm") != "recovery-box-v1":
            raise serializers.ValidationError(
                "Rotated recovery envelopes must use "
                "recovery-box-v1."
            )

        nonce = value.get("nonce")
        if not isinstance(nonce, str) or not nonce.strip():
            raise serializers.ValidationError(
                "A non-empty nonce is required."
            )

        return value


class RecoveryRotateSerializer(RecoverySetupSerializer):
    current_recovery_version = serializers.IntegerField(
        min_value=1,
        max_value=65535,
    )
    recovery_envelopes = (
        RecoveryRotationEnvelopeSerializer(
            many=True,
            required=False,
            default=list,
            max_length=5000,
        )
    )

    def validate_recovery_envelopes(
        self,
        value: list[dict],
    ) -> list[dict]:
        message_ids = [
            item["message_id"]
            for item in value
        ]

        if len(message_ids) != len(set(message_ids)):
            raise serializers.ValidationError(
                "Duplicate message_id values are not allowed."
            )

        return value

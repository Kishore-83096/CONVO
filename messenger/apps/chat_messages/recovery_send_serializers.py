import json

from rest_framework import serializers


class RecoveryEnvelopeInputSerializer(serializers.Serializer):
    recovery_owner_user_id = serializers.CharField(
        max_length=128,
        allow_blank=False,
        trim_whitespace=True,
    )
    recovery_key_version = serializers.IntegerField(
        min_value=1,
        max_value=65535,
    )
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
                "Recovery envelopes must use recovery-box-v1."
            )

        nonce = value.get("nonce")
        if not isinstance(nonce, str) or not nonce.strip():
            raise serializers.ValidationError(
                "A non-empty nonce is required."
            )

        return value

import json

from rest_framework import serializers

from .models import Message, MessageKeyEnvelope


class RecoveryBackfillCandidateQuerySerializer(
    serializers.Serializer
):
    device_id = serializers.UUIDField()


class RecoveryBackfillDeviceEnvelopeSerializer(
    serializers.ModelSerializer
):
    recipient_device_id = serializers.UUIDField(
        read_only=True,
    )

    class Meta:
        model = MessageKeyEnvelope
        fields = (
            "recipient_user_id",
            "recipient_device_id",
            "protocol",
            "session_reference",
            "wrapped_message_key",
            "key_wrap_metadata",
            "envelope_version",
            "created_at",
        )


class RecoveryBackfillCandidateSerializer(
    serializers.ModelSerializer
):
    room_id = serializers.UUIDField(
        read_only=True,
    )
    reply_to_id = serializers.UUIDField(
        allow_null=True,
        read_only=True,
    )
    device_envelope = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = (
            "id",
            "room_id",
            "sender_user_id",
            "sender_device_id",
            "client_message_id",
            "message_type",
            "encrypted_payload",
            "encryption_metadata",
            "encryption_version",
            "reply_to_id",
            "client_sent_at",
            "created_at",
            "device_envelope",
        )

    def get_device_envelope(self, message):
        envelopes = getattr(
            message,
            "requesting_device_envelopes",
            [],
        )

        if not envelopes:
            return None

        return RecoveryBackfillDeviceEnvelopeSerializer(
            envelopes[0],
        ).data


class RecoveryBackfillEnvelopeSerializer(
    serializers.Serializer
):
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
                "Recovery backfill envelopes must use "
                "recovery-box-v1."
            )

        nonce = value.get("nonce")
        if not isinstance(nonce, str) or not nonce.strip():
            raise serializers.ValidationError(
                "A non-empty nonce is required."
            )

        return value


class RecoveryBackfillSerializer(serializers.Serializer):
    device_id = serializers.UUIDField()
    recovery_key_version = serializers.IntegerField(
        min_value=1,
        max_value=65535,
    )
    envelopes = RecoveryBackfillEnvelopeSerializer(
        many=True,
        allow_empty=False,
        max_length=100,
    )

    def validate_envelopes(
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

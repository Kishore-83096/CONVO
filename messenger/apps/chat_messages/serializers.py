from rest_framework import serializers

from .models import Message, MessageKeyEnvelope
from .recovery_send_serializers import (
    RecoveryEnvelopeInputSerializer,
)

MAX_ENCRYPTED_PAYLOAD_LENGTH = 2_000_000
MAX_WRAPPED_KEY_LENGTH = 16_384
MAX_ENVELOPES_PER_MESSAGE = 100
MAX_ATTACHMENTS_PER_MESSAGE = 10

class MessageKeyEnvelopeInputSerializer(serializers.Serializer):
    recipient_device_id = serializers.UUIDField()

    protocol = serializers.ChoiceField(
        choices=MessageKeyEnvelope.Protocol.choices,
    )

    session_reference = serializers.CharField(
        max_length=128,
        required=False,
        allow_blank=True,
        default="",
        trim_whitespace=True,
    )

    wrapped_message_key = serializers.CharField(
        max_length=MAX_WRAPPED_KEY_LENGTH,
        allow_blank=False,
        trim_whitespace=True,
    )

    key_wrap_metadata = serializers.JSONField(
        required=False,
        default=dict,
    )

    envelope_version = serializers.IntegerField(
        min_value=1,
        max_value=32_767,
        required=False,
        default=1,
    )

    def validate_key_wrap_metadata(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError(
                "Key-wrap metadata must be a JSON object."
            )

        return value


class SendDirectMessageSerializer(serializers.Serializer):
    # For first message / direct room creation.
    recipient_contact_id = serializers.IntegerField(
        min_value=1,
        required=False,
    )

    # For sending inside an existing direct room.
    room_id = serializers.UUIDField(
        required=False,
    )

    sender_device_id = serializers.UUIDField()

    client_message_id = serializers.UUIDField()

    message_type = serializers.ChoiceField(
        choices=Message.MessageType.choices,
    )

    encrypted_payload = serializers.CharField(
        max_length=MAX_ENCRYPTED_PAYLOAD_LENGTH,
        allow_blank=False,
        trim_whitespace=False,
    )

    encryption_metadata = serializers.JSONField()

    encryption_version = serializers.IntegerField(
        min_value=1,
        max_value=32_767,
        required=False,
        default=1,
    )

    reply_to_id = serializers.UUIDField(
        required=False,
        allow_null=True,
        default=None,
    )

    client_sent_at = serializers.DateTimeField(
        required=False,
        allow_null=True,
        default=None,
    )

    envelopes = MessageKeyEnvelopeInputSerializer(
        many=True,
    )

    recovery_envelopes = RecoveryEnvelopeInputSerializer(
        many=True,
        required=False,
        default=list,
    )
    attachment_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        default=list,
        max_length=MAX_ATTACHMENTS_PER_MESSAGE,
    )

    def validate_encryption_metadata(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError(
                "Encryption metadata must be a JSON object."
            )

        return value

    def validate_envelopes(self, value):
        if not value:
            raise serializers.ValidationError(
                "At least one encrypted device envelope is required."
            )

        if len(value) > MAX_ENVELOPES_PER_MESSAGE:
            raise serializers.ValidationError(
                f"A maximum of {MAX_ENVELOPES_PER_MESSAGE} "
                "device envelopes can be supplied."
            )

        device_ids = [
            str(item["recipient_device_id"])
            for item in value
        ]

        if len(device_ids) != len(set(device_ids)):
            raise serializers.ValidationError(
                "Only one envelope may be supplied for each device."
            )

        return value

    def validate(self, attrs):
        recipient_contact_id = attrs.get("recipient_contact_id")
        room_id = attrs.get("room_id")

        has_recipient_contact_id = recipient_contact_id is not None
        has_room_id = room_id is not None

        if has_recipient_contact_id and has_room_id:
            raise serializers.ValidationError(
                {
                    "recipient": (
                        "Send either recipient_contact_id for first "
                        "message or room_id for an existing direct room, "
                        "not both."
                    )
                }
            )

        if not has_recipient_contact_id and not has_room_id:
            raise serializers.ValidationError(
                {
                    "recipient": (
                        "recipient_contact_id is required for first "
                        "message, or room_id is required for an "
                        "existing direct room."
                    )
                }
            )

        return attrs


class EncryptedHistoryQuerySerializer(serializers.Serializer):
    device_id = serializers.UUIDField()


class MessageKeyEnvelopeOutputSerializer(serializers.Serializer):
    recipient_user_id = serializers.CharField(
        read_only=True,
    )
    recipient_device_id = serializers.UUIDField(
        read_only=True,
    )
    protocol = serializers.CharField(
        read_only=True,
    )
    session_reference = serializers.CharField(
        read_only=True,
    )
    wrapped_message_key = serializers.CharField(
        read_only=True,
    )
    key_wrap_metadata = serializers.JSONField(
        read_only=True,
    )
    envelope_version = serializers.IntegerField(
        read_only=True,
    )


class EncryptedMessageHistoryItemSerializer(serializers.Serializer):
    id = serializers.UUIDField(
        read_only=True,
    )
    room_id = serializers.UUIDField(
        read_only=True,
    )
    sender_user_id = serializers.CharField(
        read_only=True,
    )
    sender_device_id = serializers.CharField(
        read_only=True,
    )
    client_message_id = serializers.UUIDField(
        read_only=True,
    )
    message_type = serializers.CharField(
        read_only=True,
    )
    encrypted_payload = serializers.CharField(
        read_only=True,
    )
    encryption_metadata = serializers.JSONField(
        read_only=True,
    )
    encryption_version = serializers.IntegerField(
        read_only=True,
    )
    reply_to_id = serializers.UUIDField(
        read_only=True,
        allow_null=True,
    )
    client_sent_at = serializers.DateTimeField(
        read_only=True,
        allow_null=True,
    )
    created_at = serializers.DateTimeField(
        read_only=True,
    )

    device_envelope = serializers.SerializerMethodField()

    def get_device_envelope(self, message):
        envelopes = getattr(
            message,
            "requesting_device_envelopes",
            [],
        )

        if not envelopes:
            return None

        return MessageKeyEnvelopeOutputSerializer(
            envelopes[0],
        ).data


class RoomListItemSerializer(serializers.Serializer):
    def to_representation(self, instance):
        room = instance.room
        last_message = instance.last_message

        group_data = None

        if room.room_type == "group":
            group_data = {
                "caller_role": instance.caller_role,
                "member_count": instance.member_count,
                "security_ready": instance.group_security_ready,
                "active_epoch_number": (
                    instance.group_active_epoch_number
                ),
            }

        return {
            "id": str(room.id),
            "room_type": room.room_type,
            "name": room.name,
            "member_user_ids": instance.member_user_ids,
            "other_member_user_ids": (
                instance.other_member_user_ids
            ),
            "group": group_data,
            "created_at": room.created_at,
            "updated_at": room.updated_at,
            "last_message": (
                {
                    "id": str(last_message.id),
                    "sender_user_id": (
                        last_message.sender_user_id
                    ),
                    "message_type": (
                        last_message.message_type
                    ),
                    "created_at": (
                        last_message.created_at
                    ),
                }
                if last_message is not None
                else None
            ),
        }
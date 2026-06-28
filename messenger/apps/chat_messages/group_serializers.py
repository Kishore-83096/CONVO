from rest_framework import serializers

MAX_ATTACHMENTS_PER_MESSAGE = 10

FORBIDDEN_SECRET_FIELD_FRAGMENTS = (
    "plaintext",
    "private",
    "secret",
    "sender_chain",
    "message_key",
    "ratchet",
    "recovery_key",
)

class GroupMessageRecoveryEnvelopeSerializer(serializers.Serializer):
    recovery_owner_user_id = serializers.CharField(
        max_length=128,
        trim_whitespace=True,
    )
    recovery_key_version = serializers.IntegerField(min_value=1)
    wrapped_message_key = serializers.CharField(
        allow_blank=False,
        trim_whitespace=True,
    )
    key_wrap_metadata = serializers.DictField()
    envelope_version = serializers.IntegerField(min_value=1)

    def validate(self, attrs):
        attrs["recovery_owner_user_id"] = (
            attrs["recovery_owner_user_id"].strip()
        )
        attrs["wrapped_message_key"] = attrs["wrapped_message_key"].strip()

        if not attrs["recovery_owner_user_id"]:
            raise serializers.ValidationError(
                {
                    "recovery_owner_user_id": (
                        "Recovery owner user ID is required."
                    )
                }
            )

        if not isinstance(attrs["key_wrap_metadata"], dict):
            raise serializers.ValidationError(
                {
                    "key_wrap_metadata": (
                        "Key wrap metadata must be a JSON object."
                    )
                }
            )

        forbidden_metadata_fragments = (
            "plaintext",
            "private",
            "secret",
            "raw_key",
            "ratchet",
        )

        for key in attrs["key_wrap_metadata"].keys():
            normalized = str(key).lower()
            if any(
                fragment in normalized
                for fragment in forbidden_metadata_fragments
            ):
                raise serializers.ValidationError(
                    {
                        "key_wrap_metadata": (
                            "Recovery envelope metadata must not contain "
                            "plaintext or secret cryptographic material."
                        )
                    }
                )

        return attrs
    


class GroupMessageSendSerializer(serializers.Serializer):
    group_id = serializers.UUIDField()
    sender_device_id = serializers.UUIDField()
    client_message_id = serializers.UUIDField()
    epoch_number = serializers.IntegerField(min_value=1)
    sender_key_id = serializers.UUIDField()
    chain_iteration = serializers.IntegerField(min_value=0)
    message_type = serializers.CharField(
        max_length=20,
        trim_whitespace=True,
    )
    encrypted_payload = serializers.CharField(
        allow_blank=False,
        trim_whitespace=True,
    )
    encryption_metadata = serializers.DictField()
    signature = serializers.CharField(
        allow_blank=False,
        trim_whitespace=True,
    )
    reply_to_message_id = serializers.UUIDField(
        required=False,
        allow_null=True,
    )
    client_sent_at = serializers.DateTimeField(
        required=False,
        allow_null=True,
    )
    recovery_envelopes = GroupMessageRecoveryEnvelopeSerializer(
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

    def validate(self, attrs):
        for field_name in self.initial_data.keys():
            normalized = str(field_name).lower()
            if any(
                fragment in normalized
                for fragment in FORBIDDEN_SECRET_FIELD_FRAGMENTS
            ):
                raise serializers.ValidationError(
                    {
                        field_name: (
                            "Do not upload plaintext, private keys, "
                            "sender-chain secrets, message keys, ratchet "
                            "state or recovery secrets."
                        )
                    }
                )

        metadata = attrs["encryption_metadata"]

        if not isinstance(metadata, dict):
            raise serializers.ValidationError(
                {
                    "encryption_metadata": (
                        "Encryption metadata must be a JSON object."
                    )
                }
            )

        for metadata_key in metadata.keys():
            normalized = str(metadata_key).lower()
            if any(
                fragment in normalized
                for fragment in FORBIDDEN_SECRET_FIELD_FRAGMENTS
            ):
                raise serializers.ValidationError(
                    {
                        "encryption_metadata": (
                            "Encryption metadata must not contain plaintext "
                            "or secret cryptographic material."
                        )
                    }
                )

        algorithm = str(metadata.get("algorithm", "")).strip().lower()

        if algorithm != "group-sender-key-v1":
            raise serializers.ValidationError(
                {
                    "encryption_metadata": (
                        "algorithm must be group-sender-key-v1."
                    )
                }
            )

        attrs["message_type"] = attrs["message_type"].strip()
        attrs["encrypted_payload"] = attrs["encrypted_payload"].strip()
        attrs["signature"] = attrs["signature"].strip()

        if not attrs["message_type"]:
            raise serializers.ValidationError(
                {
                    "message_type": "Message type is required."
                }
            )

        return attrs


class GroupMessageEncryptionSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    message_id = serializers.UUIDField(read_only=True)
    room_id = serializers.SerializerMethodField()
    sender_user_id = serializers.SerializerMethodField()
    sender_device_id = serializers.SerializerMethodField()
    client_message_id = serializers.SerializerMethodField()
    message_type = serializers.SerializerMethodField()
    encrypted_payload = serializers.SerializerMethodField()
    encryption_metadata = serializers.SerializerMethodField()
    epoch_number = serializers.SerializerMethodField()
    sender_key_id = serializers.SerializerMethodField()
    chain_iteration = serializers.IntegerField(read_only=True)
    signature = serializers.CharField(read_only=True)
    reply_to_id = serializers.SerializerMethodField()
    client_sent_at = serializers.SerializerMethodField()
    created_at = serializers.SerializerMethodField()

    def get_room_id(self, instance):
        return instance.message.room_id

    def get_sender_user_id(self, instance):
        return instance.message.sender_user_id

    def get_sender_device_id(self, instance):
        return instance.message.sender_device_id

    def get_client_message_id(self, instance):
        return instance.message.client_message_id

    def get_message_type(self, instance):
        return instance.message.message_type

    def get_encrypted_payload(self, instance):
        return instance.message.encrypted_payload

    def get_encryption_metadata(self, instance):
        return instance.encryption_metadata

    def get_epoch_number(self, instance):
        return instance.epoch.epoch_number

    def get_sender_key_id(self, instance):
        return instance.sender_key.sender_key_id

    def get_reply_to_id(self, instance):
        return instance.message.reply_to_id

    def get_client_sent_at(self, instance):
        return instance.message.client_sent_at

    def get_created_at(self, instance):
        return instance.message.created_at
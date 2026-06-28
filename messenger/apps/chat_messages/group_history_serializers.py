from rest_framework import serializers


class GroupHistoryQuerySerializer(serializers.Serializer):
    device_id = serializers.UUIDField()
    page_size = serializers.IntegerField(
        min_value=1,
        max_value=100,
        default=50,
        required=False,
    )
    cursor = serializers.CharField(
        required=False,
        allow_blank=False,
        trim_whitespace=True,
    )


class GroupHistoryItemSerializer(serializers.Serializer):
    id = serializers.SerializerMethodField()
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
    signing_public_key = serializers.SerializerMethodField()
    reply_to_id = serializers.SerializerMethodField()
    client_sent_at = serializers.SerializerMethodField()
    created_at = serializers.SerializerMethodField()

    def get_id(self, instance):
        return instance.message.id

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

    def get_signing_public_key(self, instance):
        return instance.sender_key.signing_public_key

    def get_reply_to_id(self, instance):
        return instance.message.reply_to_id

    def get_client_sent_at(self, instance):
        return instance.message.client_sent_at

    def get_created_at(self, instance):
        return instance.message.created_at
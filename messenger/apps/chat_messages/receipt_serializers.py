from rest_framework import serializers


class DeliveredReceiptRequestSerializer(serializers.Serializer):
    device_id = serializers.UUIDField()
    message_ids = serializers.ListField(
        child=serializers.UUIDField(),
        allow_empty=False,
        max_length=250,
    )


class ReadReceiptRequestSerializer(serializers.Serializer):
    device_id = serializers.UUIDField()
    group_id = serializers.UUIDField()
    read_through_message_id = serializers.UUIDField()


class MessageReceiptSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    message_id = serializers.UUIDField(read_only=True)
    recipient_user_id = serializers.CharField(read_only=True)
    recipient_device_id = serializers.SerializerMethodField()
    delivered_at = serializers.DateTimeField(read_only=True)
    read_at = serializers.DateTimeField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)

    def get_recipient_device_id(self, instance):
        return instance.recipient_device_id


class MessageReceiptSummarySerializer(serializers.Serializer):
    message_id = serializers.UUIDField(read_only=True)
    delivered_count = serializers.IntegerField(read_only=True)
    read_count = serializers.IntegerField(read_only=True)
    receipts = MessageReceiptSerializer(
        many=True,
        read_only=True,
    )
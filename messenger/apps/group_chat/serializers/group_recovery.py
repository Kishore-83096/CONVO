from rest_framework import serializers


class GroupRecoveryRecipientSerializer(serializers.Serializer):
    user_id = serializers.CharField(read_only=True)
    recovery_public_key = serializers.CharField(read_only=True)
    recovery_version = serializers.IntegerField(read_only=True)


class GroupRecoveryRecipientsResponseSerializer(serializers.Serializer):
    group_id = serializers.UUIDField(read_only=True)
    epoch_number = serializers.IntegerField(read_only=True)
    recipients = GroupRecoveryRecipientSerializer(
        many=True,
        read_only=True,
    )
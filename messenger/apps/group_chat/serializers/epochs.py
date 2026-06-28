from rest_framework import serializers

from ..constants import (
    EPOCH_ROTATION_REASON_MANUAL,
    EPOCH_ROTATION_REASON_SECURITY_INCIDENT,
)


class GroupEncryptionEpochSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    group_room_id = serializers.UUIDField(read_only=True)
    epoch_number = serializers.IntegerField(read_only=True)
    status = serializers.CharField(read_only=True)
    rotation_reason = serializers.CharField(read_only=True)
    created_by_user_id = serializers.CharField(read_only=True)
    membership_snapshot_hash = serializers.CharField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    closed_at = serializers.DateTimeField(read_only=True)


class RotateGroupEpochSerializer(serializers.Serializer):
    reason = serializers.ChoiceField(
        choices=[
            EPOCH_ROTATION_REASON_MANUAL,
            EPOCH_ROTATION_REASON_SECURITY_INCIDENT,
        ],
        default=EPOCH_ROTATION_REASON_MANUAL,
        required=False,
    )
from rest_framework import serializers


class RealtimeTicketCreateSerializer(serializers.Serializer):
    device_id = serializers.UUIDField()

class PresenceBatchSerializer(serializers.Serializer):
    user_ids = serializers.ListField(
        child=serializers.CharField(
            max_length=128,
            allow_blank=False,
            trim_whitespace=True,
        ),
        allow_empty=False,
        max_length=100,
    )

    def validate_user_ids(self, value):
        normalized_user_ids = []

        for user_id in value:
            normalized_user_id = str(user_id).strip()

            if normalized_user_id and normalized_user_id not in normalized_user_ids:
                normalized_user_ids.append(normalized_user_id)

        if not normalized_user_ids:
            raise serializers.ValidationError(
                "At least one valid user_id is required."
            )

        return normalized_user_ids
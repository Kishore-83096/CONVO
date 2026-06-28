from rest_framework import serializers


class RecoveryPublicKeyResolveSerializer(serializers.Serializer):
    user_ids = serializers.ListField(
        child=serializers.CharField(
            max_length=128,
            allow_blank=False,
            trim_whitespace=True,
        ),
        allow_empty=False,
        max_length=20,
    )

    def validate_user_ids(self, value: list[str]) -> list[str]:
        normalized = [
            str(user_id).strip()
            for user_id in value
        ]

        if len(normalized) != len(set(normalized)):
            raise serializers.ValidationError(
                "Duplicate user IDs are not allowed."
            )

        return normalized

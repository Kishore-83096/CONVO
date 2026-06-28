from rest_framework import serializers


class ContactDeliveryPolicySyncSerializer(serializers.Serializer):
    owner_user_id = serializers.CharField(
        max_length=128,
        allow_blank=False,
        trim_whitespace=True,
    )

    target_user_id = serializers.CharField(
        max_length=128,
        allow_blank=False,
        trim_whitespace=True,
    )

    is_blocked = serializers.BooleanField()

    ghost_until = serializers.DateTimeField(
        required=False,
        allow_null=True,
        default=None,
    )

    ghost_permanent = serializers.BooleanField(
        required=False,
        default=False,
    )

    ghost_duration_option = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        default="",
        max_length=20,
        trim_whitespace=True,
    )

    policy_version = serializers.IntegerField(
        min_value=1,
    )

    source_updated_at = serializers.DateTimeField(
        required=False,
        allow_null=True,
        default=None,
    )
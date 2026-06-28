from rest_framework import serializers


class ContactDeliveryPolicySyncSerializer(serializers.Serializer):
    """
    Internal Identity -> Messenger contact-policy sync serializer.

    Current backend field names:
        owner_user_id
        target_user_id

    Realtime-plan field names:
        policy_owner_user_id
        restricted_user_id

    Both are accepted so Identity and Messenger can evolve safely.
    Internally Messenger normalizes everything back to:

        owner_user_id
        target_user_id
    """

    owner_user_id = serializers.CharField(
        max_length=128,
        allow_blank=False,
        trim_whitespace=True,
        required=False,
    )

    target_user_id = serializers.CharField(
        max_length=128,
        allow_blank=False,
        trim_whitespace=True,
        required=False,
    )

    policy_owner_user_id = serializers.CharField(
        max_length=128,
        allow_blank=False,
        trim_whitespace=True,
        required=False,
        write_only=True,
    )

    restricted_user_id = serializers.CharField(
        max_length=128,
        allow_blank=False,
        trim_whitespace=True,
        required=False,
        write_only=True,
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

    def validate(self, attrs):
        owner_user_id = attrs.get("owner_user_id")
        policy_owner_user_id = attrs.get("policy_owner_user_id")

        target_user_id = attrs.get("target_user_id")
        restricted_user_id = attrs.get("restricted_user_id")

        if (
            owner_user_id
            and policy_owner_user_id
            and owner_user_id != policy_owner_user_id
        ):
            raise serializers.ValidationError(
                {
                    "policy_owner_user_id": (
                        "Must match owner_user_id when both are provided."
                    )
                }
            )

        if (
            target_user_id
            and restricted_user_id
            and target_user_id != restricted_user_id
        ):
            raise serializers.ValidationError(
                {
                    "restricted_user_id": (
                        "Must match target_user_id when both are provided."
                    )
                }
            )

        normalized_owner_user_id = owner_user_id or policy_owner_user_id
        normalized_target_user_id = target_user_id or restricted_user_id

        if not normalized_owner_user_id:
            raise serializers.ValidationError(
                {
                    "owner_user_id": (
                        "owner_user_id or policy_owner_user_id is required."
                    )
                }
            )

        if not normalized_target_user_id:
            raise serializers.ValidationError(
                {
                    "target_user_id": (
                        "target_user_id or restricted_user_id is required."
                    )
                }
            )

        attrs["owner_user_id"] = normalized_owner_user_id
        attrs["target_user_id"] = normalized_target_user_id

        attrs.pop("policy_owner_user_id", None)
        attrs.pop("restricted_user_id", None)

        return attrs
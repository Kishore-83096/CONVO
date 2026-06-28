from rest_framework import serializers

from apps.rooms.models import RoomMember


class GroupMemberSerializer(serializers.Serializer):
    user_id = serializers.CharField(read_only=True)
    role = serializers.CharField(read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    joined_at = serializers.DateTimeField(read_only=True)
    left_at = serializers.DateTimeField(read_only=True)
    removed_at = serializers.DateTimeField(read_only=True)
    banned_at = serializers.DateTimeField(read_only=True)
    added_by_user_id = serializers.CharField(read_only=True)
    removed_by_user_id = serializers.CharField(read_only=True)
    membership_version = serializers.IntegerField(read_only=True)


class AddGroupMembersSerializer(serializers.Serializer):
    member_user_ids = serializers.ListField(
        child=serializers.CharField(
            max_length=128,
            allow_blank=False,
            trim_whitespace=True,
        ),
        allow_empty=False,
    )

    def validate_member_user_ids(self, value):
        normalized = [
            str(user_id).strip()
            for user_id in value
        ]

        if len(normalized) != len(set(normalized)):
            raise serializers.ValidationError(
                "Duplicate member user IDs are not allowed."
            )

        return normalized


class ChangeGroupMemberRoleSerializer(serializers.Serializer):
    role = serializers.ChoiceField(
        choices=[
            RoomMember.Role.ADMIN,
            RoomMember.Role.MEMBER,
        ],
    )


class TransferOwnershipSerializer(serializers.Serializer):
    new_owner_user_id = serializers.CharField(
        max_length=128,
        allow_blank=False,
        trim_whitespace=True,
    )
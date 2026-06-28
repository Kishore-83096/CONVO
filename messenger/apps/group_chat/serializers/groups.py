from rest_framework import serializers

from apps.rooms.models import RoomMember

from ..constants import (
    DEFAULT_GROUP_MEMBER_LIMIT,
    MAX_GROUP_MEMBER_LIMIT,
)


MAX_GROUP_NAME_LENGTH = 120
MAX_GROUP_DESCRIPTION_LENGTH = 4096
MAX_AVATAR_STORAGE_KEY_LENGTH = 512


class GroupCreateSerializer(serializers.Serializer):
    name = serializers.CharField(
        max_length=MAX_GROUP_NAME_LENGTH,
        allow_blank=False,
        trim_whitespace=True,
    )

    description = serializers.CharField(
        max_length=MAX_GROUP_DESCRIPTION_LENGTH,
        required=False,
        allow_blank=True,
        default="",
        trim_whitespace=True,
    )

    member_user_ids = serializers.ListField(
        child=serializers.CharField(
            max_length=128,
            allow_blank=False,
            trim_whitespace=True,
        ),
        required=False,
        default=list,
        allow_empty=True,
    )

    max_members = serializers.IntegerField(
        min_value=2,
        max_value=MAX_GROUP_MEMBER_LIMIT,
        required=False,
        default=DEFAULT_GROUP_MEMBER_LIMIT,
    )

    join_history_visible = serializers.BooleanField(
        required=False,
        default=False,
    )

    only_admins_can_send = serializers.BooleanField(
        required=False,
        default=False,
    )

    only_admins_can_edit_info = serializers.BooleanField(
        required=False,
        default=True,
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

    def validate(self, attrs):
        member_user_ids = attrs.get(
            "member_user_ids",
            [],
        )
        max_members = attrs.get(
            "max_members",
            DEFAULT_GROUP_MEMBER_LIMIT,
        )

        if len(member_user_ids) + 1 > max_members:
            raise serializers.ValidationError(
                {
                    "member_user_ids": [
                        "The initial member list exceeds max_members."
                    ]
                }
            )

        return attrs


class GroupUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(
        max_length=MAX_GROUP_NAME_LENGTH,
        required=False,
        allow_blank=False,
        trim_whitespace=True,
    )

    description = serializers.CharField(
        max_length=MAX_GROUP_DESCRIPTION_LENGTH,
        required=False,
        allow_blank=True,
        trim_whitespace=True,
    )

    avatar_storage_key = serializers.CharField(
        max_length=MAX_AVATAR_STORAGE_KEY_LENGTH,
        required=False,
        allow_blank=True,
        trim_whitespace=True,
    )

    max_members = serializers.IntegerField(
        min_value=2,
        max_value=MAX_GROUP_MEMBER_LIMIT,
        required=False,
    )

    join_history_visible = serializers.BooleanField(
        required=False,
    )

    only_admins_can_send = serializers.BooleanField(
        required=False,
    )

    only_admins_can_edit_info = serializers.BooleanField(
        required=False,
    )

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError(
                "At least one group field must be supplied."
            )

        return attrs


class GroupMemberSummarySerializer(serializers.Serializer):
    user_id = serializers.CharField(read_only=True)
    role = serializers.CharField(read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    joined_at = serializers.DateTimeField(read_only=True)


class GroupProfileSerializer(serializers.Serializer):
    def to_representation(self, instance):
        profile = instance.profile
        room = profile.room
        caller_membership = instance.caller_membership
        active_members = instance.active_members

        return {
            "id": str(room.id),
            "room_id": str(room.id),
            "room_type": room.room_type,
            "name": room.name,
            "description": profile.description,
            "avatar_storage_key": profile.avatar_storage_key,
            "created_by_user_id": profile.created_by_user_id,
            "max_members": profile.max_members,
            "join_history_visible": profile.join_history_visible,
            "only_admins_can_send": profile.only_admins_can_send,
            "only_admins_can_edit_info": (
                profile.only_admins_can_edit_info
            ),
            "is_active": room.is_active,
            "caller_role": (
                caller_membership.role
                if caller_membership is not None
                else None
            ),
            "member_count": len(active_members),
            "member_user_ids": [
                member.user_id
                for member in active_members
            ],
            "members": [
                {
                    "user_id": member.user_id,
                    "role": member.role,
                    "is_active": member.is_active,
                    "joined_at": member.joined_at,
                }
                for member in active_members
            ],
            "created_at": profile.created_at,
            "updated_at": profile.updated_at,
        }


class GroupListItemSerializer(serializers.Serializer):
    def to_representation(self, instance):
        profile = instance.profile
        room = profile.room
        caller_membership = instance.caller_membership

        return {
            "id": str(room.id),
            "room_id": str(room.id),
            "room_type": room.room_type,
            "name": room.name,
            "description": profile.description,
            "avatar_storage_key": profile.avatar_storage_key,
            "created_by_user_id": profile.created_by_user_id,
            "max_members": profile.max_members,
            "join_history_visible": profile.join_history_visible,
            "only_admins_can_send": profile.only_admins_can_send,
            "only_admins_can_edit_info": (
                profile.only_admins_can_edit_info
            ),
            "is_active": room.is_active,
            "caller_role": (
                caller_membership.role
                if caller_membership is not None
                else None
            ),
            "member_count": len(instance.active_members),
            "created_at": profile.created_at,
            "updated_at": profile.updated_at,
        }


ADMIN_EDIT_ROLES = {
    RoomMember.Role.OWNER,
    RoomMember.Role.ADMIN,
}
"""Reusable read-only group selectors."""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from apps.rooms.models import Room, RoomMember

from .constants import ROOM_TYPE_GROUP
from .models import GroupProfile


class GroupSelectorError(Exception):
    """Raised when a group selector receives invalid input."""


@dataclass(frozen=True, slots=True)
class GroupAccessContext:
    profile: GroupProfile
    room: Room
    caller_membership: RoomMember
    active_members: list[RoomMember]


def normalize_uuid(
    value: Any,
    *,
    field_name: str,
) -> UUID:
    try:
        return UUID(str(value))
    except (TypeError, ValueError, AttributeError) as error:
        raise GroupSelectorError(
            f"{field_name} must be a valid UUID."
        ) from error


def normalize_user_id(
    value: Any,
    *,
    field_name: str,
) -> str:
    user_id = str(value).strip()

    if not user_id:
        raise GroupSelectorError(f"{field_name} is required.")

    return user_id


def get_active_group_profile(
    *,
    group_id: Any,
) -> GroupProfile | None:
    room_id = normalize_uuid(
        group_id,
        field_name="group_id",
    )

    return (
        GroupProfile.objects.select_related("room")
        .filter(
            room_id=room_id,
            room__room_type=ROOM_TYPE_GROUP,
            room__is_active=True,
        )
        .first()
    )


def get_active_group_membership(
    *,
    room: Room,
    user_id: Any,
) -> RoomMember | None:
    normalized_user_id = normalize_user_id(
        user_id,
        field_name="user_id",
    )

    return (
        RoomMember.objects.filter(
            room=room,
            user_id=normalized_user_id,
            is_active=True,
        )
        .first()
    )


def list_active_group_members(
    *,
    room: Room,
) -> list[RoomMember]:
    return list(
        RoomMember.objects.filter(
            room=room,
            is_active=True,
        ).order_by(
            "joined_at",
            "id",
        )
    )


def get_group_access_context(
    *,
    group_id: Any,
    user_id: Any,
) -> GroupAccessContext | None:
    profile = get_active_group_profile(
        group_id=group_id,
    )

    if profile is None:
        return None

    caller_membership = get_active_group_membership(
        room=profile.room,
        user_id=user_id,
    )

    if caller_membership is None:
        return None

    return GroupAccessContext(
        profile=profile,
        room=profile.room,
        caller_membership=caller_membership,
        active_members=list_active_group_members(room=profile.room),
    )
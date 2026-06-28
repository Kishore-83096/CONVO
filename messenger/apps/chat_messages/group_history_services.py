import base64
import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from django.db.models import Q
from django.utils.dateparse import parse_datetime

from apps.e2ee_devices.models import Device
from apps.group_chat.models import GroupProfile
from apps.rooms.models import Room, RoomMember

from .models import GroupMessageEncryption


class GroupHistoryServiceError(Exception):
    """Base exception for group history operations."""


class GroupHistoryValidationError(GroupHistoryServiceError):
    """Raised when group history input is invalid."""


class GroupHistoryNotFoundError(GroupHistoryServiceError):
    """Raised when group, device, or membership is missing."""


class GroupHistoryPermissionError(GroupHistoryServiceError):
    """Raised when caller cannot access the requested history."""


@dataclass(frozen=True, slots=True)
class GroupHistoryPage:
    items: list[GroupMessageEncryption]
    next_cursor: str | None
    page_size: int


def _normalize_user_id(
    value: Any,
    *,
    field_name: str,
) -> str:
    user_id = str(value).strip()

    if not user_id:
        raise GroupHistoryValidationError(
            f"{field_name} is required."
        )

    return user_id


def _normalize_uuid(
    value: Any,
    *,
    field_name: str,
) -> UUID:
    try:
        return UUID(str(value))
    except (TypeError, ValueError, AttributeError) as error:
        raise GroupHistoryValidationError(
            f"{field_name} must be a valid UUID."
        ) from error


def _encode_cursor(
    *,
    item: GroupMessageEncryption,
) -> str:
    payload = {
        "created_at": item.message.created_at.isoformat(),
        "message_id": str(item.message_id),
    }

    raw = json.dumps(
        payload,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")

    return base64.urlsafe_b64encode(raw).decode("ascii")


def _decode_cursor(
    cursor: str,
) -> tuple[Any, UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii"))
        payload = json.loads(raw.decode("utf-8"))
    except (ValueError, json.JSONDecodeError) as error:
        raise GroupHistoryValidationError(
            "Invalid history cursor."
        ) from error

    created_at = parse_datetime(str(payload.get("created_at", "")))

    if created_at is None:
        raise GroupHistoryValidationError(
            "Invalid history cursor timestamp."
        )

    message_id = _normalize_uuid(
        payload.get("message_id"),
        field_name="cursor.message_id",
    )

    return created_at, message_id


def _get_owned_active_device(
    *,
    device_id: Any,
    authenticated_user_id: str,
) -> Device:
    device_uuid = _normalize_uuid(
        device_id,
        field_name="device_id",
    )

    device = (
        Device.objects.filter(
            id=device_uuid,
            is_active=True,
        )
        .first()
    )

    if device is None:
        raise GroupHistoryNotFoundError(
            "Device was not found."
        )

    if device.user_id != authenticated_user_id:
        raise GroupHistoryPermissionError(
            "Device does not belong to the authenticated user."
        )

    return device


def _get_group_profile(
    *,
    group_id: Any,
) -> GroupProfile:
    group_uuid = _normalize_uuid(
        group_id,
        field_name="group_id",
    )

    profile = (
        GroupProfile.objects.select_related("room")
        .filter(
            room_id=group_uuid,
            room__room_type=Room.RoomType.GROUP,
            room__is_active=True,
        )
        .first()
    )

    if profile is None:
        raise GroupHistoryNotFoundError(
            "Group was not found."
        )

    return profile


def _get_membership_window(
    *,
    room: Room,
    user_id: str,
) -> RoomMember:
    membership = (
        RoomMember.objects.filter(
            room=room,
            user_id=user_id,
        )
        .first()
    )

    if membership is None:
        raise GroupHistoryNotFoundError(
            "Group was not found."
        )

    return membership


def _membership_window_end(
    membership: RoomMember,
):
    end_values = [
        value
        for value in [
            membership.left_at,
            membership.removed_at,
            membership.banned_at,
        ]
        if value is not None
    ]

    if not end_values:
        return None

    return min(end_values)


def list_group_encrypted_history(
    *,
    authenticated_user_id: Any,
    group_id: Any,
    device_id: Any,
    page_size: int = 50,
    cursor: str | None = None,
) -> GroupHistoryPage:
    user_id = _normalize_user_id(
        authenticated_user_id,
        field_name="authenticated_user_id",
    )

    page_size = int(page_size)

    if page_size < 1:
        raise GroupHistoryValidationError(
            "page_size must be at least 1."
        )

    if page_size > 100:
        raise GroupHistoryValidationError(
            "page_size cannot be greater than 100."
        )

    _get_owned_active_device(
        device_id=device_id,
        authenticated_user_id=user_id,
    )

    profile = _get_group_profile(
        group_id=group_id,
    )
    membership = _get_membership_window(
        room=profile.room,
        user_id=user_id,
    )

    queryset = (
        GroupMessageEncryption.objects.select_related(
            "message",
            "epoch",
            "sender_key",
            "sender_key__sender_device",
        )
        .filter(
            group_room=profile.room,
            message__room=profile.room,
        )
    )

    if not profile.join_history_visible:
        queryset = queryset.filter(
            message__created_at__gte=membership.joined_at,
        )

    window_end = _membership_window_end(membership)

    if window_end is not None:
        queryset = queryset.filter(
            message__created_at__lt=window_end,
        )

    if cursor:
        cursor_created_at, cursor_message_id = _decode_cursor(cursor)
        queryset = queryset.filter(
            Q(message__created_at__lt=cursor_created_at)
            | Q(
                message__created_at=cursor_created_at,
                message_id__lt=cursor_message_id,
            )
        )

    queryset = queryset.order_by(
        "-message__created_at",
        "-message_id",
    )

    rows = list(queryset[: page_size + 1])
    items = rows[:page_size]

    next_cursor = None

    if len(rows) > page_size and items:
        next_cursor = _encode_cursor(
            item=items[-1],
        )

    return GroupHistoryPage(
        items=items,
        next_cursor=next_cursor,
        page_size=page_size,
    )
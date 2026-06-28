from dataclasses import dataclass
from typing import Any
from uuid import UUID

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction

from apps.rooms.models import Room, RoomMember
from messenger_config.identity_client import (
    IdentityClientError,
    UnknownIdentityUsersError,
    validate_identity_user_ids,
)
from ..constants import (
    DEFAULT_GROUP_MEMBER_LIMIT,
    GROUP_AUDIT_GROUP_CREATED,
    GROUP_AUDIT_GROUP_UPDATED,
    ROOM_TYPE_GROUP,
)
from ..permissions import can_update_group
from .audit import record_group_audit_event

from ..models import GroupProfile
from .epochs import create_initial_epoch_for_group

class GroupChatServiceError(Exception):
    """Base exception for group-chat operations."""


class GroupChatValidationError(GroupChatServiceError):
    """Raised when group input is invalid."""


class GroupNotFoundError(GroupChatServiceError):
    """Raised when the group is missing or inaccessible."""


class GroupPermissionError(GroupChatServiceError):
    """Raised when an active member lacks permission."""


class GroupConflictError(GroupChatServiceError):
    """Raised when the group cannot be changed safely."""


@dataclass(frozen=True, slots=True)
class GroupView:
    profile: GroupProfile
    caller_membership: RoomMember
    active_members: list[RoomMember]


@dataclass(frozen=True, slots=True)
class GroupCreateResult:
    profile: GroupProfile
    caller_membership: RoomMember
    active_members: list[RoomMember]


@dataclass(frozen=True, slots=True)
class GroupUpdateResult:
    profile: GroupProfile
    caller_membership: RoomMember
    active_members: list[RoomMember]


def _normalize_user_id(
    value: Any,
    *,
    field_name: str,
) -> str:
    user_id = str(value).strip()

    if not user_id:
        raise GroupChatValidationError(
            f"{field_name} is required."
        )

    return user_id


def _normalize_user_ids(values: list[Any]) -> list[str]:
    normalized = [
        _normalize_user_id(
            value,
            field_name="member_user_ids",
        )
        for value in values
    ]

    if len(normalized) != len(set(normalized)):
        raise GroupChatValidationError(
            "Duplicate member user IDs are not allowed."
        )

    return normalized


def _normalize_uuid(
    value: Any,
    *,
    field_name: str,
) -> UUID:
    try:
        return UUID(str(value))
    except (TypeError, ValueError, AttributeError) as error:
        raise GroupChatValidationError(
            f"{field_name} must be a valid UUID."
        ) from error


def _run_model_validation(model) -> None:
    try:
        model.full_clean()
    except DjangoValidationError as error:
        raise GroupChatValidationError(
            error.message_dict
            if hasattr(error, "message_dict")
            else str(error)
        ) from error


def _validate_identity_users(
    *,
    user_ids: list[str],
    authorization_header: str | None,
) -> None:
    try:
        validate_identity_user_ids(
            user_ids=user_ids,
            authorization_header=authorization_header,
        )
    except UnknownIdentityUsersError as error:
        raise GroupChatValidationError(
            {
                "member_user_ids": [
                    "One or more users do not exist in the Identity service."
                ],
                "unknown_user_ids": error.unknown_user_ids,
            }
        ) from error
    except IdentityClientError as error:
        raise GroupConflictError(str(error)) from error


def _active_members_for_room(room: Room) -> list[RoomMember]:
    return list(
        RoomMember.objects.filter(
            room=room,
            is_active=True,
        ).order_by(
            "joined_at",
            "id",
        )
    )


def _build_group_view(
    *,
    profile: GroupProfile,
    caller_user_id: str,
) -> GroupView:
    active_members = _active_members_for_room(profile.room)
    caller_membership = next(
        (
            member
            for member in active_members
            if member.user_id == caller_user_id
        ),
        None,
    )

    if caller_membership is None:
        raise GroupNotFoundError("Group was not found.")

    return GroupView(
        profile=profile,
        caller_membership=caller_membership,
        active_members=active_members,
    )


def _ensure_can_update_group(view: GroupView) -> None:
    if not can_update_group(view.profile, view.caller_membership):
        raise GroupPermissionError(
            "Only the group owner or an admin can edit group info."
        )


def create_group(
    *,
    authenticated_user_id: Any,
    name: str,
    description: str = "",
    member_user_ids: list[Any] | None = None,
    max_members: int = DEFAULT_GROUP_MEMBER_LIMIT,
    join_history_visible: bool = False,
    only_admins_can_send: bool = False,
    only_admins_can_edit_info: bool = True,
    authorization_header: str | None = None,
) -> GroupCreateResult:
    creator_user_id = _normalize_user_id(
        authenticated_user_id,
        field_name="authenticated_user_id",
    )
    normalized_members = _normalize_user_ids(
        member_user_ids or [],
    )

    if creator_user_id in normalized_members:
        raise GroupChatValidationError(
            "The group creator is already added as owner and must not be "
            "included in member_user_ids."
        )

    if len(normalized_members) + 1 > int(max_members):
        raise GroupChatValidationError(
            "The initial member list exceeds max_members."
        )

    # Identity validation happens before DB writes/locks.
    _validate_identity_users(
        user_ids=[creator_user_id, *normalized_members],
        authorization_header=authorization_header,
    )

    try:
        with transaction.atomic():
            room = Room(
                room_type=ROOM_TYPE_GROUP,
                name=str(name).strip(),
                created_by_user_id=creator_user_id,
                direct_pair_key=None,
                is_active=True,
            )
            _run_model_validation(room)
            room.save(force_insert=True)

            profile = GroupProfile(
                room=room,
                description=str(description or "").strip(),
                created_by_user_id=creator_user_id,
                max_members=max_members,
                join_history_visible=join_history_visible,
                only_admins_can_send=only_admins_can_send,
                only_admins_can_edit_info=only_admins_can_edit_info,
            )
            _run_model_validation(profile)
            profile.save(force_insert=True)

            owner_membership = RoomMember(
                room=room,
                user_id=creator_user_id,
                role=RoomMember.Role.OWNER,
                added_by_user_id=creator_user_id,
                is_active=True,
            )
            _run_model_validation(owner_membership)
            owner_membership.save(force_insert=True)

            member_models = []
            for member_user_id in normalized_members:
                member = RoomMember(
                    room=room,
                    user_id=member_user_id,
                    role=RoomMember.Role.MEMBER,
                    added_by_user_id=creator_user_id,
                    is_active=True,
                )
                _run_model_validation(member)
                member_models.append(member)

            RoomMember.objects.bulk_create(member_models)
            create_initial_epoch_for_group(
                room=room,
                actor_user_id=creator_user_id,
            )
            record_group_audit_event(
                room=room,
                actor_user_id=creator_user_id,
                event_type=GROUP_AUDIT_GROUP_CREATED,
                metadata={
                    "name": room.name,
                    "initial_member_count": len(normalized_members) + 1,
                    "max_members": profile.max_members,
                    "join_history_visible": profile.join_history_visible,
                    "only_admins_can_send": profile.only_admins_can_send,
                    "only_admins_can_edit_info": (
                        profile.only_admins_can_edit_info
                    ),
                },
            )

    except IntegrityError as error:
        raise GroupConflictError(
            "The group could not be created because of a database conflict."
        ) from error

    active_members = _active_members_for_room(room)

    return GroupCreateResult(
        profile=profile,
        caller_membership=owner_membership,
        active_members=active_members,
    )


def list_groups_for_user(
    *,
    authenticated_user_id: Any,
) -> list[GroupView]:
    user_id = _normalize_user_id(
        authenticated_user_id,
        field_name="authenticated_user_id",
    )

    profiles = list(
        GroupProfile.objects.select_related(
            "room",
        ).filter(
            room__room_type=ROOM_TYPE_GROUP,
            room__is_active=True,
            room__members__user_id=user_id,
            room__members__is_active=True,
        ).order_by(
            "-room__updated_at",
            "-created_at",
            "room_id",
        ).distinct()
    )

    return [
        _build_group_view(
            profile=profile,
            caller_user_id=user_id,
        )
        for profile in profiles
    ]


def get_group_detail(
    *,
    authenticated_user_id: Any,
    group_id: Any,
) -> GroupView:
    user_id = _normalize_user_id(
        authenticated_user_id,
        field_name="authenticated_user_id",
    )
    room_id = _normalize_uuid(
        group_id,
        field_name="group_id",
    )

    profile = (
        GroupProfile.objects.select_related(
            "room",
        ).filter(
            room_id=room_id,
            room__room_type=ROOM_TYPE_GROUP,
            room__is_active=True,
        ).first()
    )

    if profile is None:
        raise GroupNotFoundError("Group was not found.")

    return _build_group_view(
        profile=profile,
        caller_user_id=user_id,
    )


@transaction.atomic
def update_group(
    *,
    authenticated_user_id: Any,
    group_id: Any,
    validated_data: dict[str, Any],
) -> GroupUpdateResult:
    user_id = _normalize_user_id(
        authenticated_user_id,
        field_name="authenticated_user_id",
    )
    room_id = _normalize_uuid(
        group_id,
        field_name="group_id",
    )

    profile = (
        GroupProfile.objects.select_for_update()
        .select_related("room")
        .filter(
            room_id=room_id,
            room__room_type=ROOM_TYPE_GROUP,
            room__is_active=True,
        )
        .first()
    )

    if profile is None:
        raise GroupNotFoundError("Group was not found.")

    room = (
        Room.objects.select_for_update()
        .filter(id=profile.room_id)
        .first()
    )

    if room is None or not room.is_active or room.room_type != ROOM_TYPE_GROUP:
        raise GroupNotFoundError("Group was not found.")

    profile.room = room

    view = _build_group_view(
        profile=profile,
        caller_user_id=user_id,
    )
    _ensure_can_update_group(view)
    changed_fields = sorted(validated_data.keys())

    if "max_members" in validated_data:
        requested_limit = int(validated_data["max_members"])
        if requested_limit < len(view.active_members):
            raise GroupChatValidationError(
                "max_members cannot be lower than the active member count."
            )
        profile.max_members = requested_limit

    if "name" in validated_data:
        room.name = str(validated_data["name"]).strip()

    if "description" in validated_data:
        profile.description = str(validated_data["description"] or "").strip()

    if "avatar_storage_key" in validated_data:
        profile.avatar_storage_key = str(
            validated_data["avatar_storage_key"] or ""
        ).strip()

    for boolean_field in (
        "join_history_visible",
        "only_admins_can_send",
        "only_admins_can_edit_info",
    ):
        if boolean_field in validated_data:
            setattr(
                profile,
                boolean_field,
                bool(validated_data[boolean_field]),
            )

    _run_model_validation(room)
    _run_model_validation(profile)

    room.save(
        update_fields=[
            "name",
            "updated_at",
        ]
    )
    profile.save()
    record_group_audit_event(
        room=room,
        actor_user_id=user_id,
        event_type=GROUP_AUDIT_GROUP_UPDATED,
        metadata={
            "changed_fields": changed_fields,
        },
    )

    return GroupUpdateResult(
        profile=profile,
        caller_membership=view.caller_membership,
        active_members=_active_members_for_room(room),
    )
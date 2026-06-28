from ..constants import (
    GROUP_AUDIT_MEMBER_BANNED,
    GROUP_AUDIT_MEMBER_LEFT,
    GROUP_AUDIT_MEMBER_REMOVED,
    GROUP_AUDIT_MEMBER_UNBANNED,
    GROUP_AUDIT_MEMBERS_ADDED,
    GROUP_AUDIT_OWNERSHIP_TRANSFERRED,
    GROUP_AUDIT_ROLE_CHANGED,
    ROOM_TYPE_GROUP,
    GROUP_SECURITY_TRANSITION_REASON_MEMBER_ADDED,
    GROUP_SECURITY_TRANSITION_REASON_MEMBER_BANNED,
    GROUP_SECURITY_TRANSITION_REASON_MEMBER_LEFT,
    GROUP_SECURITY_TRANSITION_REASON_MEMBER_REMOVED,
    GROUP_SECURITY_TRANSITION_REASON_MEMBER_UNBANNED,
)
from ..permissions import (
    can_add_members,
    can_ban_member,
    can_change_role,
    can_leave_group,
    can_remove_member,
    can_transfer_ownership,
    can_unban_member,
)
from ..constants import (
    EPOCH_ROTATION_REASON_MEMBER_ADDED,
    EPOCH_ROTATION_REASON_MEMBER_BANNED,
    EPOCH_ROTATION_REASON_MEMBER_LEFT,
    EPOCH_ROTATION_REASON_MEMBER_REMOVED,
    GROUP_AUDIT_MEMBER_BANNED,
    GROUP_AUDIT_MEMBER_LEFT,
    GROUP_AUDIT_MEMBER_REMOVED,
    GROUP_AUDIT_MEMBER_UNBANNED,
    GROUP_AUDIT_MEMBERS_ADDED,
    GROUP_AUDIT_OWNERSHIP_TRANSFERRED,
    GROUP_AUDIT_ROLE_CHANGED,
    ROOM_TYPE_GROUP,
)
from .security_transitions import create_member_security_transition
from .epochs import rotate_epoch_after_membership_change
from .audit import record_group_audit_event
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.rooms.models import Room, RoomMember
from messenger_config.identity_client import (
    IdentityClientError,
    UnknownIdentityUsersError,
    validate_identity_user_ids,
)

from ..models import GroupProfile


class GroupMembershipServiceError(Exception):
    """Base exception for group membership operations."""


class GroupMembershipValidationError(GroupMembershipServiceError):
    """Raised when membership input is invalid."""


class GroupMembershipPermissionError(GroupMembershipServiceError):
    """Raised when the actor is not allowed to perform an action."""


class GroupMembershipNotFoundError(GroupMembershipServiceError):
    """Raised when the group or membership does not exist."""


class GroupMembershipConflictError(GroupMembershipServiceError):
    """Raised when the membership operation conflicts with current state."""


@dataclass(frozen=True, slots=True)
class MembershipContext:
    profile: GroupProfile
    room: Room
    actor_membership: RoomMember


def _normalize_user_id(
    value: Any,
    *,
    field_name: str,
) -> str:
    user_id = str(value).strip()

    if not user_id:
        raise GroupMembershipValidationError(
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
        raise GroupMembershipValidationError(
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
        raise GroupMembershipValidationError(
            f"{field_name} must be a valid UUID."
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
        raise GroupMembershipValidationError(
            {
                "member_user_ids": [
                    "One or more users do not exist in the Identity service."
                ],
                "unknown_user_ids": error.unknown_user_ids,
            }
        ) from error
    except IdentityClientError as error:
        raise GroupMembershipConflictError(str(error)) from error


def _get_context_for_update(
    *,
    group_id: Any,
    actor_user_id: Any,
) -> MembershipContext:
    actor_user_id = _normalize_user_id(
        actor_user_id,
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
        raise GroupMembershipNotFoundError("Group was not found.")

    room = (
        Room.objects.select_for_update()
        .filter(
            id=profile.room_id,
            room_type=ROOM_TYPE_GROUP,
            is_active=True,
        )
        .first()
    )

    if room is None:
        raise GroupMembershipNotFoundError("Group was not found.")

    actor_membership = (
        RoomMember.objects.select_for_update()
        .filter(
            room=room,
            user_id=actor_user_id,
            is_active=True,
        )
        .first()
    )

    if actor_membership is None:
        raise GroupMembershipNotFoundError("Group was not found.")

    return MembershipContext(
        profile=profile,
        room=room,
        actor_membership=actor_membership,
    )


def _get_context_for_read(
    *,
    group_id: Any,
    actor_user_id: Any,
) -> MembershipContext:
    actor_user_id = _normalize_user_id(
        actor_user_id,
        field_name="authenticated_user_id",
    )
    room_id = _normalize_uuid(
        group_id,
        field_name="group_id",
    )

    profile = (
        GroupProfile.objects.select_related("room")
        .filter(
            room_id=room_id,
            room__room_type=ROOM_TYPE_GROUP,
            room__is_active=True,
        )
        .first()
    )

    if profile is None:
        raise GroupMembershipNotFoundError("Group was not found.")

    actor_membership = (
        RoomMember.objects.filter(
            room=profile.room,
            user_id=actor_user_id,
            is_active=True,
        )
        .first()
    )

    if actor_membership is None:
        raise GroupMembershipNotFoundError("Group was not found.")

    return MembershipContext(
        profile=profile,
        room=profile.room,
        actor_membership=actor_membership,
    )


def _active_members(room: Room) -> list[RoomMember]:
    return list(
        RoomMember.objects.filter(
            room=room,
            is_active=True,
        ).order_by(
            "joined_at",
            "id",
        )
    )


def _all_members(room: Room) -> list[RoomMember]:
    return list(
        RoomMember.objects.filter(
            room=room,
        ).order_by(
            "-is_active",
            "joined_at",
            "id",
        )
    )


def _is_owner(member: RoomMember) -> bool:
    return member.role == RoomMember.Role.OWNER


def _is_admin(member: RoomMember) -> bool:
    return member.role == RoomMember.Role.ADMIN


def _is_owner_or_admin(member: RoomMember) -> bool:
    return member.role in {
        RoomMember.Role.OWNER,
        RoomMember.Role.ADMIN,
    }


def _increment_membership_version(member: RoomMember) -> None:
    member.membership_version = int(member.membership_version or 0) + 1


def list_group_members(
    *,
    authenticated_user_id: Any,
    group_id: Any,
) -> list[RoomMember]:
    context = _get_context_for_read(
        group_id=group_id,
        actor_user_id=authenticated_user_id,
    )

    return _all_members(context.room)


@transaction.atomic
def add_group_members(
    *,
    authenticated_user_id: Any,
    group_id: Any,
    member_user_ids: list[Any],
    authorization_header: str | None = None,
) -> list[RoomMember]:
    actor_user_id = _normalize_user_id(
        authenticated_user_id,
        field_name="authenticated_user_id",
    )
    normalized_user_ids = _normalize_user_ids(member_user_ids)

    _validate_identity_users(
        user_ids=normalized_user_ids,
        authorization_header=authorization_header,
    )

    context = _get_context_for_update(
        group_id=group_id,
        actor_user_id=actor_user_id,
    )

    if not can_add_members(context.actor_membership):
        raise GroupMembershipPermissionError(
            "Only the group owner or an admin can add members."
        )

    existing_members = {
        member.user_id: member
        for member in RoomMember.objects.select_for_update().filter(
            room=context.room,
            user_id__in=normalized_user_ids,
        )
    }

    now = timezone.now()
    active_count = RoomMember.objects.select_for_update().filter(
        room=context.room,
        is_active=True,
    ).count()

    added_members: list[RoomMember] = []

    for user_id in normalized_user_ids:
        if user_id == actor_user_id:
            raise GroupMembershipValidationError(
                "Use the active membership instead of adding yourself again."
            )

        existing = existing_members.get(user_id)

        if existing is not None and existing.is_active:
            raise GroupMembershipConflictError(
                f"User {user_id} is already an active group member."
            )

        if existing is not None and existing.banned_at is not None:
            raise GroupMembershipPermissionError(
                f"User {user_id} is banned from this group."
            )

        if active_count + 1 > context.profile.max_members:
            raise GroupMembershipConflictError(
                "The group member limit has been reached."
            )

        if existing is not None:
            existing.role = RoomMember.Role.MEMBER
            existing.is_active = True
            existing.joined_at = now
            existing.left_at = None
            existing.removed_at = None
            existing.removed_by_user_id = None
            existing.added_by_user_id = actor_user_id
            _increment_membership_version(existing)
            existing.save(
                update_fields=[
                    "role",
                    "is_active",
                    "joined_at",
                    "left_at",
                    "removed_at",
                    "removed_by_user_id",
                    "added_by_user_id",
                    "membership_version",
                    "updated_at",
                ]
            )
            added_members.append(existing)
        else:
            member = RoomMember.objects.create(
                room=context.room,
                user_id=user_id,
                role=RoomMember.Role.MEMBER,
                added_by_user_id=actor_user_id,
                is_active=True,
                membership_version=1,
            )
            added_members.append(member)

        active_count += 1

    context.room.save(update_fields=["updated_at"])
    record_group_audit_event(
        room=context.room,
        actor_user_id=actor_user_id,
        event_type=GROUP_AUDIT_MEMBERS_ADDED,
        metadata={
            "member_user_ids": normalized_user_ids,
            "added_count": len(added_members),
        },
    )
    for added_member in added_members:
        create_member_security_transition(
            group_room=context.room,
            reason=GROUP_SECURITY_TRANSITION_REASON_MEMBER_ADDED,
            actor_user_id=actor_user_id,
            target_user_id=added_member.user_id,
        )
    return added_members


@transaction.atomic
def remove_group_member(
    *,
    authenticated_user_id: Any,
    group_id: Any,
    target_user_id: Any,
) -> RoomMember:
    actor_user_id = _normalize_user_id(
        authenticated_user_id,
        field_name="authenticated_user_id",
    )
    target_user_id = _normalize_user_id(
        target_user_id,
        field_name="target_user_id",
    )

    context = _get_context_for_update(
        group_id=group_id,
        actor_user_id=actor_user_id,
    )

    target = (
        RoomMember.objects.select_for_update()
        .filter(
            room=context.room,
            user_id=target_user_id,
            is_active=True,
        )
        .first()
    )

    if target is None:
        raise GroupMembershipNotFoundError("Member was not found.")

    if target.user_id == actor_user_id:
        raise GroupMembershipValidationError(
            "Use the leave endpoint to leave the group."
        )

    if not can_remove_member(context.actor_membership, target):
        raise GroupMembershipPermissionError(
            "You do not have permission to remove this member."
        )

    now = timezone.now()
    target.is_active = False
    target.removed_at = now
    target.removed_by_user_id = actor_user_id
    target.left_at = None
    _increment_membership_version(target)
    target.save(
        update_fields=[
            "is_active",
            "removed_at",
            "removed_by_user_id",
            "left_at",
            "membership_version",
            "updated_at",
        ]
    )

    context.room.save(update_fields=["updated_at"])
    record_group_audit_event(
        room=context.room,
        actor_user_id=actor_user_id,
        event_type=GROUP_AUDIT_MEMBER_REMOVED,
        target_user_id=target.user_id,
        metadata={
            "previous_role": target.role,
        },
    )
    create_member_security_transition(
        group_room=context.room,
        reason=GROUP_SECURITY_TRANSITION_REASON_MEMBER_REMOVED,
        actor_user_id=actor_user_id,
        target_user_id=target.user_id,
    )
    return target


@transaction.atomic
def change_group_member_role(
    *,
    authenticated_user_id: Any,
    group_id: Any,
    target_user_id: Any,
    role: str,
) -> RoomMember:
    actor_user_id = _normalize_user_id(
        authenticated_user_id,
        field_name="authenticated_user_id",
    )
    target_user_id = _normalize_user_id(
        target_user_id,
        field_name="target_user_id",
    )
    role = str(role).strip()

    if role == RoomMember.Role.OWNER:
        raise GroupMembershipValidationError(
            "Use the transfer ownership endpoint to make another owner."
        )

    if role not in {
        RoomMember.Role.ADMIN,
        RoomMember.Role.MEMBER,
    }:
        raise GroupMembershipValidationError("Invalid group role.")

    context = _get_context_for_update(
        group_id=group_id,
        actor_user_id=actor_user_id,
    )

    if not _is_owner(context.actor_membership):
        raise GroupMembershipPermissionError(
            "Only the group owner can change member roles."
        )

    target = (
        RoomMember.objects.select_for_update()
        .filter(
            room=context.room,
            user_id=target_user_id,
            is_active=True,
        )
        .first()
    )

    if target is None:
        raise GroupMembershipNotFoundError("Member was not found.")
    old_role = target.role

    if not can_change_role(context.actor_membership, target, role):
        raise GroupMembershipPermissionError(
            "Only the group owner can change non-owner member roles."
        )


    if target.role == role:
        return target

    target.role = role
    _increment_membership_version(target)
    target.save(
        update_fields=[
            "role",
            "membership_version",
            "updated_at",
        ]
    )

    context.room.save(update_fields=["updated_at"])
    record_group_audit_event(
        room=context.room,
        actor_user_id=actor_user_id,
        event_type=GROUP_AUDIT_ROLE_CHANGED,
        target_user_id=target.user_id,
        metadata={
            "old_role": old_role,
            "new_role": target.role,
        },
    )

    return target


@transaction.atomic
def leave_group(
    *,
    authenticated_user_id: Any,
    group_id: Any,
) -> RoomMember:
    actor_user_id = _normalize_user_id(
        authenticated_user_id,
        field_name="authenticated_user_id",
    )

    context = _get_context_for_update(
        group_id=group_id,
        actor_user_id=actor_user_id,
    )

    if not can_leave_group(context.actor_membership):
        raise GroupMembershipPermissionError(
            "The owner must transfer ownership before leaving the group."
        )

    now = timezone.now()
    member = context.actor_membership
    member.is_active = False
    member.left_at = now
    member.removed_at = None
    member.removed_by_user_id = None
    _increment_membership_version(member)
    member.save(
        update_fields=[
            "is_active",
            "left_at",
            "removed_at",
            "removed_by_user_id",
            "membership_version",
            "updated_at",
        ]
    )

    context.room.save(update_fields=["updated_at"])

    record_group_audit_event(
        room=context.room,
        actor_user_id=actor_user_id,
        event_type=GROUP_AUDIT_MEMBER_LEFT,
        target_user_id=member.user_id,
        metadata={
            "previous_role": member.role,
        },
    )
    create_member_security_transition(
        group_room=context.room,
        reason=GROUP_SECURITY_TRANSITION_REASON_MEMBER_LEFT,
        actor_user_id=actor_user_id,
        target_user_id=member.user_id,
    )
    return member


@transaction.atomic
def transfer_ownership(
    *,
    authenticated_user_id: Any,
    group_id: Any,
    new_owner_user_id: Any,
) -> dict[str, RoomMember]:
    actor_user_id = _normalize_user_id(
        authenticated_user_id,
        field_name="authenticated_user_id",
    )
    new_owner_user_id = _normalize_user_id(
        new_owner_user_id,
        field_name="new_owner_user_id",
    )

    context = _get_context_for_update(
        group_id=group_id,
        actor_user_id=actor_user_id,
    )

    if not _is_owner(context.actor_membership):
        raise GroupMembershipPermissionError(
            "Only the group owner can transfer ownership."
        )

    if new_owner_user_id == actor_user_id:
        raise GroupMembershipValidationError(
            "The target user is already the group owner."
        )

    current_owner = context.actor_membership

    target = (
        RoomMember.objects.select_for_update()
        .filter(
            room=context.room,
            user_id=new_owner_user_id,
            is_active=True,
        )
        .first()
    )

    if target is None:
        raise GroupMembershipNotFoundError(
            "New owner must be an active group member."
        )
    
    if not can_transfer_ownership(context.actor_membership, target):
        raise GroupMembershipPermissionError(
            "Only the group owner can transfer ownership to an active member."
        )

    current_owner.role = RoomMember.Role.ADMIN
    _increment_membership_version(current_owner)
    current_owner.save(
        update_fields=[
            "role",
            "membership_version",
            "updated_at",
        ]
    )

    target.role = RoomMember.Role.OWNER
    _increment_membership_version(target)
    target.save(
        update_fields=[
            "role",
            "membership_version",
            "updated_at",
        ]
    )

    context.room.save(update_fields=["updated_at"])
    
    record_group_audit_event(
        room=context.room,
        actor_user_id=actor_user_id,
        event_type=GROUP_AUDIT_OWNERSHIP_TRANSFERRED,
        target_user_id=target.user_id,
        metadata={
            "old_owner_user_id": current_owner.user_id,
            "new_owner_user_id": target.user_id,
        },
    )

    return {
        "old_owner": current_owner,
        "new_owner": target,
    }


@transaction.atomic
def ban_group_member(
    *,
    authenticated_user_id: Any,
    group_id: Any,
    target_user_id: Any,
) -> RoomMember:
    actor_user_id = _normalize_user_id(
        authenticated_user_id,
        field_name="authenticated_user_id",
    )
    target_user_id = _normalize_user_id(
        target_user_id,
        field_name="target_user_id",
    )

    context = _get_context_for_update(
        group_id=group_id,
        actor_user_id=actor_user_id,
    )

    if not can_ban_member(context.actor_membership):
        raise GroupMembershipPermissionError(
            "Only the group owner can ban members."
        )

    if target_user_id == actor_user_id:
        raise GroupMembershipValidationError(
            "The group owner cannot ban themselves."
        )

    now = timezone.now()

    target = (
        RoomMember.objects.select_for_update()
        .filter(
            room=context.room,
            user_id=target_user_id,
        )
        .first()
    )

    if target is not None and not can_ban_member(
        context.actor_membership,
        target,
    ):
        raise GroupMembershipPermissionError(
            "The group owner cannot be banned."
        )

    if target is None:
        try:
            target = RoomMember.objects.create(
                room=context.room,
                user_id=target_user_id,
                role=RoomMember.Role.MEMBER,
                added_by_user_id=actor_user_id,
                is_active=False,
                removed_at=now,
                banned_at=now,
                removed_by_user_id=actor_user_id,
                membership_version=1,
            )
        except IntegrityError as error:
            raise GroupMembershipConflictError(
                "The member could not be banned because of a conflict."
            ) from error
    else:
        target.is_active = False
        target.removed_at = now
        target.banned_at = now
        target.removed_by_user_id = actor_user_id
        target.left_at = None
        _increment_membership_version(target)
        target.save(
            update_fields=[
                "is_active",
                "removed_at",
                "banned_at",
                "removed_by_user_id",
                "left_at",
                "membership_version",
                "updated_at",
            ]
        )

    context.room.save(update_fields=["updated_at"])
    
    record_group_audit_event(
        room=context.room,
        actor_user_id=actor_user_id,
        event_type=GROUP_AUDIT_MEMBER_BANNED,
        target_user_id=target.user_id,
        metadata={
            "was_existing_member": target is not None,
        },
    )
    create_member_security_transition(
        group_room=context.room,
        reason=GROUP_SECURITY_TRANSITION_REASON_MEMBER_BANNED,
        actor_user_id=actor_user_id,
        target_user_id=target.user_id,
    )

    return target


@transaction.atomic
def unban_group_member(
    *,
    authenticated_user_id: Any,
    group_id: Any,
    target_user_id: Any,
) -> RoomMember:
    actor_user_id = _normalize_user_id(
        authenticated_user_id,
        field_name="authenticated_user_id",
    )
    target_user_id = _normalize_user_id(
        target_user_id,
        field_name="target_user_id",
    )

    context = _get_context_for_update(
        group_id=group_id,
        actor_user_id=actor_user_id,
    )

    if not can_unban_member(context.actor_membership):
        raise GroupMembershipPermissionError(
            "Only the group owner can unban members."
        )

    target = (
        RoomMember.objects.select_for_update()
        .filter(
            room=context.room,
            user_id=target_user_id,
        )
        .first()
    )

    if target is None or target.banned_at is None:
        raise GroupMembershipNotFoundError("Banned member was not found.")

    target.banned_at = None
    _increment_membership_version(target)
    target.save(
        update_fields=[
            "banned_at",
            "membership_version",
            "updated_at",
        ]
    )

    context.room.save(update_fields=["updated_at"])
    
    record_group_audit_event(
        room=context.room,
        actor_user_id=actor_user_id,
        event_type=GROUP_AUDIT_MEMBER_UNBANNED,
        target_user_id=target.user_id,
        metadata={},
    )
    
    create_member_security_transition(
        group_room=context.room,
        reason=GROUP_SECURITY_TRANSITION_REASON_MEMBER_UNBANNED,
        actor_user_id=actor_user_id,
        target_user_id=target.user_id,
    )

    return target
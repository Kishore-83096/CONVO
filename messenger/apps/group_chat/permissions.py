"""Central group authorization helpers.

Views should call services only. Services should use these functions instead
of scattering role checks.
"""

from apps.rooms.models import RoomMember

from .models import GroupProfile


def is_active_member(member: RoomMember | None) -> bool:
    return member is not None and member.is_active


def is_owner(member: RoomMember | None) -> bool:
    return is_active_member(member) and member.role == RoomMember.Role.OWNER


def is_admin(member: RoomMember | None) -> bool:
    return is_active_member(member) and member.role == RoomMember.Role.ADMIN


def is_member(member: RoomMember | None) -> bool:
    return is_active_member(member) and member.role == RoomMember.Role.MEMBER


def is_owner_or_admin(member: RoomMember | None) -> bool:
    return is_owner(member) or is_admin(member)


def can_view_group(caller_membership: RoomMember | None) -> bool:
    return is_active_member(caller_membership)


def can_update_group(
    profile: GroupProfile,
    caller_membership: RoomMember | None,
) -> bool:
    if not can_view_group(caller_membership):
        return False

    if not profile.only_admins_can_edit_info:
        return True

    return is_owner_or_admin(caller_membership)


def can_add_members(caller_membership: RoomMember | None) -> bool:
    return is_owner_or_admin(caller_membership)


def can_remove_member(
    caller_membership: RoomMember | None,
    target_membership: RoomMember | None,
) -> bool:
    if not can_view_group(caller_membership):
        return False

    if not is_active_member(target_membership):
        return False

    if is_owner(target_membership):
        return False

    if is_owner(caller_membership):
        return True

    if is_admin(caller_membership) and is_member(target_membership):
        return True

    return False


def can_change_role(
    caller_membership: RoomMember | None,
    target_membership: RoomMember | None,
    new_role: str,
) -> bool:
    if not is_owner(caller_membership):
        return False

    if not is_active_member(target_membership):
        return False

    if is_owner(target_membership):
        return False

    return new_role in {
        RoomMember.Role.ADMIN,
        RoomMember.Role.MEMBER,
    }


def can_transfer_ownership(
    caller_membership: RoomMember | None,
    target_membership: RoomMember | None,
) -> bool:
    if not is_owner(caller_membership):
        return False

    if not is_active_member(target_membership):
        return False

    if caller_membership.user_id == target_membership.user_id:
        return False

    return True


def can_leave_group(caller_membership: RoomMember | None) -> bool:
    if not can_view_group(caller_membership):
        return False

    return not is_owner(caller_membership)


def can_ban_member(
    caller_membership: RoomMember | None,
    target_membership: RoomMember | None = None,
) -> bool:
    if not is_owner(caller_membership):
        return False

    if target_membership is not None and is_owner(target_membership):
        return False

    return True


def can_unban_member(caller_membership: RoomMember | None) -> bool:
    return is_owner(caller_membership)


def can_send_group_message(
    profile: GroupProfile,
    caller_membership: RoomMember | None,
) -> bool:
    if not can_view_group(caller_membership):
        return False

    if profile.only_admins_can_send:
        return is_owner_or_admin(caller_membership)

    return True


def can_manage_sender_keys(caller_membership: RoomMember | None) -> bool:
    return can_view_group(caller_membership)


def can_read_group_history(caller_membership: RoomMember | None) -> bool:
    return can_view_group(caller_membership)
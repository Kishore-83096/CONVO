from apps.rooms.models import RoomMember


def _membership_end_time(membership):
    end_times = [
        value
        for value in [
            membership.left_at,
            membership.removed_at,
            membership.banned_at,
        ]
        if value is not None
    ]

    if end_times:
        return min(end_times)

    if not membership.is_active:
        return membership.updated_at

    return None


def message_is_authorized_for_user(
    *,
    message,
    user_id: str,
) -> bool:
    normalized_user_id = str(user_id).strip()

    if not normalized_user_id:
        return False

    memberships = RoomMember.objects.filter(
        room=message.room,
        user_id=normalized_user_id,
    ).order_by(
        "joined_at",
        "membership_version",
    )

    for membership in memberships:
        if message.created_at < membership.joined_at:
            continue

        ended_at = _membership_end_time(membership)

        if ended_at and message.created_at >= ended_at:
            continue

        return True

    return False


def room_is_currently_authorized_for_user(
    *,
    room,
    user_id: str,
) -> bool:
    return RoomMember.objects.filter(
        room=room,
        user_id=str(user_id).strip(),
        is_active=True,
    ).exists()
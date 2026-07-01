import uuid
from datetime import timedelta

import jwt
from django.conf import settings
from django.utils import timezone

from apps.group_chat.models import GroupProfile
from apps.rooms.models import Room, RoomMember

GROUP_OWNER_USER_ID = "1"
GROUP_ADMIN_USER_ID = "2"
GROUP_MEMBER_USER_ID = "3"
GROUP_SECOND_MEMBER_USER_ID = "4"
GROUP_OUTSIDER_USER_ID = "5"
GROUP_NEW_MEMBER_USER_ID = "6"


def build_access_token(user_id: str) -> str:
    now = timezone.now()
    return jwt.encode(
        {
            "sub": user_id,
            "type": "access",
            "iss": settings.JWT_ISSUER,
            "jti": str(uuid.uuid4()),
            "iat": now,
            "nbf": now,
            "exp": now + timedelta(minutes=5),
        },
        settings.JWT_VERIFYING_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def authenticate_client(client, user_id: str):
    token = build_access_token(user_id)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return token


def create_group_room(
    *,
    owner_user_id: str = GROUP_OWNER_USER_ID,
    admin_user_ids: list[str] | None = None,
    member_user_ids: list[str] | None = None,
    name: str = "Backend Engineering",
    max_members: int = 100,
    only_admins_can_edit_info: bool = True,
) -> GroupProfile:
    from apps.group_chat.services.epochs import create_initial_epoch_for_group

    admin_user_ids = admin_user_ids or []
    member_user_ids = member_user_ids or [GROUP_MEMBER_USER_ID]

    room = Room.objects.create(
        room_type=Room.RoomType.GROUP,
        name=name,
        created_by_user_id=owner_user_id,
        direct_pair_key=None,
        is_active=True,
    )

    profile = GroupProfile.objects.create(
        room=room,
        description="Myna backend team",
        created_by_user_id=owner_user_id,
        max_members=max_members,
        join_history_visible=False,
        only_admins_can_send=False,
        only_admins_can_edit_info=only_admins_can_edit_info,
    )

    RoomMember.objects.create(
        room=room,
        user_id=owner_user_id,
        role=RoomMember.Role.OWNER,
        added_by_user_id=owner_user_id,
        is_active=True,
    )

    for admin_user_id in admin_user_ids:
        RoomMember.objects.create(
            room=room,
            user_id=admin_user_id,
            role=RoomMember.Role.ADMIN,
            added_by_user_id=owner_user_id,
            is_active=True,
        )

    for member_user_id in member_user_ids:
        RoomMember.objects.create(
            room=room,
            user_id=member_user_id,
            role=RoomMember.Role.MEMBER,
            added_by_user_id=owner_user_id,
            is_active=True,
        )

    create_initial_epoch_for_group(
        room=room,
        actor_user_id=owner_user_id,
    )

    return profile

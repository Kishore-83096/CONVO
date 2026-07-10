import hashlib
from dataclasses import dataclass
from typing import Any
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from django.utils import timezone

from apps.rooms.models import Room, RoomMember

from .models import (
    ContactDeliveryPolicy,
    DirectContactState,
)

class ContactPolicyError(Exception):
    """Base contact-policy projection error."""


class ContactPolicyValidationError(ContactPolicyError):
    """Invalid contact-policy projection input."""



@dataclass(frozen=True, slots=True)
class DirectContactStateSyncResult:
    contact_state: DirectContactState | None
    room: Room | None
    created: bool
    updated: bool
    ignored_no_room: bool
    ignored_stale_update: bool

@dataclass(frozen=True, slots=True)
class ContactPolicySyncResult:
    policy: ContactDeliveryPolicy
    created: bool
    updated: bool
    ignored_stale_update: bool


@dataclass(frozen=True, slots=True)
class DeliveryPolicySnapshot:
    is_blocked: bool
    ghost_active: bool
    policy_version: int | None


def normalize_external_user_id(
    value: Any,
    *,
    field_name: str,
) -> str:
    user_id = str(value).strip()

    if not user_id:
        raise ContactPolicyValidationError(
            f"{field_name} is required."
        )

    return user_id

def policy_ghost_is_active(
    policy: ContactDeliveryPolicy | None,
) -> bool:
    if policy is None:
        return False

    if policy.ghost_permanent:
        return True

    if policy.ghost_until is None:
        return False

    return policy.ghost_until > timezone.now()


DELIVERY_POLICY_SNAPSHOT_CACHE_TTL_SECONDS = 600


def get_delivery_policy_cache_key(
    *,
    recipient_user_id: Any,
    sender_user_id: Any,
) -> str:
    return (
        "delivery_policy:"
        f"{str(recipient_user_id).strip()}:"
        f"{str(sender_user_id).strip()}"
    )


def invalidate_delivery_policy_cache_for_pair(
    *,
    recipient_user_id: Any,
    sender_user_id: Any,
) -> None:
    recipient_id = str(recipient_user_id).strip()
    sender_id = str(sender_user_id).strip()

    if not recipient_id or not sender_id:
        return

    cache.delete(
        get_delivery_policy_cache_key(
            recipient_user_id=recipient_id,
            sender_user_id=sender_id,
        )
    )


def invalidate_delivery_policy_cache_after_change(
    *,
    recipient_user_id: Any,
    sender_user_id: Any,
) -> None:
    invalidate_delivery_policy_cache_for_pair(
        recipient_user_id=recipient_user_id,
        sender_user_id=sender_user_id,
    )
    transaction.on_commit(
        lambda: invalidate_delivery_policy_cache_for_pair(
            recipient_user_id=recipient_user_id,
            sender_user_id=sender_user_id,
        )
    )


def _normal_delivery_policy_snapshot() -> DeliveryPolicySnapshot:
    return DeliveryPolicySnapshot(
        is_blocked=False,
        ghost_active=False,
        policy_version=None,
    )


def _delivery_policy_cache_timeout(
    policy: ContactDeliveryPolicy | None,
) -> int:
    if policy is None:
        return DELIVERY_POLICY_SNAPSHOT_CACHE_TTL_SECONDS

    if not policy.ghost_until or policy.ghost_permanent:
        return DELIVERY_POLICY_SNAPSHOT_CACHE_TTL_SECONDS

    if not policy_ghost_is_active(policy):
        return DELIVERY_POLICY_SNAPSHOT_CACHE_TTL_SECONDS

    seconds_until_expiry = int(
        (policy.ghost_until - timezone.now()).total_seconds()
    )

    return max(
        1,
        min(
            DELIVERY_POLICY_SNAPSHOT_CACHE_TTL_SECONDS,
            seconds_until_expiry,
        ),
    )


def _snapshot_from_cache_value(
    cached_value: Any,
) -> DeliveryPolicySnapshot | None:
    if not isinstance(cached_value, dict):
        return None

    if "is_blocked" not in cached_value or "ghost_active" not in cached_value:
        return None

    return DeliveryPolicySnapshot(
        is_blocked=bool(cached_value["is_blocked"]),
        ghost_active=bool(cached_value["ghost_active"]),
        policy_version=cached_value.get("policy_version"),
    )


def _cache_delivery_policy_snapshot(
    *,
    cache_key: str,
    snapshot: DeliveryPolicySnapshot,
    policy: ContactDeliveryPolicy | None,
) -> None:
    cache.set(
        cache_key,
        {
            "is_blocked": snapshot.is_blocked,
            "ghost_active": snapshot.ghost_active,
            "policy_version": snapshot.policy_version,
        },
        _delivery_policy_cache_timeout(policy),
    )


def get_delivery_policy_snapshot(
    *,
    recipient_user_id: Any,
    sender_user_id: Any,
) -> DeliveryPolicySnapshot:
    recipient_id = str(recipient_user_id).strip()
    sender_id = str(sender_user_id).strip()

    if not recipient_id or not sender_id or recipient_id == sender_id:
        return _normal_delivery_policy_snapshot()

    cache_key = get_delivery_policy_cache_key(
        recipient_user_id=recipient_id,
        sender_user_id=sender_id,
    )
    cached_snapshot = _snapshot_from_cache_value(
        cache.get(cache_key)
    )

    if cached_snapshot is not None:
        return cached_snapshot

    policy = (
        ContactDeliveryPolicy.objects.only(
            "is_blocked",
            "ghost_until",
            "ghost_permanent",
            "policy_version",
        )
        .filter(
            owner_user_id=recipient_id,
            target_user_id=sender_id,
        )
        .first()
    )

    if policy is None:
        snapshot = _normal_delivery_policy_snapshot()
    else:
        snapshot = DeliveryPolicySnapshot(
            is_blocked=bool(policy.is_blocked),
            ghost_active=policy_ghost_is_active(policy),
            policy_version=policy.policy_version,
        )

    _cache_delivery_policy_snapshot(
        cache_key=cache_key,
        snapshot=snapshot,
        policy=policy,
    )

    return snapshot

def recipient_has_blocked_sender(
    *,
    recipient_user_id: Any,
    sender_user_id: Any,
) -> bool:
    return get_delivery_policy_snapshot(
        recipient_user_id=recipient_user_id,
        sender_user_id=sender_user_id,
    ).is_blocked




def can_view_presence(
    *,
    viewer_user_id: Any,
    subject_user_id: Any,
) -> bool:
    """
    Directional presence visibility rule.

    viewer_user_id:
        The user who wants to see presence.

    subject_user_id:
        The user whose presence is being viewed.

    Rule:
        If subject blocked viewer, viewer cannot see subject.
        If subject ghosted viewer and the ghost is active, viewer cannot
        see subject.
        Otherwise presence is visible.

    Example:
        A blocks B:
            can_view_presence(viewer=B, subject=A) == False
            can_view_presence(viewer=A, subject=B) == True
            unless B also restricted A.

        A ghosts B:
            can_view_presence(viewer=B, subject=A) == False
            until ghost expiry.
            can_view_presence(viewer=A, subject=B) == True
            unless B also restricted A.
    """

    viewer_id = str(viewer_user_id).strip()
    subject_id = str(subject_user_id).strip()

    if not viewer_id or not subject_id:
        return False

    if viewer_id == subject_id:
        return True

    subject_policy_against_viewer = get_delivery_policy_snapshot(
        recipient_user_id=subject_id,
        sender_user_id=viewer_id,
    )

    if subject_policy_against_viewer.is_blocked:
        return False

    if subject_policy_against_viewer.ghost_active:
        return False

    return True


def can_publish_receipt_to_sender(
    *,
    reader_user_id: Any,
    sender_user_id: Any,
) -> bool:
    """
    Directional receipt publishing rule.

    reader_user_id:
        The user/device that delivered or read the message.

    sender_user_id:
        The original sender who would receive delivered/read status.

    Rule:
        If reader blocked sender, do not publish delivered/read.
        If reader ghosted sender and ghost is active, do not publish
        delivered/read.
        Otherwise publishing receipts is allowed.

    Important:
        This controls whether the sender receives realtime receipt events.
        It must not reveal block/ghost reason to the sender.
    """

    reader_id = str(reader_user_id).strip()
    sender_id = str(sender_user_id).strip()

    if not reader_id or not sender_id:
        return False

    if reader_id == sender_id:
        return True

    reader_policy_against_sender = get_delivery_policy_snapshot(
        recipient_user_id=reader_id,
        sender_user_id=sender_id,
    )

    if reader_policy_against_sender.is_blocked:
        return False

    if reader_policy_against_sender.ghost_active:
        return False

    return True


def can_send_typing_to_viewer(
    *,
    viewer_user_id: Any,
    subject_user_id: Any,
) -> bool:
    """
    Typing visibility is presence-like.

    If viewer cannot see subject presence, viewer must not see subject
    typing.
    """

    return can_view_presence(
        viewer_user_id=viewer_user_id,
        subject_user_id=subject_user_id,
    )




@transaction.atomic
def upsert_contact_delivery_policy(
    *,
    owner_user_id: Any,
    target_user_id: Any,
    is_blocked: bool,
    policy_version: int,
    ghost_until=None,
    ghost_permanent: bool = False,
    ghost_duration_option: str | None = "",
    source_updated_at=None,
) -> ContactPolicySyncResult:
    owner_id = normalize_external_user_id(
        owner_user_id,
        field_name="owner_user_id",
    )

    target_id = normalize_external_user_id(
        target_user_id,
        field_name="target_user_id",
    )

    if owner_id == target_id:
        raise ContactPolicyValidationError(
            "target_user_id must be different from owner_user_id."
        )

    try:
        version = int(policy_version)
    except (TypeError, ValueError) as error:
        raise ContactPolicyValidationError(
            "policy_version must be an integer."
        ) from error

    if version < 1:
        raise ContactPolicyValidationError(
            "policy_version must be at least 1."
        )

    normalized_ghost_duration_option = str(
        ghost_duration_option or ""
    ).strip()

    allowed_ghost_options = {
        "",
        "1h",
        "6h",
        "12h",
        "24h",
        "permanent",
    }

    if normalized_ghost_duration_option not in allowed_ghost_options:
        raise ContactPolicyValidationError(
            "ghost_duration_option is invalid."
        )

    policy = (
        ContactDeliveryPolicy.objects
        .select_for_update()
        .filter(
            owner_user_id=owner_id,
            target_user_id=target_id,
        )
        .first()
    )

    if policy is not None:
        if version < policy.policy_version:
            return ContactPolicySyncResult(
                policy=policy,
                created=False,
                updated=False,
                ignored_stale_update=True,
            )

        if (
            version == policy.policy_version
            and source_updated_at is not None
            and policy.source_updated_at is not None
            and source_updated_at < policy.source_updated_at
        ):
            return ContactPolicySyncResult(
                policy=policy,
                created=False,
                updated=False,
                ignored_stale_update=True,
            )

    created = policy is None

    if policy is None:
        policy = ContactDeliveryPolicy(
            owner_user_id=owner_id,
            target_user_id=target_id,
        )

    changed = (
        created
        or policy.is_blocked != bool(is_blocked)
        or policy.ghost_until != ghost_until
        or policy.ghost_permanent != bool(ghost_permanent)
        or policy.ghost_duration_option != normalized_ghost_duration_option
        or policy.policy_version != version
        or policy.source_updated_at != source_updated_at
    )

    policy.is_blocked = bool(is_blocked)
    policy.ghost_until = ghost_until
    policy.ghost_permanent = bool(ghost_permanent)
    policy.ghost_duration_option = normalized_ghost_duration_option
    policy.policy_version = version
    policy.source_updated_at = source_updated_at

    if changed:
        try:
            policy.full_clean()
            policy.save()
            invalidate_delivery_policy_cache_after_change(
                recipient_user_id=owner_id,
                sender_user_id=target_id,
            )
        except ValidationError as error:
            raise ContactPolicyValidationError(
                error.message_dict
                if hasattr(error, "message_dict")
                else str(error)
            ) from error
        except IntegrityError as error:
            raise ContactPolicyValidationError(
                "Could not save contact delivery policy."
            ) from error

    return ContactPolicySyncResult(
        policy=policy,
        created=created,
        updated=changed,
        ignored_stale_update=False,
    )



def build_existing_direct_pair_key(
    first_user_id: Any,
    second_user_id: Any,
) -> str:
    """
    Build the same direct-pair key currently used by the send-message service.

    Important:
        Do not use Room.build_direct_pair_key here yet because the current
        send service uses the colon-join hash format.
    """

    first = str(first_user_id).strip()
    second = str(second_user_id).strip()

    if not first or not second:
        raise ContactPolicyValidationError(
            "Both direct-room user IDs are required."
        )

    if first == second:
        raise ContactPolicyValidationError(
            "Direct contact state requires two different users."
        )

    normalized_pair = ":".join(
        sorted(
            [
                first,
                second,
            ]
        )
    )

    return hashlib.sha256(
        normalized_pair.encode("utf-8")
    ).hexdigest()


def find_existing_active_direct_room(
    *,
    first_user_id: Any,
    second_user_id: Any,
) -> Room | None:
    """
    Return the existing active direct room for two users.

    If no direct room exists, return None.
    This function must not create a room.
    """

    first_id = normalize_external_user_id(
        first_user_id,
        field_name="first_user_id",
    )
    second_id = normalize_external_user_id(
        second_user_id,
        field_name="second_user_id",
    )

    pair_key = build_existing_direct_pair_key(
        first_id,
        second_id,
    )

    room = (
        Room.objects
        .filter(
            room_type=Room.RoomType.DIRECT,
            direct_pair_key=pair_key,
            is_active=True,
        )
        .first()
    )

    if room is None:
        return None

    active_member_ids = set(
        RoomMember.objects.filter(
            room=room,
            is_active=True,
            user_id__in=[
                first_id,
                second_id,
            ],
        ).values_list(
            "user_id",
            flat=True,
        )
    )

    if active_member_ids != {
        first_id,
        second_id,
    }:
        return None

    return room


@transaction.atomic
def sync_direct_contact_state_if_room_exists(
    *,
    owner_user_id: Any,
    contact_user_id: Any,
    is_saved: bool,
    identity_contact_id: int | None = None,
    source_updated_at=None,
) -> DirectContactStateSyncResult:
    """
    Sync saved-contact state from Identity into Messenger only when
    a direct room already exists.

    Product rule:
        - If no direct room exists, do nothing.
        - If direct room exists, upsert directional saved state.
        - owner_user_id -> contact_user_id is directional.
    """

    owner_id = normalize_external_user_id(
        owner_user_id,
        field_name="owner_user_id",
    )

    contact_id = normalize_external_user_id(
        contact_user_id,
        field_name="contact_user_id",
    )

    if owner_id == contact_id:
        raise ContactPolicyValidationError(
            "contact_user_id must be different from owner_user_id."
        )

    room = find_existing_active_direct_room(
        first_user_id=owner_id,
        second_user_id=contact_id,
    )

    if room is None:
        return DirectContactStateSyncResult(
            contact_state=None,
            room=None,
            created=False,
            updated=False,
            ignored_no_room=True,
            ignored_stale_update=False,
        )

    contact_state = (
        DirectContactState.objects
        .select_for_update()
        .filter(
            owner_user_id=owner_id,
            contact_user_id=contact_id,
        )
        .first()
    )

    if (
        contact_state is not None
        and source_updated_at is not None
        and contact_state.source_updated_at is not None
        and source_updated_at < contact_state.source_updated_at
    ):
        return DirectContactStateSyncResult(
            contact_state=contact_state,
            room=room,
            created=False,
            updated=False,
            ignored_no_room=False,
            ignored_stale_update=True,
        )

    created = contact_state is None

    if contact_state is None:
        contact_state = DirectContactState(
            room=room,
            owner_user_id=owner_id,
            contact_user_id=contact_id,
        )

    changed = (
        created
        or contact_state.room_id != room.id
        or contact_state.identity_contact_id != identity_contact_id
        or contact_state.is_saved != bool(is_saved)
        or contact_state.source_updated_at != source_updated_at
    )

    contact_state.room = room
    contact_state.identity_contact_id = identity_contact_id
    contact_state.is_saved = bool(is_saved)
    contact_state.source_updated_at = source_updated_at

    if changed:
        try:
            contact_state.full_clean()
            contact_state.save()
        except ValidationError as error:
            raise ContactPolicyValidationError(
                error.message_dict
                if hasattr(error, "message_dict")
                else str(error)
            ) from error
        except IntegrityError as error:
            raise ContactPolicyValidationError(
                "Could not save direct contact state."
            ) from error

    return DirectContactStateSyncResult(
        contact_state=contact_state,
        room=room,
        created=created,
        updated=changed,
        ignored_no_room=False,
        ignored_stale_update=False,
    )




def sender_has_saved_direct_contact(
    *,
    sender_user_id: Any,
    recipient_user_id: Any,
) -> bool:
    """
    Return True only when sender currently has recipient saved.

    This is directional:

        sender_user_id -> recipient_user_id

    Product rule:
        A user can send direct messages only to users they currently have
        saved as contacts.

    Receiving is separate and is controlled by recipient block/ghost policy.
    """

    sender_id = normalize_external_user_id(
        sender_user_id,
        field_name="sender_user_id",
    )

    recipient_id = normalize_external_user_id(
        recipient_user_id,
        field_name="recipient_user_id",
    )

    if sender_id == recipient_id:
        return False

    return DirectContactState.objects.filter(
        owner_user_id=sender_id,
        contact_user_id=recipient_id,
        is_saved=True,
    ).exists()
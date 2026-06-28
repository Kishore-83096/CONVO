from dataclasses import dataclass
from typing import Any

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import ContactDeliveryPolicy


class ContactPolicyError(Exception):
    """Base contact-policy projection error."""


class ContactPolicyValidationError(ContactPolicyError):
    """Invalid contact-policy projection input."""


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


def get_delivery_policy_snapshot(
    *,
    recipient_user_id: Any,
    sender_user_id: Any,
) -> DeliveryPolicySnapshot:
    recipient_id = str(recipient_user_id).strip()
    sender_id = str(sender_user_id).strip()

    if not recipient_id or not sender_id or recipient_id == sender_id:
        return DeliveryPolicySnapshot(
            is_blocked=False,
            ghost_active=False,
            policy_version=None,
        )

    policy = ContactDeliveryPolicy.objects.filter(
        owner_user_id=recipient_id,
        target_user_id=sender_id,
    ).first()

    if policy is None:
        return DeliveryPolicySnapshot(
            is_blocked=False,
            ghost_active=False,
            policy_version=None,
        )

    return DeliveryPolicySnapshot(
        is_blocked=bool(policy.is_blocked),
        ghost_active=policy_ghost_is_active(policy),
        policy_version=policy.policy_version,
    )


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
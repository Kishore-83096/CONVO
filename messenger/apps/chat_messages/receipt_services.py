from dataclasses import dataclass
from typing import Any
from uuid import UUID

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.e2ee_devices.models import Device
from apps.rooms.models import Room

from .access_selectors import message_is_authorized_for_user
from .models import DirectMessageReceiptDecision, Message, MessageReceipt

class ReceiptServiceError(Exception):
    """Base receipt error."""


class ReceiptValidationError(ReceiptServiceError):
    """Invalid receipt input."""


class ReceiptNotFoundError(ReceiptServiceError):
    """Message/device not found or intentionally hidden."""


class ReceiptPermissionError(ReceiptServiceError):
    """Receipt action is not allowed."""


class ReceiptConflictError(ReceiptServiceError):
    """Receipt state conflict."""


@dataclass(frozen=True, slots=True)
class DeliveredReceiptResult:
    updated_count: int
    receipt_ids: list[UUID]


@dataclass(frozen=True, slots=True)
class ReadReceiptResult:
    updated_count: int
    receipt_ids: list[UUID]


@dataclass(frozen=True, slots=True)
class MessageReceiptSummary:
    message_id: UUID
    delivered_count: int
    read_count: int
    receipts: list[MessageReceipt]


def _normalize_user_id(
    value: Any,
    *,
    field_name: str,
) -> str:
    user_id = str(value).strip()

    if not user_id:
        raise ReceiptValidationError(f"{field_name} is required.")

    return user_id


def _owned_active_device(
    *,
    device_id,
    user_id: str,
) -> Device:
    try:
        device_uuid = UUID(str(device_id))
    except (TypeError, ValueError, AttributeError) as error:
        raise ReceiptValidationError(
            "device_id must be a valid UUID."
        ) from error

    device = Device.objects.filter(
        id=device_uuid,
        user_id=user_id,
        is_active=True,
    ).first()

    if device is None:
        raise ReceiptNotFoundError("Device was not found.")

    return device


def _get_authorized_message(
    *,
    message_id,
    user_id: str,
) -> Message:
    try:
        message_uuid = UUID(str(message_id))
    except (TypeError, ValueError, AttributeError) as error:
        raise ReceiptValidationError(
            "message_id must be a valid UUID."
        ) from error

    message = (
        Message.objects.select_related("room")
        .filter(id=message_uuid)
        .first()
    )

    if message is None:
        raise ReceiptNotFoundError("Message was not found.")

    if not message_is_authorized_for_user(
        message=message,
        user_id=user_id,
    ):
        raise ReceiptNotFoundError("Message was not found.")

    return message


def _upsert_receipt(
    *,
    message: Message,
    recipient_user_id: str,
    recipient_device: Device,
    delivered_at=None,
    read_at=None,
) -> tuple[MessageReceipt, bool]:
    receipt, created = MessageReceipt.objects.select_for_update().get_or_create(
        message=message,
        recipient_user_id=recipient_user_id,
        recipient_device=recipient_device,
        defaults={
            "delivered_at": delivered_at,
            "read_at": read_at,
        },
    )

    changed = created

    if delivered_at is not None:
        if receipt.delivered_at is None or delivered_at > receipt.delivered_at:
            receipt.delivered_at = delivered_at
            changed = True

    if read_at is not None:
        if receipt.read_at is None or read_at > receipt.read_at:
            receipt.read_at = read_at
            changed = True

        if receipt.delivered_at is None or read_at > receipt.delivered_at:
            receipt.delivered_at = read_at
            changed = True

    if changed:
        try:
            receipt.full_clean()
            receipt.save()
        except DjangoValidationError as error:
            raise ReceiptValidationError(
                error.message_dict
                if hasattr(error, "message_dict")
                else str(error)
            ) from error
        except IntegrityError as error:
            raise ReceiptConflictError(
                "Could not store receipt because of a conflict."
            ) from error

    return receipt, changed




def _receipt_is_suppressed(
    *,
    message: Message,
    recipient_user_id: str,
    receipt_type: str,
) -> bool:
    decision = (
        DirectMessageReceiptDecision.objects.filter(
            message=message,
            recipient_user_id=recipient_user_id,
        )
        .only(
            "suppress_delivered_receipt",
            "suppress_read_receipt",
        )
        .first()
    )

    if decision is None:
        return False

    if receipt_type == "delivered":
        return decision.suppress_delivered_receipt

    if receipt_type == "read":
        return decision.suppress_read_receipt

    return False



@transaction.atomic
def mark_messages_delivered(
    *,
    authenticated_user_id: Any,
    device_id,
    message_ids: list,
) -> DeliveredReceiptResult:
    user_id = _normalize_user_id(
        authenticated_user_id,
        field_name="authenticated_user_id",
    )

    if not message_ids:
        raise ReceiptValidationError("message_ids cannot be empty.")

    device = _owned_active_device(
        device_id=device_id,
        user_id=user_id,
    )

    now = timezone.now()
    receipt_ids = []
    updated_count = 0

    for message_id in message_ids:
        message = _get_authorized_message(
            message_id=message_id,
            user_id=user_id,
        )

        if message.sender_user_id == user_id:
            continue

        if _receipt_is_suppressed(
            message=message,
            recipient_user_id=user_id,
            receipt_type="delivered",
        ):
            continue

        receipt, changed = _upsert_receipt(
            message=message,
            recipient_user_id=user_id,
            recipient_device=device,
            delivered_at=now,
        )

        receipt_ids.append(receipt.id)

        if changed:
            updated_count += 1

    return DeliveredReceiptResult(
        updated_count=updated_count,
        receipt_ids=receipt_ids,
    )


@transaction.atomic
def mark_group_read_through(
    *,
    authenticated_user_id: Any,
    device_id,
    group_id,
    read_through_message_id,
) -> ReadReceiptResult:
    user_id = _normalize_user_id(
        authenticated_user_id,
        field_name="authenticated_user_id",
    )

    device = _owned_active_device(
        device_id=device_id,
        user_id=user_id,
    )

    try:
        group_uuid = UUID(str(group_id))
    except (TypeError, ValueError, AttributeError) as error:
        raise ReceiptValidationError(
            "group_id must be a valid UUID."
        ) from error

    read_through_message = _get_authorized_message(
        message_id=read_through_message_id,
        user_id=user_id,
    )

    if read_through_message.room_id != group_uuid:
        raise ReceiptValidationError(
            "read_through_message_id must belong to group_id."
        )

    if read_through_message.room.room_type != Room.RoomType.GROUP:
        raise ReceiptValidationError(
            "Read-through receipts are only supported for groups."
        )

    now = timezone.now()
    receipt_ids = []
    updated_count = 0

    candidate_messages = (
        Message.objects.select_related("room")
        .filter(
            room_id=group_uuid,
            created_at__lte=read_through_message.created_at,
        )
        .exclude(sender_user_id=user_id)
        .order_by("created_at", "id")
    )

    for message in candidate_messages:
        if not message_is_authorized_for_user(
            message=message,
            user_id=user_id,
        ):
            continue

        if _receipt_is_suppressed(
            message=message,
            recipient_user_id=user_id,
            receipt_type="read",
        ):
            continue

        receipt, changed = _upsert_receipt(
            message=message,
            recipient_user_id=user_id,
            recipient_device=device,
            delivered_at=now,
            read_at=now,
        )

        receipt_ids.append(receipt.id)

        if changed:
            updated_count += 1

    return ReadReceiptResult(
        updated_count=updated_count,
        receipt_ids=receipt_ids,
    )


def get_message_receipt_summary(
    *,
    authenticated_user_id: Any,
    message_id,
) -> MessageReceiptSummary:
    user_id = _normalize_user_id(
        authenticated_user_id,
        field_name="authenticated_user_id",
    )

    message = _get_authorized_message(
        message_id=message_id,
        user_id=user_id,
    )

    receipts = list(
        MessageReceipt.objects.filter(
            message=message,
        )
        .select_related("recipient_device")
        .order_by(
            "recipient_user_id",
            "recipient_device_id",
        )
    )

    delivered_count = sum(
        1
        for receipt in receipts
        if receipt.delivered_at is not None
    )

    read_count = sum(
        1
        for receipt in receipts
        if receipt.read_at is not None
    )

    return MessageReceiptSummary(
        message_id=message.id,
        delivered_count=delivered_count,
        read_count=read_count,
        receipts=receipts,
    )
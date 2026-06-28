from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from typing import Any

from asgiref.sync import async_to_sync
from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from django.db import transaction
from .outbox import send_realtime_group_event
from apps.chat_messages.models import (
    GroupMessageEncryption,
    Message,
    MessageReceipt,
)

from apps.e2ee_devices.models import Device
from apps.rooms.models import RoomMember
from .events import (
    GROUP_MESSAGE_STORED,
    MESSAGE_DELIVERED,
    MESSAGE_READ,
    MESSAGE_STORED,
    PRESENCE_CHANGED,
    PRESENCE_HIDDEN,
    build_event,
)
from .policies import can_publish_receipt_to_sender
from .services import (
    UNAVAILABLE_PRESENCE_STATUS,
    get_presence_snapshot_for_viewer,
)



logger = logging.getLogger(__name__)


_GROUP_SAFE_PATTERN = re.compile(r"^[a-zA-Z0-9_.-]+$")


@dataclass(frozen=True, slots=True)
class PresencePublishResult:
    subject_user_id: str
    requested_viewer_count: int
    unique_viewer_count: int
    sent_count: int
    visible_count: int
    hidden_count: int
    viewer_user_ids: tuple[str, ...]


def make_safe_group_suffix(value: Any) -> str:
    raw_value = str(value).strip()

    if raw_value and _GROUP_SAFE_PATTERN.fullmatch(raw_value):
        return raw_value

    return hashlib.sha256(
        raw_value.encode("utf-8"),
    ).hexdigest()


def make_user_group_name(user_id: Any) -> str:
    return f"user.{make_safe_group_suffix(user_id)}"

def make_device_group_name(device_id: Any) -> str:
    return f"device.{make_safe_group_suffix(device_id)}"

def normalize_viewer_user_ids(
    viewer_user_ids: list[Any] | tuple[Any, ...],
) -> tuple[str, ...]:
    normalized = []

    for viewer_user_id in viewer_user_ids:
        value = str(viewer_user_id).strip()

        if value and value not in normalized:
            normalized.append(value)

    return tuple(normalized)


async def publish_presence_to_viewers(
    *,
    subject_user_id: Any,
    viewer_user_ids: list[Any] | tuple[Any, ...],
) -> PresencePublishResult:
    """
    Publish one filtered presence event to each viewer.

    Important privacy rule:
        Each viewer receives a snapshot filtered by
        get_presence_snapshot_for_viewer().

    If the viewer is allowed:
        event type = presence.changed

    If the viewer is blocked/ghosted/hidden:
        event type = presence.hidden

    Never expose the reason for hidden presence.
    """

    normalized_subject_user_id = str(subject_user_id).strip()
    normalized_viewer_user_ids = normalize_viewer_user_ids(
        viewer_user_ids,
    )

    channel_layer = get_channel_layer()

    if channel_layer is None:
        return PresencePublishResult(
            subject_user_id=normalized_subject_user_id,
            requested_viewer_count=len(viewer_user_ids),
            unique_viewer_count=len(normalized_viewer_user_ids),
            sent_count=0,
            visible_count=0,
            hidden_count=0,
            viewer_user_ids=normalized_viewer_user_ids,
        )

    sent_count = 0
    visible_count = 0
    hidden_count = 0

    for viewer_user_id in normalized_viewer_user_ids:
        snapshot = await get_presence_snapshot_for_viewer(
            viewer_user_id=viewer_user_id,
            subject_user_id=normalized_subject_user_id,
        )

        if snapshot["status"] == UNAVAILABLE_PRESENCE_STATUS:
            event_type = PRESENCE_HIDDEN
            hidden_count += 1
        else:
            event_type = PRESENCE_CHANGED
            visible_count += 1

        websocket_payload = build_event(
            event_type,
            {
                "presence": snapshot,
            },
        )

        sent = await send_realtime_group_event(
            event_type=websocket_payload["type"],
            target_group=make_user_group_name(viewer_user_id),
            payload=websocket_payload,
        )

        if sent:
            sent_count += 1

    return PresencePublishResult(
        subject_user_id=normalized_subject_user_id,
        requested_viewer_count=len(viewer_user_ids),
        unique_viewer_count=len(normalized_viewer_user_ids),
        sent_count=sent_count,
        visible_count=visible_count,
        hidden_count=hidden_count,
        viewer_user_ids=normalized_viewer_user_ids,
    )



@database_sync_to_async
def get_presence_viewer_user_ids_for_subject(
    *,
    subject_user_id: Any,
) -> tuple[str, ...]:
    """
    Return users who may care about this user's presence changes.

    For now, this means:
        all active room co-members of the subject user.

    Privacy is not decided here.
    Privacy is enforced later by get_presence_snapshot_for_viewer().
    """

    normalized_subject_user_id = str(subject_user_id).strip()

    if not normalized_subject_user_id:
        return tuple()

    active_room_ids = (
        RoomMember.objects
        .filter(
            user_id=normalized_subject_user_id,
            is_active=True,
            room__is_active=True,
        )
        .values_list(
            "room_id",
            flat=True,
        )
    )

    viewer_user_ids = (
        RoomMember.objects
        .filter(
            room_id__in=active_room_ids,
            is_active=True,
            room__is_active=True,
        )
        .exclude(
            user_id=normalized_subject_user_id,
        )
        .values_list(
            "user_id",
            flat=True,
        )
        .distinct()
        .order_by("user_id")
    )

    return tuple(
        str(user_id).strip()
        for user_id in viewer_user_ids
        if str(user_id).strip()
    )


async def publish_presence_to_related_viewers(
    *,
    subject_user_id: Any,
) -> PresencePublishResult:
    """
    Publish the subject user's filtered presence to active room co-members.

    This function intentionally does not decide whether each viewer is
    allowed to see presence. publish_presence_to_viewers() already applies
    the per-viewer privacy filter.
    """

    viewer_user_ids = await get_presence_viewer_user_ids_for_subject(
        subject_user_id=subject_user_id,
    )

    return await publish_presence_to_viewers(
        subject_user_id=subject_user_id,
        viewer_user_ids=viewer_user_ids,
    )





@dataclass(frozen=True, slots=True)
class DirectMessageStoredPublishResult:
    message_id: str
    recipient_user_id: str
    recipient_device_ids: tuple[str, ...]
    sent_count: int
    skipped: bool = False


@database_sync_to_async
def get_direct_message_stored_event_payload(
    *,
    message_id: Any,
    recipient_user_id: Any,
) -> tuple[dict[str, Any], tuple[str, ...]]:
    """
    Build a safe message.stored payload.

    This payload intentionally contains only metadata.
    The frontend must fetch encrypted history through REST.
    """

    normalized_recipient_user_id = str(recipient_user_id).strip()

    message = (
        Message.objects
        .select_related("room")
        .prefetch_related("key_envelopes")
        .get(id=message_id)
    )

    recipient_device_ids = tuple(
        str(device_id)
        for device_id in (
            message.key_envelopes
            .filter(
                recipient_user_id=normalized_recipient_user_id,
            )
            .order_by("recipient_device_id")
            .values_list(
                "recipient_device_id",
                flat=True,
            )
        )
    )

    payload = {
        "room_id": str(message.room_id),
        "message_id": str(message.id),
        "client_message_id": str(message.client_message_id),
        "sender_user_id": str(message.sender_user_id),
        "message_type": message.message_type,
        "requires_fetch": True,
    }

    return payload, recipient_device_ids


async def publish_direct_message_stored(
    *,
    message_id: Any,
    recipient_user_id: Any,
) -> DirectMessageStoredPublishResult:
    """
    Publish message.stored to recipient device groups.

    This must only be called for newly-created direct messages where
    recipient delivery was allowed.
    """

    normalized_message_id = str(message_id).strip()
    normalized_recipient_user_id = str(recipient_user_id).strip()

    if not normalized_message_id or not normalized_recipient_user_id:
        return DirectMessageStoredPublishResult(
            message_id=normalized_message_id,
            recipient_user_id=normalized_recipient_user_id,
            recipient_device_ids=tuple(),
            sent_count=0,
            skipped=True,
        )

    channel_layer = get_channel_layer()

    if channel_layer is None:
        return DirectMessageStoredPublishResult(
            message_id=normalized_message_id,
            recipient_user_id=normalized_recipient_user_id,
            recipient_device_ids=tuple(),
            sent_count=0,
            skipped=True,
        )

    event_payload, recipient_device_ids = (
        await get_direct_message_stored_event_payload(
            message_id=normalized_message_id,
            recipient_user_id=normalized_recipient_user_id,
        )
    )

    if not recipient_device_ids:
        return DirectMessageStoredPublishResult(
            message_id=normalized_message_id,
            recipient_user_id=normalized_recipient_user_id,
            recipient_device_ids=tuple(),
            sent_count=0,
            skipped=True,
        )

    websocket_payload = build_event(
        MESSAGE_STORED,
        event_payload,
    )

    sent_count = 0

    for recipient_device_id in recipient_device_ids:
        sent = await send_realtime_group_event(
            event_type=websocket_payload["type"],
            target_group=make_device_group_name(recipient_device_id),
            payload=websocket_payload,
        )

        if sent:
            sent_count += 1

    return DirectMessageStoredPublishResult(
        message_id=normalized_message_id,
        recipient_user_id=normalized_recipient_user_id,
        recipient_device_ids=recipient_device_ids,
        sent_count=sent_count,
        skipped=False,
    )


def schedule_direct_message_stored_publish(
    *,
    message_id: Any,
    recipient_user_id: Any,
) -> None:
    """
    Schedule direct message realtime publish after database commit.

    If called while inside a transaction, Django runs this after commit.
    If called outside a transaction, Django runs it immediately.

    Realtime publish failures must never break the REST send response.
    """

    normalized_message_id = str(message_id).strip()
    normalized_recipient_user_id = str(recipient_user_id).strip()

    def publish_after_commit():
        try:
            async_to_sync(publish_direct_message_stored)(
                message_id=normalized_message_id,
                recipient_user_id=normalized_recipient_user_id,
            )

        except Exception:
            logger.exception(
                "Failed to publish direct message realtime event.",
                extra={
                    "message_id": normalized_message_id,
                    "recipient_user_id": normalized_recipient_user_id,
                },
            )

    transaction.on_commit(publish_after_commit)

@dataclass(frozen=True, slots=True)
class GroupMessageStoredPublishResult:
    message_id: str
    group_id: str
    recipient_device_ids: tuple[str, ...]
    sent_count: int
    skipped: bool = False


@database_sync_to_async
def get_group_message_stored_event_payload(
    *,
    message_id: Any,
    sender_device_id: Any,
) -> tuple[dict[str, Any], tuple[str, ...]]:
    """
    Build a safe group.message.stored payload.

    This payload intentionally contains only routing metadata.
    The frontend must fetch encrypted group history through REST.

    Never include:
    - encrypted_payload
    - signature
    - sender-chain secrets
    - sender-key plaintext
    - recovery envelopes
    """

    normalized_sender_device_id = str(sender_device_id).strip()

    group_encryption = (
        GroupMessageEncryption.objects
        .select_related(
            "message",
            "group_room",
            "epoch",
            "sender_key",
        )
        .get(message_id=message_id)
    )

    message = group_encryption.message
    group_room = group_encryption.group_room

    active_member_user_ids = list(
        RoomMember.objects
        .filter(
            room=group_room,
            is_active=True,
            room__is_active=True,
        )
        .values_list(
            "user_id",
            flat=True,
        )
    )

    recipient_device_ids = tuple(
        str(device_id)
        for device_id in (
            Device.objects
            .filter(
                user_id__in=active_member_user_ids,
                is_active=True,
            )
            .exclude(
                id=normalized_sender_device_id,
            )
            .order_by("id")
            .values_list(
                "id",
                flat=True,
            )
        )
    )

    payload = {
        "room_id": str(group_room.id),
        "group_id": str(group_room.id),
        "message_id": str(message.id),
        "client_message_id": str(message.client_message_id),
        "sender_user_id": str(message.sender_user_id),
        "sender_device_id": str(message.sender_device_id),
        "message_type": message.message_type,
        "epoch_number": group_encryption.epoch.epoch_number,
        "sender_key_id": str(group_encryption.sender_key.sender_key_id),
        "chain_iteration": group_encryption.chain_iteration,
        "requires_fetch": True,
    }

    return payload, recipient_device_ids


async def publish_group_message_stored(
    *,
    message_id: Any,
    sender_device_id: Any,
) -> GroupMessageStoredPublishResult:
    """
    Publish group.message.stored to active group member device groups.

    The sending device is excluded because it already has the REST response.
    Sender's other active devices are included if they are active group-member
    devices.
    """

    normalized_message_id = str(message_id).strip()
    normalized_sender_device_id = str(sender_device_id).strip()

    if not normalized_message_id or not normalized_sender_device_id:
        return GroupMessageStoredPublishResult(
            message_id=normalized_message_id,
            group_id="",
            recipient_device_ids=tuple(),
            sent_count=0,
            skipped=True,
        )

    channel_layer = get_channel_layer()

    if channel_layer is None:
        return GroupMessageStoredPublishResult(
            message_id=normalized_message_id,
            group_id="",
            recipient_device_ids=tuple(),
            sent_count=0,
            skipped=True,
        )

    event_payload, recipient_device_ids = (
        await get_group_message_stored_event_payload(
            message_id=normalized_message_id,
            sender_device_id=normalized_sender_device_id,
        )
    )

    if not recipient_device_ids:
        return GroupMessageStoredPublishResult(
            message_id=normalized_message_id,
            group_id=str(event_payload.get("group_id", "")),
            recipient_device_ids=tuple(),
            sent_count=0,
            skipped=True,
        )

    websocket_payload = build_event(
        GROUP_MESSAGE_STORED,
        event_payload,
    )

    sent_count = 0

    for recipient_device_id in recipient_device_ids:
        sent = await send_realtime_group_event(
            event_type=websocket_payload["type"],
            target_group=make_device_group_name(recipient_device_id),
            payload=websocket_payload,
        )

        if sent:
            sent_count += 1

    return GroupMessageStoredPublishResult(
        message_id=normalized_message_id,
        group_id=str(event_payload["group_id"]),
        recipient_device_ids=recipient_device_ids,
        sent_count=sent_count,
        skipped=False,
    )


def schedule_group_message_stored_publish(
    *,
    message_id: Any,
    sender_device_id: Any,
) -> None:
    """
    Schedule group message realtime publish after database commit.

    Realtime publish failures must never break the REST group send response.
    """

    normalized_message_id = str(message_id).strip()
    normalized_sender_device_id = str(sender_device_id).strip()

    def publish_after_commit():
        try:
            async_to_sync(publish_group_message_stored)(
                message_id=normalized_message_id,
                sender_device_id=normalized_sender_device_id,
            )

        except Exception:
            logger.exception(
                "Failed to publish group message realtime event.",
                extra={
                    "message_id": normalized_message_id,
                    "sender_device_id": normalized_sender_device_id,
                },
            )

    transaction.on_commit(publish_after_commit)







@dataclass(frozen=True, slots=True)
class MessageDeliveredPublishResult:
    receipt_id: str
    message_id: str
    sender_user_id: str
    recipient_user_id: str
    sender_device_ids: tuple[str, ...]
    sent_count: int
    skipped: bool = False


@database_sync_to_async
def get_message_delivered_event_payload(
    *,
    receipt_id: Any,
) -> tuple[dict[str, Any], tuple[str, ...], bool]:
    """
    Build a safe message.delivered payload.

    This payload intentionally contains only receipt metadata.
    It never contains plaintext, encrypted payloads, keys, or recovery data.
    """

    receipt = (
        MessageReceipt.objects
        .select_related(
            "message",
            "recipient_device",
        )
        .get(id=receipt_id)
    )

    message = receipt.message
    sender_user_id = str(message.sender_user_id)
    recipient_user_id = str(receipt.recipient_user_id)

    if receipt.delivered_at is None:
        return {}, tuple(), True

    allowed = can_publish_receipt_to_sender(
        reader_user_id=recipient_user_id,
        sender_user_id=sender_user_id,
    )

    if not allowed:
        return {}, tuple(), True

    sender_device_ids = tuple(
        str(device_id)
        for device_id in (
            Device.objects
            .filter(
                user_id=sender_user_id,
                is_active=True,
            )
            .order_by("id")
            .values_list(
                "id",
                flat=True,
            )
        )
    )

    if not sender_device_ids:
        return {}, tuple(), True

    payload = {
        "room_id": str(message.room_id),
        "message_id": str(message.id),
        "recipient_user_id": recipient_user_id,
        "recipient_device_id": (
            str(receipt.recipient_device_id)
            if receipt.recipient_device_id
            else ""
        ),
        "delivered_at": receipt.delivered_at.isoformat(),
    }

    return payload, sender_device_ids, False


async def publish_message_delivered(
    *,
    receipt_id: Any,
) -> MessageDeliveredPublishResult:
    """
    Publish message.delivered to the original sender's active devices.

    This is used only after the delivered receipt is actually stored.
    """

    normalized_receipt_id = str(receipt_id).strip()

    if not normalized_receipt_id:
        return MessageDeliveredPublishResult(
            receipt_id="",
            message_id="",
            sender_user_id="",
            recipient_user_id="",
            sender_device_ids=tuple(),
            sent_count=0,
            skipped=True,
        )

    channel_layer = get_channel_layer()

    if channel_layer is None:
        return MessageDeliveredPublishResult(
            receipt_id=normalized_receipt_id,
            message_id="",
            sender_user_id="",
            recipient_user_id="",
            sender_device_ids=tuple(),
            sent_count=0,
            skipped=True,
        )

    event_payload, sender_device_ids, skipped = (
        await get_message_delivered_event_payload(
            receipt_id=normalized_receipt_id,
        )
    )

    if skipped:
        return MessageDeliveredPublishResult(
            receipt_id=normalized_receipt_id,
            message_id=str(event_payload.get("message_id", "")),
            sender_user_id="",
            recipient_user_id=str(event_payload.get("recipient_user_id", "")),
            sender_device_ids=tuple(),
            sent_count=0,
            skipped=True,
        )

    websocket_payload = build_event(
        MESSAGE_DELIVERED,
        event_payload,
    )

    sent_count = 0

    for sender_device_id in sender_device_ids:
        sent = await send_realtime_group_event(
            event_type=websocket_payload["type"],
            target_group=make_device_group_name(sender_device_id),
            payload=websocket_payload,
        )

        if sent:
            sent_count += 1

    return MessageDeliveredPublishResult(
        receipt_id=normalized_receipt_id,
        message_id=str(event_payload["message_id"]),
        sender_user_id="",
        recipient_user_id=str(event_payload["recipient_user_id"]),
        sender_device_ids=sender_device_ids,
        sent_count=sent_count,
        skipped=False,
    )


async def publish_message_delivered_receipts(
    *,
    receipt_ids: list[Any] | tuple[Any, ...],
) -> list[MessageDeliveredPublishResult]:
    results = []

    normalized_receipt_ids = []

    for receipt_id in receipt_ids:
        normalized_receipt_id = str(receipt_id).strip()

        if normalized_receipt_id and normalized_receipt_id not in normalized_receipt_ids:
            normalized_receipt_ids.append(normalized_receipt_id)

    for receipt_id in normalized_receipt_ids:
        result = await publish_message_delivered(
            receipt_id=receipt_id,
        )
        results.append(result)

    return results


def schedule_message_delivered_receipts_publish(
    *,
    receipt_ids: list[Any] | tuple[Any, ...],
) -> None:
    """
    Schedule delivered receipt realtime publish after database commit.

    Realtime publish failures must never break the REST delivered receipt API.
    """

    normalized_receipt_ids = [
        str(receipt_id).strip()
        for receipt_id in receipt_ids
        if str(receipt_id).strip()
    ]

    if not normalized_receipt_ids:
        return

    def publish_after_commit():
        try:
            async_to_sync(publish_message_delivered_receipts)(
                receipt_ids=normalized_receipt_ids,
            )

        except Exception:
            logger.exception(
                "Failed to publish delivered receipt realtime event.",
                extra={
                    "receipt_ids": normalized_receipt_ids,
                },
            )

    transaction.on_commit(publish_after_commit)



@dataclass(frozen=True, slots=True)
class MessageReadPublishResult:
    receipt_id: str
    message_id: str
    sender_user_id: str
    reader_user_id: str
    sender_device_ids: tuple[str, ...]
    sent_count: int
    skipped: bool = False


@database_sync_to_async
def get_message_read_event_payload(
    *,
    receipt_id: Any,
) -> tuple[dict[str, Any], tuple[str, ...], bool]:
    """
    Build a safe message.read payload.

    This payload intentionally contains only receipt metadata.
    It never contains plaintext, encrypted payloads, keys, or recovery data.
    """

    receipt = (
        MessageReceipt.objects
        .select_related(
            "message",
            "recipient_device",
        )
        .get(id=receipt_id)
    )

    message = receipt.message
    sender_user_id = str(message.sender_user_id)
    reader_user_id = str(receipt.recipient_user_id)

    if receipt.read_at is None:
        return {}, tuple(), True

    allowed = can_publish_receipt_to_sender(
        reader_user_id=reader_user_id,
        sender_user_id=sender_user_id,
    )

    if not allowed:
        return {}, tuple(), True

    sender_device_ids = tuple(
        str(device_id)
        for device_id in (
            Device.objects
            .filter(
                user_id=sender_user_id,
                is_active=True,
            )
            .order_by("id")
            .values_list(
                "id",
                flat=True,
            )
        )
    )

    if not sender_device_ids:
        return {}, tuple(), True

    payload = {
        "room_id": str(message.room_id),
        "message_id": str(message.id),
        "read_through_message_id": str(message.id),
        "reader_user_id": reader_user_id,
        "reader_device_id": (
            str(receipt.recipient_device_id)
            if receipt.recipient_device_id
            else ""
        ),
        "read_at": receipt.read_at.isoformat(),
    }

    return payload, sender_device_ids, False


async def publish_message_read(
    *,
    receipt_id: Any,
) -> MessageReadPublishResult:
    """
    Publish message.read to the original sender's active devices.

    This is used only after the read receipt is actually stored.
    """

    normalized_receipt_id = str(receipt_id).strip()

    if not normalized_receipt_id:
        return MessageReadPublishResult(
            receipt_id="",
            message_id="",
            sender_user_id="",
            reader_user_id="",
            sender_device_ids=tuple(),
            sent_count=0,
            skipped=True,
        )

    channel_layer = get_channel_layer()

    if channel_layer is None:
        return MessageReadPublishResult(
            receipt_id=normalized_receipt_id,
            message_id="",
            sender_user_id="",
            reader_user_id="",
            sender_device_ids=tuple(),
            sent_count=0,
            skipped=True,
        )

    event_payload, sender_device_ids, skipped = (
        await get_message_read_event_payload(
            receipt_id=normalized_receipt_id,
        )
    )

    if skipped:
        return MessageReadPublishResult(
            receipt_id=normalized_receipt_id,
            message_id=str(event_payload.get("message_id", "")),
            sender_user_id="",
            reader_user_id=str(event_payload.get("reader_user_id", "")),
            sender_device_ids=tuple(),
            sent_count=0,
            skipped=True,
        )

    websocket_payload = build_event(
        MESSAGE_READ,
        event_payload,
    )

    sent_count = 0

    for sender_device_id in sender_device_ids:
        sent = await send_realtime_group_event(
            event_type=websocket_payload["type"],
            target_group=make_device_group_name(sender_device_id),
            payload=websocket_payload,
        )

        if sent:
            sent_count += 1

    return MessageReadPublishResult(
        receipt_id=normalized_receipt_id,
        message_id=str(event_payload["message_id"]),
        sender_user_id="",
        reader_user_id=str(event_payload["reader_user_id"]),
        sender_device_ids=sender_device_ids,
        sent_count=sent_count,
        skipped=False,
    )


async def publish_message_read_receipts(
    *,
    receipt_ids: list[Any] | tuple[Any, ...],
) -> list[MessageReadPublishResult]:
    results = []
    normalized_receipt_ids = []

    for receipt_id in receipt_ids:
        normalized_receipt_id = str(receipt_id).strip()

        if normalized_receipt_id and normalized_receipt_id not in normalized_receipt_ids:
            normalized_receipt_ids.append(normalized_receipt_id)

    for receipt_id in normalized_receipt_ids:
        result = await publish_message_read(
            receipt_id=receipt_id,
        )
        results.append(result)

    return results


def schedule_message_read_receipts_publish(
    *,
    receipt_ids: list[Any] | tuple[Any, ...],
) -> None:
    """
    Schedule read receipt realtime publish after database commit.

    Realtime publish failures must never break the REST read receipt API.
    """

    normalized_receipt_ids = [
        str(receipt_id).strip()
        for receipt_id in receipt_ids
        if str(receipt_id).strip()
    ]

    if not normalized_receipt_ids:
        return

    def publish_after_commit():
        try:
            async_to_sync(publish_message_read_receipts)(
                receipt_ids=normalized_receipt_ids,
            )

        except Exception:
            logger.exception(
                "Failed to publish read receipt realtime event.",
                extra={
                    "receipt_ids": normalized_receipt_ids,
                },
            )

    transaction.on_commit(publish_after_commit)

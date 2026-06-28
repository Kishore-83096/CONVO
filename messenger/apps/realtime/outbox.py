from __future__ import annotations

import logging
from typing import Any

from asgiref.sync import async_to_sync
from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from django.utils import timezone

from .models import RealtimeOutboxEvent


logger = logging.getLogger(__name__)


MAX_OUTBOX_ATTEMPTS = 10


def calculate_next_attempt_at(
    *,
    attempts: int,
):
    delay_seconds = min(
        300,
        2 ** min(
            attempts,
            8,
        ),
    )

    return timezone.now() + timezone.timedelta(
        seconds=delay_seconds,
    )


@database_sync_to_async
def enqueue_realtime_outbox_event(
    *,
    event_type: str,
    target_group: str,
    payload: dict[str, Any],
    last_error: str = "",
) -> RealtimeOutboxEvent:
    return RealtimeOutboxEvent.objects.create(
        event_type=str(event_type).strip(),
        target_group=str(target_group).strip(),
        payload=payload,
        status=RealtimeOutboxEvent.Status.PENDING,
        attempts=0,
        next_attempt_at=timezone.now(),
        last_error=str(last_error or "")[:5000],
    )


async def send_realtime_group_event(
    *,
    event_type: str,
    target_group: str,
    payload: dict[str, Any],
) -> bool:
    """
    Send a realtime event to a channel-layer group.

    If Redis/channel layer is unavailable, store the event in the outbox
    and return False.

    This function must never raise to REST send/receipt flows.
    """

    normalized_event_type = str(event_type).strip()
    normalized_target_group = str(target_group).strip()

    if not normalized_event_type or not normalized_target_group:
        return False

    channel_layer = get_channel_layer()

    try:
        if channel_layer is None:
            raise RuntimeError("Channel layer is not configured.")

        await channel_layer.group_send(
            normalized_target_group,
            {
                "type": "realtime.event",
                "payload": payload,
            },
        )

        return True

    except Exception as exc:
        await enqueue_realtime_outbox_event(
            event_type=normalized_event_type,
            target_group=normalized_target_group,
            payload=payload,
            last_error=str(exc),
        )

        logger.exception(
            "Realtime publish failed and was queued in outbox.",
            extra={
                "event_type": normalized_event_type,
                "target_group": normalized_target_group,
            },
        )

        return False


def retry_single_realtime_outbox_event(
    *,
    event: RealtimeOutboxEvent,
) -> bool:
    """
    Try to publish one pending outbox event.

    Returns True when delivered.
    Returns False when it remains pending/failed/dead.
    """

    now = timezone.now()

    event.last_attempt_at = now
    event.attempts += 1

    try:
        channel_layer = get_channel_layer()

        if channel_layer is None:
            raise RuntimeError("Channel layer is not configured.")

        async_to_sync(channel_layer.group_send)(
            event.target_group,
            {
                "type": "realtime.event",
                "payload": event.payload,
            },
        )

        event.status = RealtimeOutboxEvent.Status.DELIVERED
        event.delivered_at = timezone.now()
        event.last_error = ""
        event.save(
            update_fields=[
                "status",
                "attempts",
                "last_attempt_at",
                "delivered_at",
                "last_error",
                "updated_at",
            ]
        )

        return True

    except Exception as exc:
        event.last_error = str(exc)[:5000]

        if event.attempts >= MAX_OUTBOX_ATTEMPTS:
            event.status = RealtimeOutboxEvent.Status.DEAD
        else:
            event.status = RealtimeOutboxEvent.Status.FAILED
            event.next_attempt_at = calculate_next_attempt_at(
                attempts=event.attempts,
            )

        event.save(
            update_fields=[
                "status",
                "attempts",
                "last_attempt_at",
                "next_attempt_at",
                "last_error",
                "updated_at",
            ]
        )

        logger.exception(
            "Realtime outbox retry failed.",
            extra={
                "outbox_event_id": str(event.id),
                "event_type": event.event_type,
                "target_group": event.target_group,
                "attempts": event.attempts,
            },
        )

        return False


def retry_pending_realtime_outbox_events(
    *,
    limit: int = 100,
) -> dict[str, int]:
    """
    Retry pending/failed realtime events that are due.

    This is called by the management command.
    """

    now = timezone.now()
    safe_limit = max(
        1,
        min(
            int(limit),
            500,
        ),
    )

    event_ids = list(
        RealtimeOutboxEvent.objects
        .filter(
            status__in=[
                RealtimeOutboxEvent.Status.PENDING,
                RealtimeOutboxEvent.Status.FAILED,
            ],
            next_attempt_at__lte=now,
        )
        .order_by(
            "created_at",
        )
        .values_list(
            "id",
            flat=True,
        )[:safe_limit]
    )

    result = {
        "attempted": 0,
        "delivered": 0,
        "failed": 0,
    }

    for event_id in event_ids:
        event = RealtimeOutboxEvent.objects.get(
            id=event_id,
        )

        result["attempted"] += 1

        delivered = retry_single_realtime_outbox_event(
            event=event,
        )

        if delivered:
            result["delivered"] += 1
        else:
            result["failed"] += 1

    return result
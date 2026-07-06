from __future__ import annotations

import hashlib
import json
import logging
import os
import socket
import uuid
from dataclasses import dataclass
from typing import Any, Iterable

from asgiref.sync import async_to_sync
from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from django.db import connection, transaction
from django.db.models import Q
from django.utils import timezone

from .models import RealtimeOutboxEvent


logger = logging.getLogger(__name__)


DEFAULT_OUTBOX_BATCH_SIZE = 100
DEFAULT_OUTBOX_MAX_ATTEMPTS = 10
DEFAULT_OUTBOX_STALE_CLAIM_SECONDS = 300


@dataclass(frozen=True, slots=True)
class RealtimeOutboxCreateSpec:
    event_type: str
    target_group: str
    payload: dict[str, Any]
    event_key: str | None = None
    last_error: str = ""


def get_default_worker_id() -> str:
    return (
        f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:12]}"
    )


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


def _canonical_json(value: dict[str, Any]) -> str:
    return json.dumps(
        value,
        default=str,
        separators=(",", ":"),
        sort_keys=True,
    )


def build_realtime_outbox_event_key(
    *,
    event_type: str,
    target_group: str,
    payload: dict[str, Any],
    event_key: str | None = None,
) -> str:
    explicit = str(event_key or "").strip()
    if explicit:
        return explicit[:128]

    digest = hashlib.sha256(
        (
            f"{str(event_type).strip()}\0"
            f"{str(target_group).strip()}\0"
            f"{_canonical_json(payload)}"
        ).encode("utf-8")
    ).hexdigest()

    return f"rt:{digest}"


def build_direct_message_stored_event_key(
    *,
    message_id: Any,
    target_group: str,
) -> str:
    digest = hashlib.sha256(
        (
            f"direct-message-stored\0"
            f"{str(message_id).strip()}\0"
            f"{str(target_group).strip()}"
        ).encode("utf-8")
    ).hexdigest()

    return f"dm:{digest}"


def enqueue_realtime_outbox_event_sync(
    *,
    event_type: str,
    target_group: str,
    payload: dict[str, Any],
    event_key: str | None = None,
    last_error: str = "",
) -> RealtimeOutboxEvent:
    event, _created = enqueue_realtime_outbox_event_with_created_sync(
        event_type=event_type,
        target_group=target_group,
        payload=payload,
        event_key=event_key,
        last_error=last_error,
    )

    return event


def enqueue_realtime_outbox_event_with_created_sync(
    *,
    event_type: str,
    target_group: str,
    payload: dict[str, Any],
    event_key: str | None = None,
    last_error: str = "",
) -> tuple[RealtimeOutboxEvent, bool]:
    normalized_event_type = str(event_type).strip()
    normalized_target_group = str(target_group).strip()

    if not normalized_event_type or not normalized_target_group:
        raise ValueError("event_type and target_group are required.")

    normalized_event_key = build_realtime_outbox_event_key(
        event_type=normalized_event_type,
        target_group=normalized_target_group,
        payload=payload,
        event_key=event_key,
    )

    event, created = RealtimeOutboxEvent.objects.get_or_create(
        event_key=normalized_event_key,
        defaults={
            "event_type": normalized_event_type,
            "target_group": normalized_target_group,
            "payload": payload,
            "status": RealtimeOutboxEvent.Status.PENDING,
            "attempts": 0,
            "next_attempt_at": timezone.now(),
            "last_error": str(last_error or "")[:5000],
        },
    )

    return event, created


def enqueue_realtime_outbox_events_sync(
    events: Iterable[RealtimeOutboxCreateSpec],
) -> int:
    created_count = 0

    for spec in events:
        _event, created = enqueue_realtime_outbox_event_with_created_sync(
            event_type=spec.event_type,
            target_group=spec.target_group,
            payload=spec.payload,
            event_key=spec.event_key,
            last_error=spec.last_error,
        )

        if created:
            created_count += 1

    return created_count




def enqueue_new_realtime_outbox_events_sync(
    events: Iterable[RealtimeOutboxCreateSpec],
) -> int:
    """
    Bulk-persist outbox rows for a newly created parent object.

    This fast path is intentionally for call sites that already proved the
    parent object was newly inserted in the same outer transaction. Duplicate
    event keys inside the input batch are collapsed in Python; database-level
    event_key uniqueness remains the final invariant guard.
    """
    outbox_models: list[RealtimeOutboxEvent] = []
    seen_event_keys: set[str] = set()
    next_attempt_at = timezone.now()

    for spec in events:
        normalized_event_type = str(
            spec.event_type
        ).strip()

        normalized_target_group = str(
            spec.target_group
        ).strip()

        if (
            not normalized_event_type
            or not normalized_target_group
        ):
            raise ValueError(
                "event_type and target_group are required."
            )

        normalized_event_key = (
            build_realtime_outbox_event_key(
                event_type=normalized_event_type,
                target_group=normalized_target_group,
                payload=spec.payload,
                event_key=spec.event_key,
            )
        )

        if normalized_event_key in seen_event_keys:
            continue

        seen_event_keys.add(
            normalized_event_key
        )

        outbox_models.append(
            RealtimeOutboxEvent(
                event_type=normalized_event_type,
                target_group=normalized_target_group,
                event_key=normalized_event_key,
                payload=spec.payload,
                status=(
                    RealtimeOutboxEvent.Status.PENDING
                ),
                attempts=0,
                next_attempt_at=next_attempt_at,
                last_error=str(
                    spec.last_error or ""
                )[:5000],
            )
        )

    if not outbox_models:
        return 0

    RealtimeOutboxEvent.objects.bulk_create(
        outbox_models
    )

    return len(outbox_models)


    

@database_sync_to_async
def enqueue_realtime_outbox_event(
    *,
    event_type: str,
    target_group: str,
    payload: dict[str, Any],
    event_key: str | None = None,
    last_error: str = "",
) -> RealtimeOutboxEvent:
    return enqueue_realtime_outbox_event_sync(
        event_type=str(event_type).strip(),
        target_group=str(target_group).strip(),
        payload=payload,
        event_key=event_key,
        last_error=str(last_error or "")[:5000],
    )


async def send_realtime_group_event(
    *,
    event_type: str,
    target_group: str,
    payload: dict[str, Any],
    event_key: str | None = None,
) -> bool:
    """
    Best-effort immediate realtime send.

    This remains useful for non-REST flows. Direct-message REST sends should
    create durable outbox rows inside their DB transaction and let the worker
    publish them later.
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
            event_key=event_key,
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


def _safe_limit(limit: int) -> int:
    return max(
        1,
        min(
            int(limit),
            500,
        ),
    )


def claim_due_realtime_outbox_events(
    *,
    limit: int = DEFAULT_OUTBOX_BATCH_SIZE,
    worker_id: str | None = None,
    stale_claim_seconds: int = DEFAULT_OUTBOX_STALE_CLAIM_SECONDS,
) -> list[RealtimeOutboxEvent]:
    """
    Claim due outbox rows for one worker.

    On PostgreSQL/MySQL versions that support SKIP LOCKED, concurrent workers
    avoid waiting on each other's locked rows. Other supported databases still
    use the same status transition as the durable claim boundary.
    """

    now = timezone.now()
    stale_before = now - timezone.timedelta(
        seconds=max(1, int(stale_claim_seconds)),
    )
    normalized_worker_id = str(worker_id or get_default_worker_id()).strip()
    safe_limit = _safe_limit(limit)

    due_filter = (
        Q(
            status__in=[
                RealtimeOutboxEvent.Status.PENDING,
                RealtimeOutboxEvent.Status.FAILED,
            ],
            next_attempt_at__lte=now,
        )
        | Q(
            status=RealtimeOutboxEvent.Status.PROCESSING,
            claimed_at__lte=stale_before,
        )
    )

    with transaction.atomic():
        queryset = (
            RealtimeOutboxEvent.objects
            .filter(due_filter)
            .order_by(
                "created_at",
                "id",
            )
        )

        if connection.features.has_select_for_update:
            queryset = queryset.select_for_update(
                skip_locked=(
                    connection.features.has_select_for_update_skip_locked
                )
            )

        events = list(queryset[:safe_limit])
        event_ids = [event.id for event in events]

        if event_ids:
            RealtimeOutboxEvent.objects.filter(
                id__in=event_ids,
            ).update(
                status=RealtimeOutboxEvent.Status.PROCESSING,
                claimed_by=normalized_worker_id[:128],
                claimed_at=now,
                last_attempt_at=now,
            )

        for event in events:
            event.status = RealtimeOutboxEvent.Status.PROCESSING
            event.claimed_by = normalized_worker_id[:128]
            event.claimed_at = now
            event.last_attempt_at = now

    return events


def publish_claimed_realtime_outbox_event(
    *,
    event: RealtimeOutboxEvent,
    max_attempts: int = DEFAULT_OUTBOX_MAX_ATTEMPTS,
) -> bool:
    """
    Publish one claimed event.

    Returns True when delivered. Returns False when the event remains retryable
    or is moved to dead-letter state.
    """

    attempts = int(event.attempts) + 1

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
        event.attempts = attempts
        event.delivered_at = timezone.now()
        event.last_error = ""
        event.claimed_by = ""
        event.claimed_at = None
        event.save(
            update_fields=[
                "status",
                "attempts",
                "delivered_at",
                "last_error",
                "claimed_by",
                "claimed_at",
                "updated_at",
            ]
        )

        return True

    except Exception as exc:
        event.attempts = attempts
        event.last_error = str(exc)[:5000]
        event.claimed_by = ""
        event.claimed_at = None

        if attempts >= max(1, int(max_attempts)):
            event.status = RealtimeOutboxEvent.Status.DEAD
        else:
            event.status = RealtimeOutboxEvent.Status.FAILED
            event.next_attempt_at = calculate_next_attempt_at(
                attempts=attempts,
            )

        event.save(
            update_fields=[
                "status",
                "attempts",
                "next_attempt_at",
                "last_error",
                "claimed_by",
                "claimed_at",
                "updated_at",
            ]
        )

        logger.exception(
            "Realtime outbox publish failed.",
            extra={
                "outbox_event_id": str(event.id),
                "event_type": event.event_type,
                "target_group": event.target_group,
                "attempts": event.attempts,
                "status": event.status,
            },
        )

        return False


def retry_single_realtime_outbox_event(
    *,
    event: RealtimeOutboxEvent,
    max_attempts: int = DEFAULT_OUTBOX_MAX_ATTEMPTS,
) -> bool:
    if event.status != RealtimeOutboxEvent.Status.PROCESSING:
        now = timezone.now()
        event.status = RealtimeOutboxEvent.Status.PROCESSING
        event.claimed_by = get_default_worker_id()[:128]
        event.claimed_at = now
        event.last_attempt_at = now
        event.save(
            update_fields=[
                "status",
                "claimed_by",
                "claimed_at",
                "last_attempt_at",
                "updated_at",
            ]
        )

    return publish_claimed_realtime_outbox_event(
        event=event,
        max_attempts=max_attempts,
    )


def retry_pending_realtime_outbox_events(
    *,
    limit: int = DEFAULT_OUTBOX_BATCH_SIZE,
    worker_id: str | None = None,
    max_attempts: int = DEFAULT_OUTBOX_MAX_ATTEMPTS,
    stale_claim_seconds: int = DEFAULT_OUTBOX_STALE_CLAIM_SECONDS,
) -> dict[str, int]:
    """
    Claim and publish pending/failed realtime events that are due.
    """

    events = claim_due_realtime_outbox_events(
        limit=limit,
        worker_id=worker_id,
        stale_claim_seconds=stale_claim_seconds,
    )

    result = {
        "attempted": 0,
        "delivered": 0,
        "failed": 0,
        "dead": 0,
    }

    for event in events:
        result["attempted"] += 1

        delivered = publish_claimed_realtime_outbox_event(
            event=event,
            max_attempts=max_attempts,
        )

        if delivered:
            result["delivered"] += 1
        elif event.status == RealtimeOutboxEvent.Status.DEAD:
            result["dead"] += 1
        else:
            result["failed"] += 1

    return result

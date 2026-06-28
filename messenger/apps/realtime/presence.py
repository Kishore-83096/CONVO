from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import redis.asyncio as redis
from channels.db import database_sync_to_async
from django.conf import settings
from django.utils import timezone

from apps.e2ee_devices.models import Device


LAST_SEEN_DB_WRITE_THROTTLE_SECONDS = 60


@dataclass(frozen=True, slots=True)
class PresenceState:
    user_id: str
    device_id: str
    device_online: bool
    user_online: bool
    online_device_ids: tuple[str, ...]
    connection_count: int


def normalize_presence_id(value: Any) -> str:
    return str(value).strip()


def presence_device_connections_key(device_id: Any) -> str:
    return f"presence:device:{normalize_presence_id(device_id)}:connections"


def presence_device_last_heartbeat_key(device_id: Any) -> str:
    return f"presence:device:{normalize_presence_id(device_id)}:last_heartbeat"


def presence_device_user_key(device_id: Any) -> str:
    return f"presence:device:{normalize_presence_id(device_id)}:user_id"


def presence_user_online_devices_key(user_id: Any) -> str:
    return f"presence:user:{normalize_presence_id(user_id)}:online_devices"


def presence_device_last_seen_write_key(device_id: Any) -> str:
    return f"presence:device:{normalize_presence_id(device_id)}:last_seen_db_write"


def get_presence_ttl_seconds() -> int:
    return int(settings.REALTIME_PRESENCE_TTL_SECONDS)


def get_redis_client():
    return redis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
    )


async def close_redis_client(redis_client) -> None:
    close = getattr(redis_client, "aclose", None)

    if close is not None:
        await close()


@database_sync_to_async
def update_device_last_seen_at(
    *,
    device_id: str,
    seen_at,
) -> int:
    return (
        Device.objects
        .filter(id=device_id)
        .update(last_seen_at=seen_at)
    )


@database_sync_to_async
def get_latest_device_last_seen_for_user(
    *,
    user_id: str,
):
    return (
        Device.objects
        .filter(
            user_id=user_id,
            last_seen_at__isnull=False,
        )
        .order_by("-last_seen_at")
        .values_list("last_seen_at", flat=True)
        .first()
    )


async def maybe_update_device_last_seen_at(
    *,
    redis_client,
    device_id: str,
    seen_at,
) -> bool:
    """
    Update Device.last_seen_at, but throttle database writes.

    Redis key uses NX so only the first call inside the throttle window
    writes to the database.
    """

    throttle_key = presence_device_last_seen_write_key(device_id)

    should_write = await redis_client.set(
        throttle_key,
        seen_at.isoformat(),
        ex=LAST_SEEN_DB_WRITE_THROTTLE_SECONDS,
        nx=True,
    )

    if not should_write:
        return False

    await update_device_last_seen_at(
        device_id=device_id,
        seen_at=seen_at,
    )

    return True


async def get_user_online_device_ids(
    *,
    user_id: Any,
) -> tuple[str, ...]:
    normalized_user_id = normalize_presence_id(user_id)

    if not normalized_user_id:
        return tuple()

    redis_client = get_redis_client()

    try:
        device_ids = await redis_client.smembers(
            presence_user_online_devices_key(normalized_user_id),
        )

        return tuple(
            sorted(str(device_id) for device_id in device_ids)
        )

    finally:
        await close_redis_client(redis_client)


async def is_user_online(
    *,
    user_id: Any,
) -> bool:
    return bool(
        await get_user_online_device_ids(
            user_id=user_id,
        )
    )


async def is_device_online(
    *,
    device_id: Any,
) -> bool:
    normalized_device_id = normalize_presence_id(device_id)

    if not normalized_device_id:
        return False

    redis_client = get_redis_client()

    try:
        connection_count = await redis_client.scard(
            presence_device_connections_key(normalized_device_id),
        )

        return int(connection_count or 0) > 0

    finally:
        await close_redis_client(redis_client)


async def build_presence_state(
    *,
    redis_client,
    user_id: str,
    device_id: str,
) -> PresenceState:
    connection_count = int(
        await redis_client.scard(
            presence_device_connections_key(device_id),
        )
        or 0
    )

    online_device_ids = await redis_client.smembers(
        presence_user_online_devices_key(user_id),
    )

    normalized_online_device_ids = tuple(
        sorted(str(item) for item in online_device_ids)
    )

    return PresenceState(
        user_id=user_id,
        device_id=device_id,
        device_online=connection_count > 0,
        user_online=bool(normalized_online_device_ids),
        online_device_ids=normalized_online_device_ids,
        connection_count=connection_count,
    )


async def mark_device_online(
    *,
    user_id: Any,
    device_id: Any,
    channel_name: str,
) -> PresenceState:
    normalized_user_id = normalize_presence_id(user_id)
    normalized_device_id = normalize_presence_id(device_id)
    normalized_channel_name = normalize_presence_id(channel_name)

    if not normalized_user_id:
        raise ValueError("user_id is required.")

    if not normalized_device_id:
        raise ValueError("device_id is required.")

    if not normalized_channel_name:
        raise ValueError("channel_name is required.")

    redis_client = get_redis_client()
    ttl_seconds = get_presence_ttl_seconds()
    now = timezone.now()

    try:
        device_connections_key = presence_device_connections_key(
            normalized_device_id,
        )
        device_heartbeat_key = presence_device_last_heartbeat_key(
            normalized_device_id,
        )
        device_user_key = presence_device_user_key(
            normalized_device_id,
        )
        user_devices_key = presence_user_online_devices_key(
            normalized_user_id,
        )

        await redis_client.sadd(
            device_connections_key,
            normalized_channel_name,
        )
        await redis_client.expire(
            device_connections_key,
            ttl_seconds,
        )

        await redis_client.set(
            device_heartbeat_key,
            now.isoformat(),
            ex=ttl_seconds,
        )

        await redis_client.set(
            device_user_key,
            normalized_user_id,
            ex=ttl_seconds,
        )

        await redis_client.sadd(
            user_devices_key,
            normalized_device_id,
        )
        await redis_client.expire(
            user_devices_key,
            ttl_seconds,
        )

        await maybe_update_device_last_seen_at(
            redis_client=redis_client,
            device_id=normalized_device_id,
            seen_at=now,
        )

        return await build_presence_state(
            redis_client=redis_client,
            user_id=normalized_user_id,
            device_id=normalized_device_id,
        )

    finally:
        await close_redis_client(redis_client)


async def refresh_device_heartbeat(
    *,
    user_id: Any,
    device_id: Any,
    channel_name: str,
) -> PresenceState:
    """
    Refresh active presence TTL for a connected device.

    Called when the client sends:
        {"type": "heartbeat"}
    """

    normalized_user_id = normalize_presence_id(user_id)
    normalized_device_id = normalize_presence_id(device_id)
    normalized_channel_name = normalize_presence_id(channel_name)

    if not normalized_user_id:
        raise ValueError("user_id is required.")

    if not normalized_device_id:
        raise ValueError("device_id is required.")

    if not normalized_channel_name:
        raise ValueError("channel_name is required.")

    redis_client = get_redis_client()
    ttl_seconds = get_presence_ttl_seconds()
    now = timezone.now()

    try:
        device_connections_key = presence_device_connections_key(
            normalized_device_id,
        )
        device_heartbeat_key = presence_device_last_heartbeat_key(
            normalized_device_id,
        )
        device_user_key = presence_device_user_key(
            normalized_device_id,
        )
        user_devices_key = presence_user_online_devices_key(
            normalized_user_id,
        )

        await redis_client.sadd(
            device_connections_key,
            normalized_channel_name,
        )
        await redis_client.expire(
            device_connections_key,
            ttl_seconds,
        )

        await redis_client.set(
            device_heartbeat_key,
            now.isoformat(),
            ex=ttl_seconds,
        )

        await redis_client.set(
            device_user_key,
            normalized_user_id,
            ex=ttl_seconds,
        )

        await redis_client.sadd(
            user_devices_key,
            normalized_device_id,
        )
        await redis_client.expire(
            user_devices_key,
            ttl_seconds,
        )

        await maybe_update_device_last_seen_at(
            redis_client=redis_client,
            device_id=normalized_device_id,
            seen_at=now,
        )

        return await build_presence_state(
            redis_client=redis_client,
            user_id=normalized_user_id,
            device_id=normalized_device_id,
        )

    finally:
        await close_redis_client(redis_client)


async def mark_device_disconnected(
    *,
    user_id: Any,
    device_id: Any,
    channel_name: str,
) -> PresenceState:
    """
    Remove one socket connection from the device connection set.

    If this was the last active connection for the device, the device is
    removed from the user's online device set.

    Phase 14 will decide when/how to publish offline events.
    """

    normalized_user_id = normalize_presence_id(user_id)
    normalized_device_id = normalize_presence_id(device_id)
    normalized_channel_name = normalize_presence_id(channel_name)

    if not normalized_user_id:
        raise ValueError("user_id is required.")

    if not normalized_device_id:
        raise ValueError("device_id is required.")

    if not normalized_channel_name:
        raise ValueError("channel_name is required.")

    redis_client = get_redis_client()
    ttl_seconds = get_presence_ttl_seconds()
    now = timezone.now()

    try:
        device_connections_key = presence_device_connections_key(
            normalized_device_id,
        )
        device_heartbeat_key = presence_device_last_heartbeat_key(
            normalized_device_id,
        )
        device_user_key = presence_device_user_key(
            normalized_device_id,
        )
        user_devices_key = presence_user_online_devices_key(
            normalized_user_id,
        )

        await redis_client.srem(
            device_connections_key,
            normalized_channel_name,
        )

        connection_count = int(
            await redis_client.scard(device_connections_key)
            or 0
        )

        if connection_count > 0:
            await redis_client.expire(
                device_connections_key,
                ttl_seconds,
            )
            await redis_client.expire(
                device_heartbeat_key,
                ttl_seconds,
            )
            await redis_client.expire(
                device_user_key,
                ttl_seconds,
            )
            await redis_client.expire(
                user_devices_key,
                ttl_seconds,
            )

        else:
            await redis_client.delete(
                device_connections_key,
                device_heartbeat_key,
                device_user_key,
            )
            await redis_client.srem(
                user_devices_key,
                normalized_device_id,
            )

            user_device_count = int(
                await redis_client.scard(user_devices_key)
                or 0
            )

            if user_device_count > 0:
                await redis_client.expire(
                    user_devices_key,
                    ttl_seconds,
                )
            else:
                await redis_client.delete(
                    user_devices_key,
                )

        await maybe_update_device_last_seen_at(
            redis_client=redis_client,
            device_id=normalized_device_id,
            seen_at=now,
        )

        return await build_presence_state(
            redis_client=redis_client,
            user_id=normalized_user_id,
            device_id=normalized_device_id,
        )

    finally:
        await close_redis_client(redis_client)


async def get_user_presence_snapshot(
    *,
    user_id: Any,
) -> dict[str, Any]:
    """
    Return raw presence snapshot for a user.

    Phase 13 presence batch API will wrap this with can_view_presence()
    before returning data to another user.
    """

    normalized_user_id = normalize_presence_id(user_id)

    if not normalized_user_id:
        return {
            "user_id": "",
            "status": "offline",
            "online_device_ids": [],
            "last_seen_at": None,
        }

    online_device_ids = await get_user_online_device_ids(
        user_id=normalized_user_id,
    )

    latest_seen = await get_latest_device_last_seen_for_user(
        user_id=normalized_user_id,
    )

    return {
        "user_id": normalized_user_id,
        "status": "online" if online_device_ids else "offline",
        "online_device_ids": list(online_device_ids),
        "last_seen_at": latest_seen.isoformat() if latest_seen else None,
    }
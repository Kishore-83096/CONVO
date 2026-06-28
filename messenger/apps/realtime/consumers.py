from __future__ import annotations

import hashlib
import logging
import re
from typing import Any

from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.conf import settings

from .events import (
    CONNECTION_ACCEPTED,
    HEARTBEAT_ACK,
    build_client_error_event,
    build_event,
)
from .presence import (
    mark_device_disconnected,
    mark_device_online,
    refresh_device_heartbeat,
)
from .publishers import publish_presence_to_related_viewers

logger = logging.getLogger(__name__)
_GROUP_SAFE_PATTERN = re.compile(r"^[a-zA-Z0-9_.-]+$")


def make_safe_group_suffix(value: Any) -> str:
    """
    Channels group names may contain only ASCII letters, numbers,
    hyphens, underscores, and periods.

    Most Myna user IDs and UUID device IDs are already safe. If a future
    external user ID contains unsafe characters, hash it instead of
    leaking/using invalid characters in the Channels group name.
    """

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


class MessengerConsumer(AsyncJsonWebsocketConsumer):
    """
    Main authenticated Messenger WebSocket consumer.

    Phase 10 responsibilities:
        - Accept already-authenticated sockets.
        - Join device and user channel groups.
        - Send connection.accepted.
        - Handle heartbeat.
        - Forward server-published realtime events to this socket.

    Authentication is handled before this consumer by
    RealtimeTicketAuthMiddleware.
    """

    async def connect(self):
        self.user_id = self.scope.get("myna_user_id")
        self.device_id = self.scope.get("myna_device_id")

        if not self.user_id or not self.device_id:
            await self.close(
                code=4401,
            )
            return

        self.user_group_name = make_user_group_name(
            self.user_id,
        )
        self.device_group_name = make_device_group_name(
            self.device_id,
        )

        await self.channel_layer.group_add(
            self.user_group_name,
            self.channel_name,
        )
        await self.channel_layer.group_add(
            self.device_group_name,
            self.channel_name,
        )

        presence_state = await mark_device_online(
            user_id=self.user_id,
            device_id=self.device_id,
            channel_name=self.channel_name,
        )

        await self.accept()

        await self.send_json(
            build_event(
                CONNECTION_ACCEPTED,
                {
                    "user_id": str(self.user_id),
                    "device_id": str(self.device_id),
                    "heartbeat_seconds": (
                        settings.REALTIME_HEARTBEAT_SECONDS
                    ),
                },
            )
        )

        if presence_state.connection_count == 1:
            await self.publish_presence_update_safely()

    async def disconnect(self, close_code):
        user_group_name = getattr(
            self,
            "user_group_name",
            None,
        )
        device_group_name = getattr(
            self,
            "device_group_name",
            None,
        )

        if getattr(self, "user_id", None) and getattr(self, "device_id", None):
            presence_state = await mark_device_disconnected(
                user_id=self.user_id,
                device_id=self.device_id,
                channel_name=self.channel_name,
            )

            if not presence_state.device_online:
                await self.publish_presence_update_safely()

        if user_group_name:
            await self.channel_layer.group_discard(
                user_group_name,
                self.channel_name,
            )

        if device_group_name:
            await self.channel_layer.group_discard(
                device_group_name,
                self.channel_name,
            )

    async def receive_json(self, content, **kwargs):
        if not isinstance(content, dict):
            await self.send_json(
                build_client_error_event(
                    code="invalid_payload",
                    message="WebSocket payload must be a JSON object.",
                )
            )
            return

        event_type = str(
            content.get("type", ""),
        ).strip()

        if event_type == "heartbeat":
            await self.handle_heartbeat()
            return

        await self.send_json(
            build_client_error_event(
                code="unsupported_event_type",
                message="Unsupported WebSocket event type.",
            )
        )

    async def handle_heartbeat(self):
        """
        Refresh Redis presence TTL and acknowledge the socket is alive.
        """

        await refresh_device_heartbeat(
            user_id=self.user_id,
            device_id=self.device_id,
            channel_name=self.channel_name,
        )

        await self.send_json(
            build_event(
                HEARTBEAT_ACK,
                {
                    "user_id": str(self.user_id),
                    "device_id": str(self.device_id),
                    "heartbeat_seconds": (
                        settings.REALTIME_HEARTBEAT_SECONDS
                    ),
                },
            )
        )

    async def publish_presence_update_safely(self):
        """
        Publish this user's presence to related viewers.

        Presence publishing must never break the WebSocket connection.
        If publishing fails, the socket should still stay connected and
        the client can recover through the presence batch API.
        """

        try:
            await publish_presence_to_related_viewers(
                subject_user_id=self.user_id,
            )

        except Exception:
            logger.exception(
                "Failed to publish realtime presence update.",
                extra={
                    "user_id": str(self.user_id),
                    "device_id": str(self.device_id),
                },
            )
    async def realtime_event(self, event):
        """
        Receive a server-side Channels group event and forward its payload
        to this WebSocket.

        Publishers should call:

            channel_layer.group_send(
                "user.<id>" or "device.<id>",
                {
                    "type": "realtime.event",
                    "payload": build_event(...),
                },
            )
        """

        payload = event.get("payload")

        if isinstance(payload, dict):
            await self.send_json(payload)
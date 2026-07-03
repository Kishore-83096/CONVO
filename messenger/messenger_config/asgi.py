"""
ASGI config for the Myna Messenger service.

Important import order:

Django apps must be loaded before importing modules that import models.
So get_asgi_application() must run before importing realtime middleware
that touches RealtimeTicket / Device / other Django models.
"""

import os
import asyncio
from concurrent.futures import ThreadPoolExecutor

from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "messenger_config.settings",
)

django_asgi_app = get_asgi_application()

from apps.realtime.authentication import RealtimeTicketAuthMiddleware  # noqa: E402
from messenger_config.routing import websocket_urlpatterns  # noqa: E402


def _configured_asgi_threads() -> int | None:
    value = os.getenv("ASGI_THREADS", "").strip()
    if not value:
        return None
    try:
        thread_count = int(value)
    except ValueError:
        return None
    if thread_count < 1:
        return None
    return thread_count


class DefaultExecutorCap:
    """
    Cap the event loop default executor for ASGI work that uses
    loop.run_in_executor(None, ...). This is a real cap for default-executor
    pressure; thread-sensitive sync_to_async sections may still use their own
    dedicated executors.
    """

    def __init__(self, app, max_workers: int | None) -> None:
        self.app = app
        self.max_workers = max_workers
        self._configured_loop_ids: set[int] = set()

    async def __call__(self, scope, receive, send) -> None:
        if self.max_workers:
            loop = asyncio.get_running_loop()
            loop_id = id(loop)
            if loop_id not in self._configured_loop_ids:
                loop.set_default_executor(
                    ThreadPoolExecutor(
                        max_workers=self.max_workers,
                        thread_name_prefix="myna-asgi",
                    )
                )
                self._configured_loop_ids.add(loop_id)
        await self.app(scope, receive, send)


router = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": RealtimeTicketAuthMiddleware(
            URLRouter(websocket_urlpatterns),
        ),
    }
)

application = DefaultExecutorCap(
    router,
    _configured_asgi_threads(),
)

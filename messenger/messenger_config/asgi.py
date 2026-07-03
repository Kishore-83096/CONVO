"""
ASGI config for the Myna Messenger service.

Important import order:

Django apps must be loaded before importing modules that import models.
So get_asgi_application() must run before importing realtime middleware
that touches RealtimeTicket / Device / other Django models.
"""

import os
import asyncio
import time
from datetime import datetime, timezone
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


class BenchmarkHttpTimingLog:
    """
    Benchmark-only ASGI timing log.

    UvicornWorker access logs do not expose the benchmark request headers or
    request duration in the format needed by the local benchmark analyzer. This
    wrapper is disabled unless MYNA_BENCHMARK_ASGI_ACCESS_LOG=1.
    """

    def __init__(self, app) -> None:
        self.app = app
        self.enabled = (
            os.getenv("MYNA_BENCHMARK_ASGI_ACCESS_LOG", "")
            .strip()
            .lower()
            in {"1", "true", "yes", "on"}
        )
        self.log_file = os.getenv(
            "MYNA_BENCHMARK_ASGI_ACCESS_LOG_FILE",
            os.getenv(
                "GUNICORN_ACCESS_LOG_FILE",
                "/tmp/myna_benchmark_gunicorn_access.log",
            ),
        )

    async def __call__(self, scope, receive, send) -> None:
        if not self.enabled or scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        started = time.perf_counter()
        status_code = 0

        async def timing_send(message):
            nonlocal status_code
            if message.get("type") == "http.response.start":
                status_code = int(message.get("status") or 0)
            await send(message)

        try:
            await self.app(scope, receive, timing_send)
        finally:
            duration_us = int((time.perf_counter() - started) * 1_000_000)
            headers = {
                key.decode("latin1").lower(): value.decode("latin1")
                for key, value in scope.get("headers", [])
            }
            path = scope.get("path", "")
            method = scope.get("method", "")
            line = (
                f"{datetime.now(timezone.utc).isoformat()} "
                f"pid={os.getpid()} "
                f"status={status_code} "
                f"duration_us={duration_us} "
                f'method="{method}" '
                f'path="{path}" '
                f'run="{headers.get("x-myna-benchmark-run-id", "")}" '
                f'req="{headers.get("x-myna-benchmark-request-id", "")}" '
                f'phase="{headers.get("x-myna-benchmark-phase", "")}" '
                f'concurrency="{headers.get("x-myna-benchmark-concurrency", "")}"'
            )
            with open(self.log_file, "a", encoding="utf-8") as handle:
                handle.write(line + "\n")


router = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": RealtimeTicketAuthMiddleware(
            URLRouter(websocket_urlpatterns),
        ),
    }
)

application = DefaultExecutorCap(
    BenchmarkHttpTimingLog(router),
    _configured_asgi_threads(),
)

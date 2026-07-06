"""
ASGI config for the Myna Messenger service.

Important import order:

Django apps must be loaded before importing modules that import models.
So get_asgi_application() must run before importing realtime middleware
that touches RealtimeTicket / Device / other Django models.
"""

import os
import asyncio
import json
import logging
import time
import traceback
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor

from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

from messenger_config.benchmark_timing import (
    BenchmarkRequestTiming,
    record_benchmark_thread_observation,
    record_django_asgi_entry,
    reset_benchmark_request_timing,
    set_benchmark_request_timing,
)

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "messenger_config.settings",
)

django_asgi_app = get_asgi_application()

from apps.realtime.authentication import RealtimeTicketAuthMiddleware  # noqa: E402
from messenger_config.routing import websocket_urlpatterns  # noqa: E402

logger = logging.getLogger(__name__)

_RECONCILIATION_TOLERANCE_US = 500

PRE_VIEW_BOUNDARY_LOG_FIELDS = (
    "pre_view_asgi_to_django_us",
    "pre_view_django_to_middleware_us",
    "pre_view_middleware_to_drf_dispatch_us",
    "pre_view_django_to_drf_dispatch_us",
    "drf_dispatch_pre_initialize_us",
    "drf_initialize_request_us",
    "drf_dispatch_pre_initial_us",
    "drf_initial_total_us",
    "drf_content_negotiation_us",
    "drf_versioning_us",
    "drf_authentication_total_us",
    "drf_permission_us",
    "drf_throttle_us",
    "drf_initial_unattributed_us",
    "drf_initial_to_post_us",
    "pre_view_unattributed_us",
    "pre_view_boundary_reconciliation_delta_us",
    "drf_initial_reconciliation_delta_us",
)

THREAD_OBSERVATION_BOUNDARIES = (
    "server_entry",
    "django_asgi_entry",
    "drf_dispatch_entry",
    "drf_initial_entry",
    "drf_initial_exit",
    "post_entry",
)


def _ns_delta_to_us(start_ns: int, end_ns: int) -> int:
    return int((end_ns - start_ns) / 1_000)


def _format_optional_us(value: int | None) -> str:
    return str(value) if value is not None else "-"


def _duration_us(start_ns: int | None, end_ns: int | None) -> int | None:
    if start_ns is None or end_ns is None:
        return None
    return _ns_delta_to_us(start_ns, end_ns)


def _sum_if_complete(values: list[int | None]) -> int | None:
    if any(value is None for value in values):
        return None
    return sum(value for value in values if value is not None)


def _derived_delta_us(parent: int | None, children: list[int | None]) -> int | None:
    child_sum = _sum_if_complete(children)
    if parent is None or child_sum is None:
        return None
    return parent - child_sum


def _add_warning(timing: BenchmarkRequestTiming, code: str) -> None:
    if code not in timing.warning_codes:
        timing.warning_codes.append(code)


def _thread_field_value(
    timing: BenchmarkRequestTiming,
    boundary: str,
    field: str,
) -> str:
    observation = timing.thread_observations.get(boundary)
    if observation is None:
        return "-"
    thread_id, thread_name = observation
    if field == "id":
        return str(thread_id)
    return thread_name.replace('"', "'").replace(" ", "_")


def _benchmark_boundary_fields(
    timing: BenchmarkRequestTiming,
) -> dict[str, int | None | str]:
    server_entry_ns = timing.server_entry_ns
    django_asgi_entry_ns = timing.django_asgi_entry_ns
    django_middleware_entry_ns = timing.django_middleware_entry_ns
    drf_dispatch_entry_ns = timing.drf_dispatch_entry_ns
    drf_initialize_request_entry_ns = timing.drf_initialize_request_entry_ns
    drf_initialize_request_exit_ns = timing.drf_initialize_request_exit_ns
    drf_initial_entry_ns = timing.drf_initial_entry_ns
    drf_initial_exit_ns = timing.drf_initial_exit_ns
    drf_content_negotiation_entry_ns = timing.drf_content_negotiation_entry_ns
    drf_content_negotiation_exit_ns = timing.drf_content_negotiation_exit_ns
    drf_versioning_entry_ns = timing.drf_versioning_entry_ns
    drf_versioning_exit_ns = timing.drf_versioning_exit_ns
    drf_authentication_entry_ns = timing.drf_authentication_entry_ns
    drf_authentication_exit_ns = timing.drf_authentication_exit_ns
    drf_permission_entry_ns = timing.drf_permission_entry_ns
    drf_permission_exit_ns = timing.drf_permission_exit_ns
    drf_throttle_entry_ns = timing.drf_throttle_entry_ns
    drf_throttle_exit_ns = timing.drf_throttle_exit_ns
    server_return_ns = timing.server_return_ns
    view_entry_ns = timing.view_entry_ns
    view_exit_ns = timing.view_exit_ns
    response_start_ns = timing.response_start_ns
    response_complete_ns = timing.response_complete_ns

    ordered_boundaries = [
        ("server_entry", server_entry_ns),
        ("django_asgi_entry", django_asgi_entry_ns),
        ("django_middleware_entry", django_middleware_entry_ns),
        ("drf_dispatch_entry", drf_dispatch_entry_ns),
        ("drf_initialize_request_entry", drf_initialize_request_entry_ns),
        ("drf_initialize_request_exit", drf_initialize_request_exit_ns),
        ("drf_initial_entry", drf_initial_entry_ns),
        ("drf_initial_exit", drf_initial_exit_ns),
        ("view_entry", view_entry_ns),
        ("view_exit", view_exit_ns),
        ("response_start", response_start_ns),
        ("response_complete", response_complete_ns),
        ("server_return", server_return_ns),
    ]
    previous_name = None
    previous_ns = None
    for name, boundary_ns in ordered_boundaries:
        if boundary_ns is None:
            continue
        if previous_ns is not None and boundary_ns < previous_ns:
            _add_warning(
                timing,
                f"NON_MONOTONIC_{previous_name}_TO_{name}".upper(),
            )
        previous_name = name
        previous_ns = boundary_ns

    server_total_us = _duration_us(server_entry_ns, server_return_ns)
    view_total_us = _duration_us(view_entry_ns, view_exit_ns)
    server_pre_view_us = _duration_us(server_entry_ns, view_entry_ns)
    server_post_view_us = _duration_us(view_exit_ns, server_return_ns)
    pre_view_asgi_to_django_us = _duration_us(
        server_entry_ns,
        django_asgi_entry_ns,
    )
    pre_view_django_to_middleware_us = _duration_us(
        django_asgi_entry_ns,
        django_middleware_entry_ns,
    )
    pre_view_middleware_to_drf_dispatch_us = _duration_us(
        django_middleware_entry_ns,
        drf_dispatch_entry_ns,
    )
    pre_view_django_to_drf_dispatch_us = _duration_us(
        django_asgi_entry_ns,
        drf_dispatch_entry_ns,
    )
    drf_dispatch_pre_initialize_us = _duration_us(
        drf_dispatch_entry_ns,
        drf_initialize_request_entry_ns,
    )
    drf_initialize_request_us = _duration_us(
        drf_initialize_request_entry_ns,
        drf_initialize_request_exit_ns,
    )
    drf_dispatch_pre_initial_us = _duration_us(
        drf_initialize_request_exit_ns,
        drf_initial_entry_ns,
    )
    drf_initial_total_us = _duration_us(
        drf_initial_entry_ns,
        drf_initial_exit_ns,
    )
    drf_content_negotiation_us = _duration_us(
        drf_content_negotiation_entry_ns,
        drf_content_negotiation_exit_ns,
    )
    drf_versioning_us = _duration_us(
        drf_versioning_entry_ns,
        drf_versioning_exit_ns,
    )
    drf_authentication_total_us = _duration_us(
        drf_authentication_entry_ns,
        drf_authentication_exit_ns,
    )
    drf_permission_us = _duration_us(
        drf_permission_entry_ns,
        drf_permission_exit_ns,
    )
    drf_throttle_us = _duration_us(
        drf_throttle_entry_ns,
        drf_throttle_exit_ns,
    )
    drf_initial_to_post_us = _duration_us(
        drf_initial_exit_ns,
        view_entry_ns,
    )
    drf_initial_children = [
        drf_content_negotiation_us,
        drf_versioning_us,
        drf_authentication_total_us,
        drf_permission_us,
        drf_throttle_us,
    ]
    drf_initial_unattributed_us = _derived_delta_us(
        drf_initial_total_us,
        drf_initial_children,
    )
    drf_initial_reconciliation_delta_us = None
    if drf_initial_unattributed_us is not None:
        drf_initial_reconciliation_delta_us = _derived_delta_us(
            drf_initial_total_us,
            drf_initial_children + [drf_initial_unattributed_us],
        )

    pre_view_children: list[int | None]
    if (
        pre_view_django_to_middleware_us is not None
        and pre_view_middleware_to_drf_dispatch_us is not None
    ):
        pre_view_children = [
            pre_view_asgi_to_django_us,
            pre_view_django_to_middleware_us,
            pre_view_middleware_to_drf_dispatch_us,
            drf_dispatch_pre_initialize_us,
            drf_initialize_request_us,
            drf_dispatch_pre_initial_us,
            drf_initial_total_us,
            drf_initial_to_post_us,
        ]
    else:
        pre_view_children = [
            pre_view_asgi_to_django_us,
            pre_view_django_to_drf_dispatch_us,
            drf_dispatch_pre_initialize_us,
            drf_initialize_request_us,
            drf_dispatch_pre_initial_us,
            drf_initial_total_us,
            drf_initial_to_post_us,
        ]
    pre_view_unattributed_us = _derived_delta_us(
        server_pre_view_us,
        pre_view_children,
    )
    pre_view_boundary_reconciliation_delta_us = None
    if pre_view_unattributed_us is not None:
        pre_view_boundary_reconciliation_delta_us = _derived_delta_us(
            server_pre_view_us,
            pre_view_children + [pre_view_unattributed_us],
        )
    post_view_to_response_start_us = _duration_us(view_exit_ns, response_start_ns)
    response_send_us = _duration_us(response_start_ns, response_complete_ns)
    asgi_after_response_complete_us = _duration_us(
        response_complete_ns,
        server_return_ns,
    )

    server_boundary_delta_us = None
    if (
        server_total_us is not None
        and server_pre_view_us is not None
        and view_total_us is not None
        and server_post_view_us is not None
    ):
        server_boundary_delta_us = server_total_us - (
            server_pre_view_us
            + view_total_us
            + server_post_view_us
        )
        if abs(server_boundary_delta_us) > _RECONCILIATION_TOLERANCE_US:
            _add_warning(timing, "SERVER_BOUNDARY_RECONCILIATION_FAILED")

    server_outside_view_delta_us = None
    if (
        server_total_us is not None
        and view_total_us is not None
        and server_pre_view_us is not None
        and server_post_view_us is not None
    ):
        server_outside_view_us = server_total_us - view_total_us
        server_outside_view_delta_us = server_outside_view_us - (
            server_pre_view_us
            + server_post_view_us
        )
        if abs(server_outside_view_delta_us) > _RECONCILIATION_TOLERANCE_US:
            _add_warning(timing, "SERVER_OUTSIDE_VIEW_RECONCILIATION_FAILED")

    for field_name, value in {
        "server_pre_view_us": server_pre_view_us,
        "view_total_us": view_total_us,
        "server_post_view_us": server_post_view_us,
        "pre_view_asgi_to_django_us": pre_view_asgi_to_django_us,
        "pre_view_django_to_middleware_us": pre_view_django_to_middleware_us,
        "pre_view_middleware_to_drf_dispatch_us": (
            pre_view_middleware_to_drf_dispatch_us
        ),
        "pre_view_django_to_drf_dispatch_us": pre_view_django_to_drf_dispatch_us,
        "drf_dispatch_pre_initialize_us": drf_dispatch_pre_initialize_us,
        "drf_initialize_request_us": drf_initialize_request_us,
        "drf_dispatch_pre_initial_us": drf_dispatch_pre_initial_us,
        "drf_initial_total_us": drf_initial_total_us,
        "drf_content_negotiation_us": drf_content_negotiation_us,
        "drf_versioning_us": drf_versioning_us,
        "drf_authentication_total_us": drf_authentication_total_us,
        "drf_permission_us": drf_permission_us,
        "drf_throttle_us": drf_throttle_us,
        "drf_initial_unattributed_us": drf_initial_unattributed_us,
        "drf_initial_to_post_us": drf_initial_to_post_us,
        "pre_view_unattributed_us": pre_view_unattributed_us,
        "post_view_to_response_start_us": post_view_to_response_start_us,
        "response_send_us": response_send_us,
        "asgi_after_response_complete_us": asgi_after_response_complete_us,
    }.items():
        if value is not None and value < -_RECONCILIATION_TOLERANCE_US:
            _add_warning(timing, f"NEGATIVE_{field_name}".upper())

    if (
        pre_view_boundary_reconciliation_delta_us is not None
        and abs(pre_view_boundary_reconciliation_delta_us)
        > _RECONCILIATION_TOLERANCE_US
    ):
        _add_warning(timing, "PRE_VIEW_BOUNDARY_RECONCILIATION_FAILED")
    if (
        drf_initial_reconciliation_delta_us is not None
        and abs(drf_initial_reconciliation_delta_us)
        > _RECONCILIATION_TOLERANCE_US
    ):
        _add_warning(timing, "DRF_INITIAL_RECONCILIATION_FAILED")
    for child_name, child_value in {
        "pre_view_asgi_to_django_us": pre_view_asgi_to_django_us,
        "pre_view_django_to_middleware_us": pre_view_django_to_middleware_us,
        "pre_view_middleware_to_drf_dispatch_us": (
            pre_view_middleware_to_drf_dispatch_us
        ),
        "pre_view_django_to_drf_dispatch_us": pre_view_django_to_drf_dispatch_us,
        "drf_dispatch_pre_initialize_us": drf_dispatch_pre_initialize_us,
        "drf_initialize_request_us": drf_initialize_request_us,
        "drf_dispatch_pre_initial_us": drf_dispatch_pre_initial_us,
        "drf_initial_total_us": drf_initial_total_us,
        "drf_initial_to_post_us": drf_initial_to_post_us,
    }.items():
        if (
            server_pre_view_us is not None
            and child_value is not None
            and child_value - server_pre_view_us > _RECONCILIATION_TOLERANCE_US
        ):
            _add_warning(timing, f"{child_name}_EXCEEDS_SERVER_PRE_VIEW".upper())
    for child_name, child_value in {
        "drf_content_negotiation_us": drf_content_negotiation_us,
        "drf_versioning_us": drf_versioning_us,
        "drf_authentication_total_us": drf_authentication_total_us,
        "drf_permission_us": drf_permission_us,
        "drf_throttle_us": drf_throttle_us,
    }.items():
        if (
            drf_initial_total_us is not None
            and child_value is not None
            and child_value - drf_initial_total_us > _RECONCILIATION_TOLERANCE_US
        ):
            _add_warning(timing, f"{child_name}_EXCEEDS_DRF_INITIAL".upper())

    if view_entry_ns is not None:
        for required_name, required_value in {
            "django_asgi_entry": django_asgi_entry_ns,
            "drf_dispatch_entry": drf_dispatch_entry_ns,
            "drf_initialize_request_entry": drf_initialize_request_entry_ns,
            "drf_initialize_request_exit": drf_initialize_request_exit_ns,
            "drf_initial_entry": drf_initial_entry_ns,
            "drf_initial_exit": drf_initial_exit_ns,
        }.items():
            if required_value is None:
                _add_warning(
                    timing,
                    f"MISSING_REQUIRED_{required_name}".upper(),
                )

    fields: dict[str, int | None | str] = {
        "view_entry_us": _duration_us(server_entry_ns, view_entry_ns),
        "view_exit_us": _duration_us(server_entry_ns, view_exit_ns),
        "server_pre_view_us": server_pre_view_us,
        "view_total_us": view_total_us,
        "server_post_view_us": server_post_view_us,
        "pre_view_asgi_to_django_us": pre_view_asgi_to_django_us,
        "pre_view_django_to_middleware_us": pre_view_django_to_middleware_us,
        "pre_view_middleware_to_drf_dispatch_us": (
            pre_view_middleware_to_drf_dispatch_us
        ),
        "pre_view_django_to_drf_dispatch_us": pre_view_django_to_drf_dispatch_us,
        "drf_dispatch_pre_initialize_us": drf_dispatch_pre_initialize_us,
        "drf_initialize_request_us": drf_initialize_request_us,
        "drf_dispatch_pre_initial_us": drf_dispatch_pre_initial_us,
        "drf_initial_total_us": drf_initial_total_us,
        "drf_content_negotiation_us": drf_content_negotiation_us,
        "drf_versioning_us": drf_versioning_us,
        "drf_authentication_total_us": drf_authentication_total_us,
        "drf_permission_us": drf_permission_us,
        "drf_throttle_us": drf_throttle_us,
        "drf_initial_unattributed_us": drf_initial_unattributed_us,
        "drf_initial_to_post_us": drf_initial_to_post_us,
        "pre_view_unattributed_us": pre_view_unattributed_us,
        "pre_view_boundary_reconciliation_delta_us": (
            pre_view_boundary_reconciliation_delta_us
        ),
        "drf_initial_reconciliation_delta_us": (
            drf_initial_reconciliation_delta_us
        ),
        "post_view_to_response_start_us": post_view_to_response_start_us,
        "response_send_us": response_send_us,
        "asgi_after_response_complete_us": asgi_after_response_complete_us,
        "server_boundary_reconciliation_delta_us": server_boundary_delta_us,
        "server_outside_view_reconciliation_delta_us": (
            server_outside_view_delta_us
        ),
        "instrumentation_warning_count": len(timing.warning_codes),
        "instrumentation_warnings": (
            ",".join(timing.warning_codes)
            if timing.warning_codes
            else "-"
        ),
    }
    for boundary in THREAD_OBSERVATION_BOUNDARIES:
        fields[f"thread_{boundary}_id"] = _thread_field_value(
            timing,
            boundary,
            "id",
        )
        fields[f"thread_{boundary}_name"] = _thread_field_value(
            timing,
            boundary,
            "name",
        )
    return fields


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


class BenchmarkDjangoAsgiEntryTiming:
    """
    Records the supported boundary immediately before the Django ASGI app.

    This wrapper sits inside the benchmark server wrapper. It does not measure
    any server admission work before BenchmarkHttpTimingLog records SERVER_ENTRY.
    """

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope.get("type") == "http":
            record_django_asgi_entry()
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
        self.exception_log_file = os.getenv(
            "MYNA_BENCHMARK_ASGI_EXCEPTION_LOG_FILE",
            "/tmp/myna_benchmark_asgi_exceptions.jsonl",
        )

    async def __call__(self, scope, receive, send) -> None:
        if not self.enabled or scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        server_entry_ns = time.perf_counter_ns()
        timing = BenchmarkRequestTiming(server_entry_ns=server_entry_ns)
        record_benchmark_thread_observation(timing, "server_entry")
        timing_token = set_benchmark_request_timing(timing)
        status_code = 0
        response_start_us = None
        response_complete_us = None

        async def timing_send(message):
            nonlocal response_complete_us, response_start_us, status_code
            if message.get("type") == "http.response.start":
                status_code = int(message.get("status") or 0)
                response_start_ns = time.perf_counter_ns()
                timing.response_start_ns = response_start_ns
                response_start_us = _ns_delta_to_us(
                    server_entry_ns,
                    response_start_ns,
                )
            if (
                message.get("type") == "http.response.body"
                and not message.get("more_body", False)
            ):
                response_complete_ns = time.perf_counter_ns()
                timing.response_complete_ns = response_complete_ns
                response_complete_us = _ns_delta_to_us(
                    server_entry_ns,
                    response_complete_ns,
                )
            await send(message)

        headers: dict[str, str] = {}
        try:
            await self.app(scope, receive, timing_send)
        except Exception as exc:
            headers = {
                key.decode("latin1").lower(): value.decode("latin1")
                for key, value in scope.get("headers", [])
            }
            diagnostic = {
                "type": "myna_benchmark_asgi_exception",
                "captured_at": datetime.now(timezone.utc).isoformat(),
                "pid": os.getpid(),
                "benchmark_run_id": headers.get("x-myna-benchmark-run-id", ""),
                "benchmark_request_id": headers.get("x-myna-benchmark-request-id", ""),
                "benchmark_phase": headers.get("x-myna-benchmark-phase", ""),
                "benchmark_concurrency": headers.get("x-myna-benchmark-concurrency", ""),
                "method": scope.get("method", ""),
                "path": scope.get("path", ""),
                "exception_type": exc.__class__.__name__,
                "exception_message": str(exc),
                "exception_signature": f"{exc.__class__.__name__}({str(exc)!r})",
                "traceback": traceback.format_exc(),
            }
            try:
                with open(self.exception_log_file, "a", encoding="utf-8") as handle:
                    handle.write(json.dumps(diagnostic, sort_keys=True) + "\n")
            except Exception:
                logger.exception(
                    "Failed to write benchmark ASGI exception diagnostic.",
                    extra={
                        "benchmark_run_id": diagnostic["benchmark_run_id"],
                        "benchmark_request_id": diagnostic["benchmark_request_id"],
                    },
                )
            logger.exception(
                "Unhandled benchmark HTTP request exception.",
                extra={
                    "benchmark_run_id": diagnostic["benchmark_run_id"],
                    "benchmark_request_id": diagnostic["benchmark_request_id"],
                    "benchmark_phase": diagnostic["benchmark_phase"],
                    "benchmark_concurrency": diagnostic["benchmark_concurrency"],
                    "method": diagnostic["method"],
                    "path": diagnostic["path"],
                    "exception_type": diagnostic["exception_type"],
                },
            )
            raise
        finally:
            try:
                server_return_ns = time.perf_counter_ns()
                timing.server_return_ns = server_return_ns
                duration_us = _ns_delta_to_us(server_entry_ns, server_return_ns)
                boundary_fields = _benchmark_boundary_fields(timing)
                pre_view_boundary_text = " ".join(
                    f"{field}={_format_optional_us(boundary_fields[field])}"
                    for field in PRE_VIEW_BOUNDARY_LOG_FIELDS
                )
                thread_boundary_text = " ".join(
                    f'{field}="{boundary_fields[field]}"'
                    for boundary in THREAD_OBSERVATION_BOUNDARIES
                    for field in (
                        f"thread_{boundary}_id",
                        f"thread_{boundary}_name",
                    )
                )
                if not headers:
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
                    f"response_start_us={response_start_us if response_start_us is not None else '-'} "
                    f"response_complete_us={response_complete_us if response_complete_us is not None else '-'} "
                    f"view_entry_us={_format_optional_us(boundary_fields['view_entry_us'])} "
                    f"view_exit_us={_format_optional_us(boundary_fields['view_exit_us'])} "
                    f"server_pre_view_us={_format_optional_us(boundary_fields['server_pre_view_us'])} "
                    f"view_total_us={_format_optional_us(boundary_fields['view_total_us'])} "
                    f"server_post_view_us={_format_optional_us(boundary_fields['server_post_view_us'])} "
                    f"{pre_view_boundary_text} "
                    f"post_view_to_response_start_us={_format_optional_us(boundary_fields['post_view_to_response_start_us'])} "
                    f"response_send_us={_format_optional_us(boundary_fields['response_send_us'])} "
                    f"asgi_after_response_complete_us={_format_optional_us(boundary_fields['asgi_after_response_complete_us'])} "
                    f"server_boundary_reconciliation_delta_us={_format_optional_us(boundary_fields['server_boundary_reconciliation_delta_us'])} "
                    f"server_outside_view_reconciliation_delta_us={_format_optional_us(boundary_fields['server_outside_view_reconciliation_delta_us'])} "
                    f"instrumentation_warning_count={boundary_fields['instrumentation_warning_count']} "
                    f'instrumentation_warnings="{boundary_fields["instrumentation_warnings"]}" '
                    f"{thread_boundary_text} "
                    f'method="{method}" '
                    f'path="{path}" '
                    f'run="{headers.get("x-myna-benchmark-run-id", "")}" '
                    f'req="{headers.get("x-myna-benchmark-request-id", "")}" '
                    f'phase="{headers.get("x-myna-benchmark-phase", "")}" '
                    f'concurrency="{headers.get("x-myna-benchmark-concurrency", "")}"'
                )
                with open(self.log_file, "a", encoding="utf-8") as handle:
                    handle.write(line + "\n")
            finally:
                reset_benchmark_request_timing(timing_token)


router = ProtocolTypeRouter(
    {
        "http": BenchmarkDjangoAsgiEntryTiming(django_asgi_app),
        "websocket": RealtimeTicketAuthMiddleware(
            URLRouter(websocket_urlpatterns),
        ),
    }
)

application = DefaultExecutorCap(
    BenchmarkHttpTimingLog(router),
    _configured_asgi_threads(),
)

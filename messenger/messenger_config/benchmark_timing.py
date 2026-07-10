from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass, field
import threading
import time


@dataclass(slots=True)
class BenchmarkRequestTiming:
    server_entry_ns: int
    django_asgi_entry_ns: int | None = None
    django_wsgi_entry_ns: int | None = None
    django_middleware_entry_ns: int | None = None
    drf_dispatch_entry_ns: int | None = None
    drf_initialize_request_entry_ns: int | None = None
    drf_initialize_request_exit_ns: int | None = None
    drf_initial_entry_ns: int | None = None
    drf_initial_exit_ns: int | None = None
    drf_content_negotiation_entry_ns: int | None = None
    drf_content_negotiation_exit_ns: int | None = None
    drf_versioning_entry_ns: int | None = None
    drf_versioning_exit_ns: int | None = None
    drf_authentication_entry_ns: int | None = None
    drf_authentication_exit_ns: int | None = None
    drf_permission_entry_ns: int | None = None
    drf_permission_exit_ns: int | None = None
    drf_throttle_entry_ns: int | None = None
    drf_throttle_exit_ns: int | None = None
    drf_finalize_response_entry_ns: int | None = None
    drf_finalize_response_exit_ns: int | None = None
    view_entry_ns: int | None = None
    view_exit_ns: int | None = None
    response_start_ns: int | None = None
    response_complete_ns: int | None = None
    wsgi_start_response_ns: int | None = None
    wsgi_app_return_ns: int | None = None
    wsgi_response_iter_start_ns: int | None = None
    wsgi_response_complete_ns: int | None = None
    server_return_ns: int | None = None
    thread_observations: dict[str, tuple[int, str]] = field(default_factory=dict)
    warning_codes: list[str] = field(default_factory=list)


_ACTIVE_BENCHMARK_REQUEST_TIMING: ContextVar[
    BenchmarkRequestTiming | None
] = ContextVar(
    "myna_active_benchmark_request_timing",
    default=None,
)


def set_benchmark_request_timing(
    timing: BenchmarkRequestTiming,
) -> Token[BenchmarkRequestTiming | None]:
    return _ACTIVE_BENCHMARK_REQUEST_TIMING.set(timing)


def reset_benchmark_request_timing(
    token: Token[BenchmarkRequestTiming | None],
) -> None:
    _ACTIVE_BENCHMARK_REQUEST_TIMING.reset(token)


def active_benchmark_request_timing() -> BenchmarkRequestTiming | None:
    return _ACTIVE_BENCHMARK_REQUEST_TIMING.get()


def _capture_thread_observation(timing: BenchmarkRequestTiming, name: str) -> None:
    current = threading.current_thread()
    timing.thread_observations[name] = (threading.get_ident(), current.name)


def record_benchmark_thread_observation(
    timing: BenchmarkRequestTiming | None,
    name: str,
) -> None:
    if timing is not None:
        _capture_thread_observation(timing, name)


def _record_timestamp(
    field_name: str,
    *,
    ns: int | None = None,
    thread_boundary: str | None = None,
    only_if_missing: bool = False,
) -> int:
    captured_ns = time.perf_counter_ns() if ns is None else ns
    timing = active_benchmark_request_timing()
    if timing is not None:
        if not only_if_missing or getattr(timing, field_name) is None:
            setattr(timing, field_name, captured_ns)
            if thread_boundary is not None:
                _capture_thread_observation(timing, thread_boundary)
    return captured_ns


def record_django_asgi_entry(ns: int | None = None) -> int:
    return _record_timestamp(
        "django_asgi_entry_ns",
        ns=ns,
        thread_boundary="django_asgi_entry",
        only_if_missing=True,
    )


def record_django_wsgi_entry(ns: int | None = None) -> int:
    return _record_timestamp(
        "django_wsgi_entry_ns",
        ns=ns,
        thread_boundary="django_wsgi_entry",
        only_if_missing=True,
    )


def record_django_middleware_entry(ns: int | None = None) -> int:
    return _record_timestamp(
        "django_middleware_entry_ns",
        ns=ns,
        only_if_missing=True,
    )


def record_drf_dispatch_entry(ns: int | None = None) -> int:
    return _record_timestamp(
        "drf_dispatch_entry_ns",
        ns=ns,
        thread_boundary="drf_dispatch_entry",
        only_if_missing=True,
    )


def record_drf_initialize_request_entry(ns: int | None = None) -> int:
    return _record_timestamp("drf_initialize_request_entry_ns", ns=ns)


def record_drf_initialize_request_exit(ns: int | None = None) -> int:
    return _record_timestamp("drf_initialize_request_exit_ns", ns=ns)


def record_drf_initial_entry(ns: int | None = None) -> int:
    return _record_timestamp(
        "drf_initial_entry_ns",
        ns=ns,
        thread_boundary="drf_initial_entry",
        only_if_missing=True,
    )


def record_drf_initial_exit(ns: int | None = None) -> int:
    return _record_timestamp(
        "drf_initial_exit_ns",
        ns=ns,
        thread_boundary="drf_initial_exit",
    )


def record_drf_content_negotiation_entry(ns: int | None = None) -> int:
    return _record_timestamp("drf_content_negotiation_entry_ns", ns=ns)


def record_drf_content_negotiation_exit(ns: int | None = None) -> int:
    return _record_timestamp("drf_content_negotiation_exit_ns", ns=ns)


def record_drf_versioning_entry(ns: int | None = None) -> int:
    return _record_timestamp("drf_versioning_entry_ns", ns=ns)


def record_drf_versioning_exit(ns: int | None = None) -> int:
    return _record_timestamp("drf_versioning_exit_ns", ns=ns)


def record_drf_authentication_entry(ns: int | None = None) -> int:
    return _record_timestamp("drf_authentication_entry_ns", ns=ns)


def record_drf_authentication_exit(ns: int | None = None) -> int:
    return _record_timestamp("drf_authentication_exit_ns", ns=ns)


def record_drf_permission_entry(ns: int | None = None) -> int:
    return _record_timestamp("drf_permission_entry_ns", ns=ns)


def record_drf_permission_exit(ns: int | None = None) -> int:
    return _record_timestamp("drf_permission_exit_ns", ns=ns)


def record_drf_throttle_entry(ns: int | None = None) -> int:
    return _record_timestamp("drf_throttle_entry_ns", ns=ns)


def record_drf_throttle_exit(ns: int | None = None) -> int:
    return _record_timestamp("drf_throttle_exit_ns", ns=ns)


def record_drf_finalize_response_entry(ns: int | None = None) -> int:
    return _record_timestamp(
        "drf_finalize_response_entry_ns",
        ns=ns,
        only_if_missing=True,
    )


def record_drf_finalize_response_exit(ns: int | None = None) -> int:
    return _record_timestamp(
        "drf_finalize_response_exit_ns",
        ns=ns,
    )


def record_direct_send_view_entry(ns: int | None = None) -> int:
    return _record_timestamp(
        "view_entry_ns",
        ns=ns,
        thread_boundary="post_entry",
    )


def record_direct_send_view_exit(ns: int | None = None) -> int:
    return _record_timestamp("view_exit_ns", ns=ns)


class BenchmarkPreViewTimingMiddleware:
    """
    Benchmark-only marker for the first Django middleware request boundary.

    It is inserted only for benchmark timing/profiling runs. The middleware
    is otherwise a transparent pass-through and is not active in production.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        record_django_middleware_entry()
        return self.get_response(request)

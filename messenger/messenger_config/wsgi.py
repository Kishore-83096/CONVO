"""
WSGI config for messenger_config project.

The benchmark wrapper is transparent unless the Gunicorn benchmark worker has
created a request-local BenchmarkRequestTiming context. Normal production WSGI
requests therefore use the same Django application behavior without profiling.
"""

import os
import time
from collections.abc import Iterable, Iterator
from typing import Any

from django.core.wsgi import get_wsgi_application

from messenger_config.benchmark_timing import (
    active_benchmark_request_timing,
    record_django_wsgi_entry,
)

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "messenger_config.settings",
)


django_wsgi_application = get_wsgi_application()


class BenchmarkDjangoWsgiTiming:
    def __init__(self, app) -> None:
        self.app = app

    def __call__(self, environ, start_response) -> Iterable[bytes]:
        timing = active_benchmark_request_timing()
        if timing is None:
            return self.app(environ, start_response)

        record_django_wsgi_entry()

        def timing_start_response(
            status: str,
            response_headers: list[tuple[str, str]],
            exc_info: Any = None,
        ):
            captured_ns = time.perf_counter_ns()
            timing.wsgi_start_response_ns = captured_ns
            timing.response_start_ns = captured_ns
            if exc_info is None:
                return start_response(status, response_headers)
            return start_response(status, response_headers, exc_info)

        response = self.app(environ, timing_start_response)
        timing.wsgi_app_return_ns = time.perf_counter_ns()

        def iter_response() -> Iterator[bytes]:
            iterator = iter(response)
            first_item = True
            try:
                while True:
                    try:
                        item = next(iterator)
                    except StopIteration:
                        break
                    if first_item:
                        timing.wsgi_response_iter_start_ns = (
                            time.perf_counter_ns()
                        )
                        first_item = False
                    yield item
            finally:
                completed_ns = time.perf_counter_ns()
                if timing.wsgi_response_iter_start_ns is None:
                    timing.wsgi_response_iter_start_ns = completed_ns
                timing.wsgi_response_complete_ns = completed_ns
                timing.response_complete_ns = completed_ns
                close = getattr(response, "close", None)
                if callable(close):
                    close()

        return iter_response()


application = BenchmarkDjangoWsgiTiming(
    django_wsgi_application,
)

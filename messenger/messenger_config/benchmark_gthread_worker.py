from __future__ import annotations

from datetime import datetime, timezone
import os
import queue
import threading
import time

from gunicorn.workers.gthread import ThreadWorker

from messenger_config.benchmark_timing import (
    BenchmarkRequestTiming,
    record_benchmark_thread_observation,
    reset_benchmark_request_timing,
    set_benchmark_request_timing,
)
from messenger_config.benchmark_wsgi_timing import (
    POST_VIEW_WSGI_BOUNDARY_LOG_FIELDS,
    PRE_VIEW_WSGI_BOUNDARY_LOG_FIELDS,
    THREAD_OBSERVATION_BOUNDARIES,
    build_wsgi_boundary_fields,
    format_optional_us,
)

QUEUE_LOG_FILE = "/tmp/myna_gthread_queue.log"
DEFAULT_TIMING_LOG_FILE = "/tmp/myna_benchmark_gunicorn_access.log"


_LOG_QUEUE: queue.SimpleQueue[tuple[str, str]] = queue.SimpleQueue()
_LOG_THREAD_LOCK = threading.Lock()
_LOG_THREAD_STARTED = False


def _header(req, wanted):
    wanted = wanted.lower()
    for name, value in getattr(req, "headers", ()):
        if str(name).lower() == wanted:
            return str(value)
    return ""


def _append_line(path: str, line: str) -> None:
    fd = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_APPEND,
        0o644,
    )
    try:
        os.write(fd, line.encode("utf-8"))
    finally:
        os.close(fd)


def _log_writer() -> None:
    while True:
        path, line = _LOG_QUEUE.get()
        _append_line(path, line)


def _ensure_log_writer() -> None:
    global _LOG_THREAD_STARTED
    if _LOG_THREAD_STARTED:
        return
    with _LOG_THREAD_LOCK:
        if _LOG_THREAD_STARTED:
            return
        thread = threading.Thread(
            target=_log_writer,
            name="myna-benchmark-log-writer",
            daemon=True,
        )
        thread.start()
        _LOG_THREAD_STARTED = True


def _enqueue_log_line(path: str, line: str) -> None:
    _ensure_log_writer()
    _LOG_QUEUE.put((path, line))


class BenchmarkThreadWorker(ThreadWorker):
    def enqueue_req(self, conn):
        queue_enter_ns = time.perf_counter_ns()
        conn._myna_queue_enter_ns = queue_enter_ns
        conn._myna_enqueue_worker_pid = os.getpid()
        return super().enqueue_req(conn)

    def handle(self, conn):
        handle_start_ns = time.perf_counter_ns()
        queue_enter_ns = getattr(
            conn,
            "_myna_queue_enter_ns",
            None,
        )

        conn._myna_handle_start_ns = handle_start_ns
        conn._myna_handle_worker_pid = os.getpid()
        conn._myna_handle_thread_ident = threading.get_ident()
        conn._myna_handle_thread_name = threading.current_thread().name

        if queue_enter_ns is not None:
            conn._myna_queue_wait_us = max(
                0,
                (handle_start_ns - queue_enter_ns) // 1000,
            )
        else:
            conn._myna_queue_wait_us = 0

        return super().handle(conn)

    def handle_request(self, req, conn):
        request_id = _header(
            req,
            "X-Myna-Benchmark-Request-Id",
        )
        run_id = _header(req, "X-Myna-Benchmark-Run-Id")
        phase = _header(req, "X-Myna-Benchmark-Phase")
        concurrency = _header(
            req,
            "X-Myna-Benchmark-Concurrency",
        )

        timing = None
        timing_token = None
        if request_id:
            timing = BenchmarkRequestTiming(
                server_entry_ns=time.perf_counter_ns(),
            )
            record_benchmark_thread_observation(
                timing,
                "server_entry",
            )
            timing_token = set_benchmark_request_timing(timing)

        try:
            return super().handle_request(req, conn)
        finally:
            if request_id:
                queue_line = (
                    f"run={run_id} "
                    f"req={request_id} "
                    f"phase={phase} "
                    f"concurrency={concurrency} "
                    f"worker_pid={os.getpid()} "
                    f"enqueue_worker_pid={getattr(conn, '_myna_enqueue_worker_pid', 0)} "
                    f"handle_worker_pid={getattr(conn, '_myna_handle_worker_pid', 0)} "
                    f"thread_ident={getattr(conn, '_myna_handle_thread_ident', 0)} "
                    f"thread_name={getattr(conn, '_myna_handle_thread_name', '')} "
                    f"queue_enter_ns={getattr(conn, '_myna_queue_enter_ns', 0)} "
                    f"handle_start_ns={getattr(conn, '_myna_handle_start_ns', 0)} "
                    f"queue_wait_us={getattr(conn, '_myna_queue_wait_us', 0)}\n"
                )

                if timing is not None:
                    timing.server_return_ns = time.perf_counter_ns()
                    boundary_fields = build_wsgi_boundary_fields(timing)
                    timing_log_file = os.getenv(
                        "GUNICORN_ACCESS_LOG_FILE",
                        DEFAULT_TIMING_LOG_FILE,
                    )
                    boundary_names = (
                        (
                            "view_entry_us",
                            "view_exit_us",
                            "server_pre_view_us",
                            "view_total_us",
                            "server_post_view_us",
                        )
                        + PRE_VIEW_WSGI_BOUNDARY_LOG_FIELDS
                        + POST_VIEW_WSGI_BOUNDARY_LOG_FIELDS
                        + (
                            "server_boundary_reconciliation_delta_us",
                            "server_outside_view_reconciliation_delta_us",
                            "instrumentation_warning_count",
                        )
                    )
                    boundary_text = " ".join(
                        f"{name}={format_optional_us(boundary_fields.get(name))}"
                        for name in boundary_names
                    )
                    thread_text = " ".join(
                        f'{field}="{boundary_fields[field]}"'
                        for boundary in THREAD_OBSERVATION_BOUNDARIES
                        for field in (
                            f"thread_{boundary}_id",
                            f"thread_{boundary}_name",
                        )
                    )
                    timing_line = (
                        f"{datetime.now(timezone.utc).isoformat()} "
                        f"timing_mode=wsgi "
                        f"wsgi_timing_total_us={format_optional_us(boundary_fields.get('wsgi_timing_total_us'))} "
                        f"{boundary_text} "
                        f'instrumentation_warnings="{boundary_fields["instrumentation_warnings"]}" '
                        f"{thread_text} "
                        f'run="{run_id}" '
                        f'req="{request_id}" '
                        f'phase="{phase}" '
                        f'concurrency="{concurrency}"\n'
                    )
                    _enqueue_log_line(timing_log_file, timing_line)

                _enqueue_log_line(QUEUE_LOG_FILE, queue_line)

                if timing_token is not None:
                    reset_benchmark_request_timing(timing_token)

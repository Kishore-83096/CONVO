import os
import queue
import threading
import time

from gunicorn.workers.gthread import ThreadWorker


LOG_FILE = "/tmp/myna_gthread_queue.log"
WRITER_BATCH_SIZE = max(
    1,
    int(os.getenv("MYNA_GTHREAD_QUEUE_WRITER_BATCH_SIZE", "128")),
)

_RECORD_QUEUE: queue.SimpleQueue[str] = queue.SimpleQueue()
_WRITER_START_LOCK = threading.Lock()
_WRITER_STARTED = False


def _header_map(req):
    return {
        str(name).lower(): str(value)
        for name, value in getattr(req, "headers", ())
    }


def _write_batch(lines):
    payload = "".join(lines).encode("utf-8")
    if not payload:
        return

    fd = os.open(
        LOG_FILE,
        os.O_WRONLY | os.O_CREAT | os.O_APPEND,
        0o644,
    )

    try:
        offset = 0
        while offset < len(payload):
            written = os.write(fd, payload[offset:])
            if written <= 0:
                raise OSError("Queue instrumentation writer made no progress.")
            offset += written
    finally:
        os.close(fd)


def _writer_loop():
    while True:
        first_line = _RECORD_QUEUE.get()
        batch = [first_line]

        while len(batch) < WRITER_BATCH_SIZE:
            try:
                batch.append(_RECORD_QUEUE.get_nowait())
            except queue.Empty:
                break

        try:
            _write_batch(batch)
        except OSError:
            # Queue instrumentation must never crash a Gunicorn request worker.
            # Missing samples are detected by the benchmark report pipeline.
            continue


def _ensure_writer_started():
    global _WRITER_STARTED

    if _WRITER_STARTED:
        return

    with _WRITER_START_LOCK:
        if _WRITER_STARTED:
            return

        writer = threading.Thread(
            target=_writer_loop,
            name=f"myna-gthread-queue-writer-{os.getpid()}",
            daemon=True,
        )
        writer.start()
        _WRITER_STARTED = True


class BenchmarkThreadWorker(ThreadWorker):
    def init_process(self):
        # Gunicorn calls init_process in the worker process. Start one queue-log
        # writer thread per worker before the request loop begins.
        _ensure_writer_started()
        return super().init_process()

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
        headers = _header_map(req)
        request_id = headers.get("x-myna-benchmark-request-id", "")

        if request_id:
            line = (
                f"run={headers.get('x-myna-benchmark-run-id', '')} "
                f"req={request_id} "
                f"phase={headers.get('x-myna-benchmark-phase', '')} "
                f"concurrency={headers.get('x-myna-benchmark-concurrency', '')} "
                f"worker_pid={os.getpid()} "
                f"enqueue_worker_pid={getattr(conn, '_myna_enqueue_worker_pid', 0)} "
                f"handle_worker_pid={getattr(conn, '_myna_handle_worker_pid', 0)} "
                f"thread_ident={getattr(conn, '_myna_handle_thread_ident', 0)} "
                f"thread_name={getattr(conn, '_myna_handle_thread_name', '')} "
                f"queue_enter_ns={getattr(conn, '_myna_queue_enter_ns', 0)} "
                f"handle_start_ns={getattr(conn, '_myna_handle_start_ns', 0)} "
                f"queue_wait_us={getattr(conn, '_myna_queue_wait_us', 0)}\n"
            )

            # Request threads only enqueue an in-memory record. File open/write/
            # close happens on the dedicated per-worker background writer.
            _RECORD_QUEUE.put(line)

        return super().handle_request(req, conn)

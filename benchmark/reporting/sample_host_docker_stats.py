#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import http.client
import json
import os
import signal
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote


class UnixHTTPConnection(http.client.HTTPConnection):
    def __init__(self, unix_socket_path: str, timeout: float = 2.0) -> None:
        super().__init__("localhost", timeout=timeout)
        self.unix_socket_path = unix_socket_path

    def connect(self) -> None:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        sock.connect(self.unix_socket_path)
        self.sock = sock


def engine_json(socket_path: str, path: str) -> dict[str, Any]:
    connection = UnixHTTPConnection(socket_path)
    try:
        connection.request("GET", path)
        response = connection.getresponse()
        payload = response.read()
        if response.status != 200:
            raise RuntimeError(
                f"Docker Engine API {path} returned HTTP {response.status}: "
                f"{payload[:200]!r}"
            )
        decoded = json.loads(payload.decode("utf-8"))
        if not isinstance(decoded, dict):
            raise RuntimeError(f"Docker Engine API {path} returned non-object JSON")
        return decoded
    finally:
        connection.close()


def cpu_snapshot(stats: dict[str, Any]) -> tuple[int, int, int]:
    cpu_stats = stats.get("cpu_stats") or {}
    cpu_usage = cpu_stats.get("cpu_usage") or {}
    total_usage = int(cpu_usage.get("total_usage") or 0)
    system_usage = int(cpu_stats.get("system_cpu_usage") or 0)
    online_cpus = int(cpu_stats.get("online_cpus") or 0)
    if online_cpus <= 0:
        online_cpus = len(cpu_usage.get("percpu_usage") or []) or 1
    return total_usage, system_usage, online_cpus


def cpu_percent(
    current: tuple[int, int, int],
    previous: tuple[int, int, int] | None,
) -> float | None:
    if previous is None:
        return None
    cpu_delta = current[0] - previous[0]
    system_delta = current[1] - previous[1]
    if cpu_delta < 0 or system_delta <= 0:
        return None
    return (cpu_delta / system_delta) * current[2] * 100.0


def memory_values(stats: dict[str, Any]) -> tuple[int, int, float | None]:
    memory_stats = stats.get("memory_stats") or {}
    usage = int(memory_stats.get("usage") or 0)
    limit = int(memory_stats.get("limit") or 0)
    details = memory_stats.get("stats") or {}
    reclaimable = int(
        details.get("inactive_file")
        if details.get("inactive_file") is not None
        else details.get("cache") or 0
    )
    used = max(0, usage - reclaimable)
    percent = (used / limit) * 100.0 if limit > 0 else None
    return used, limit, percent


def network_values(stats: dict[str, Any]) -> tuple[int, int]:
    rx = 0
    tx = 0
    for values in (stats.get("networks") or {}).values():
        if not isinstance(values, dict):
            continue
        rx += int(values.get("rx_bytes") or 0)
        tx += int(values.get("tx_bytes") or 0)
    return rx, tx


def block_values(stats: dict[str, Any]) -> tuple[int, int]:
    read_bytes = 0
    write_bytes = 0
    blkio = stats.get("blkio_stats") or {}
    for item in blkio.get("io_service_bytes_recursive") or []:
        if not isinstance(item, dict):
            continue
        operation = str(item.get("op") or "").strip().lower()
        value = int(item.get("value") or 0)
        if operation == "read":
            read_bytes += value
        elif operation == "write":
            write_bytes += value
    return read_bytes, write_bytes


def byte_pair(left: int, right: int) -> str:
    return f"{left}B / {right}B"


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00",
        "Z",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="High-cadence Docker Engine API one-shot stats sampler."
    )
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--socket", default="/var/run/docker.sock")
    parser.add_argument("container_ids", nargs="+")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.interval <= 0:
        raise SystemExit("--interval must be greater than zero")
    if not os.path.exists(args.socket):
        raise SystemExit(f"Docker socket not found: {args.socket}")

    version_payload = engine_json(args.socket, "/version")
    api_version = str(version_payload.get("ApiVersion") or "").strip()
    if not api_version:
        raise SystemExit("Docker Engine API version was unavailable")
    api_prefix = f"/v{api_version}"

    container_ids = list(dict.fromkeys(args.container_ids))
    names: dict[str, str] = {}
    for container_id in container_ids:
        inspect = engine_json(
            args.socket,
            f"{api_prefix}/containers/{quote(container_id, safe='')}/json",
        )
        names[container_id] = str(inspect.get("Name") or container_id).lstrip("/")

    output = Path(args.output_csv)
    output.parent.mkdir(parents=True, exist_ok=True)

    stop_event = threading.Event()

    def request_stop(_signum: int, _frame: Any) -> None:
        stop_event.set()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)

    previous_cpu: dict[str, tuple[int, int, int]] = {}
    headers = [
        "timestamp",
        "container",
        "cpu_percent",
        "mem_usage",
        "mem_percent",
        "net_io",
        "block_io",
        "pids",
    ]

    def fetch(container_id: str) -> tuple[str, dict[str, Any]]:
        path = (
            f"{api_prefix}/containers/{quote(container_id, safe='')}/stats"
            "?stream=false&one-shot=true"
        )
        return container_id, engine_json(args.socket, path)

    next_deadline = time.monotonic()
    with output.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        if output.stat().st_size == 0:
            writer.writerow(headers)
            handle.flush()

        with ThreadPoolExecutor(max_workers=len(container_ids)) as executor:
            while not stop_event.is_set():
                futures = [executor.submit(fetch, item) for item in container_ids]
                rows: list[list[Any]] = []
                timestamp = utc_timestamp()
                for future in as_completed(futures):
                    try:
                        container_id, stats = future.result()
                    except Exception:
                        continue
                    current_cpu = cpu_snapshot(stats)
                    cpu = cpu_percent(
                        current_cpu,
                        previous_cpu.get(container_id),
                    )
                    previous_cpu[container_id] = current_cpu
                    used, limit, mem_percent = memory_values(stats)
                    rx, tx = network_values(stats)
                    block_read, block_write = block_values(stats)
                    pids = int((stats.get("pids_stats") or {}).get("current") or 0)
                    rows.append(
                        [
                            timestamp,
                            names.get(container_id, container_id),
                            "" if cpu is None else f"{cpu:.6f}",
                            byte_pair(used, limit),
                            "" if mem_percent is None else f"{mem_percent:.6f}",
                            byte_pair(rx, tx),
                            byte_pair(block_read, block_write),
                            pids,
                        ]
                    )
                writer.writerows(rows)
                handle.flush()

                next_deadline += args.interval
                delay = next_deadline - time.monotonic()
                if delay > 0:
                    stop_event.wait(delay)
                else:
                    next_deadline = time.monotonic()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

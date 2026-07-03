#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
import os
import time
import traceback
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

import myna_distributed_pairs_latency_benchmark_test as dp


ENDPOINTS = [
    {
        "endpoint": "health",
        "method": "GET",
        "path": "/api/v1/health/",
        "requires_auth": False,
    },
    {
        "endpoint": "whoami",
        "method": "GET",
        "path": "/api/v1/auth/whoami/",
        "requires_auth": True,
    },
    {
        "endpoint": "send_message",
        "method": "POST",
        "path": "/api/v1/messages/direct/",
        "requires_auth": True,
    },
]


@dataclass
class EndpointRequestRecord:
    endpoint: str
    method: str
    path: str
    sequence: int
    token: str | None = None
    benchmark_request_id: str | None = None
    benchmark_phase: str | None = None
    benchmark_concurrency_header: int | None = None
    response_status: int | None = None
    response_body: Any = None
    latency_ms: float | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        if self.response_status is None or not (200 <= self.response_status < 300):
            return False
        if isinstance(self.response_body, dict) and self.response_body.get("success") is False:
            return False
        return True

    @property
    def server_timing_ms(self) -> dict[str, float]:
        if not isinstance(self.response_body, dict):
            return {}
        data = self.response_body.get("data")
        timings = data.get("server_timing_ms") if isinstance(data, dict) else None
        if not isinstance(timings, dict):
            return {}
        parsed: dict[str, float] = {}
        for key, value in timings.items():
            try:
                parsed[str(key)] = float(value)
            except (TypeError, ValueError):
                continue
        return parsed


def endpoint_levels() -> list[int]:
    return dp.parse_int_list(os.getenv("MYNA_ENDPOINT_BENCHMARK_LEVELS", "1,5,10,20,30,40,50,60,70,80,90,100"))


def requests_per_level() -> int:
    value = int(os.getenv("MYNA_ENDPOINT_BENCHMARK_REQUESTS_PER_LEVEL", "100"))
    if value < 1:
        raise RuntimeError("MYNA_ENDPOINT_BENCHMARK_REQUESTS_PER_LEVEL must be >= 1.")
    return value


def assign_endpoint_headers(records: list[EndpointRequestRecord], *, concurrency: int, phase: str) -> None:
    for ordinal, record in enumerate(records, start=1):
        record.benchmark_phase = phase
        record.benchmark_concurrency_header = concurrency
        record.benchmark_request_id = (
            f"{dp.TEST_RUN_ID}-{record.endpoint}-c{concurrency}-s{record.sequence}-r{ordinal}"
        )


async def send_one_endpoint_request(
    client: httpx.AsyncClient,
    *,
    record: EndpointRequestRecord,
    semaphore: asyncio.Semaphore,
) -> None:
    async with semaphore:
        url = dp.api_url(dp.CONFIG["MESSENGER_BASE_URL"], record.path)
        headers = dict(dp.HTTP_HEADERS)
        if record.token:
            headers["Authorization"] = f"Bearer {record.token}"
        if record.benchmark_request_id:
            headers["X-Myna-Benchmark-Run-Id"] = dp.TEST_RUN_ID
            headers["X-Myna-Benchmark-Request-Id"] = record.benchmark_request_id
            headers["X-Myna-Benchmark-Phase"] = record.benchmark_phase or dp.CURRENT_PHASE
            headers["X-Myna-Benchmark-Concurrency"] = str(record.benchmark_concurrency_header or "")

        started = time.perf_counter()
        try:
            response = await client.request(record.method, url, headers=headers)
            record.latency_ms = (time.perf_counter() - started) * 1000
            record.response_status = response.status_code
            record.response_body = dp.json_or_text(response)
            dp.record_api_call(record.method, url, response.status_code, record.latency_ms, record.ok)
        except Exception as exc:
            record.latency_ms = (time.perf_counter() - started) * 1000
            record.error = repr(exc)
            dp.record_api_call(record.method, url, None, record.latency_ms, False, repr(exc))


async def send_endpoint_requests(
    client: httpx.AsyncClient,
    *,
    records: list[EndpointRequestRecord],
    concurrency: int,
) -> None:
    semaphore = asyncio.Semaphore(max(1, concurrency))
    await asyncio.gather(
        *(send_one_endpoint_request(client, record=record, semaphore=semaphore) for record in records)
    )


def summarize_endpoint_records(
    records: list[EndpointRequestRecord],
    *,
    endpoint: dict[str, Any],
    concurrency: int,
    elapsed_ms: float,
) -> dict[str, Any]:
    ok_records = [record for record in records if record.ok]
    failed_records = [record for record in records if not record.ok]
    statuses: dict[str, int] = {}
    for record in records:
        key = str(record.response_status or "exception")
        statuses[key] = statuses.get(key, 0) + 1
    latencies = [record.latency_ms for record in records if record.latency_ms is not None]
    server_timing_values: dict[str, list[float]] = {}
    for record in ok_records:
        for key, value in record.server_timing_ms.items():
            server_timing_values.setdefault(key, []).append(value)

    return {
        "endpoint": endpoint["endpoint"],
        "method": endpoint["method"],
        "path": endpoint["path"],
        "total_requests": len(records),
        "total_messages": len(records),
        "concurrency": concurrency,
        "success_count": len(ok_records),
        "failure_count": len(failed_records),
        "status_counts": statuses,
        "latency_ms": dp._latency_summary([float(value) for value in latencies]),
        "server_timing_ms": {
            key: dp._latency_summary(values)
            for key, values in sorted(server_timing_values.items())
        },
        "total_send_elapsed_ms": round(elapsed_ms, 2),
        "requests_per_second": round(len(records) / max(elapsed_ms / 1000, 0.001), 2),
        "messages_per_second": round(len(records) / max(elapsed_ms / 1000, 0.001), 2),
        "failed_samples": [
            {
                "sequence": record.sequence,
                "status": record.response_status,
                "error": record.error,
                "body": record.response_body,
            }
            for record in failed_records[:20]
        ],
        "request_records": [
            {
                "sequence": record.sequence,
                "benchmark_request_id": record.benchmark_request_id,
                "benchmark_phase": record.benchmark_phase,
                "benchmark_concurrency": record.benchmark_concurrency_header,
                "latency_ms": round(record.latency_ms, 2) if record.latency_ms is not None else None,
                "status": record.response_status,
                "ok": record.ok,
                "server_timing_ms": record.server_timing_ms,
                "error": record.error,
            }
            for record in records
        ],
    }


def adapt_send_message_summary(
    summary: dict[str, Any],
    *,
    concurrency: int,
    elapsed_ms: float,
) -> dict[str, Any]:
    summary["endpoint"] = "send_message"
    summary["method"] = "POST"
    summary["path"] = "/api/v1/messages/direct/"
    summary["total_requests"] = summary.get("total_messages")
    summary["requests_per_second"] = round(int(summary.get("total_messages") or 0) / max(elapsed_ms / 1000, 0.001), 2)
    summary["messages_per_second"] = summary["requests_per_second"]
    summary["total_send_elapsed_ms"] = round(elapsed_ms, 2)
    return summary


async def warmup_rooms(
    client: httpx.AsyncClient,
    *,
    pairs: list[dp.PairContext],
    sequence_start: int,
) -> int:
    pairs_by_index = {pair.index: pair for pair in pairs}
    sequence = sequence_start
    records: list[dp.SentMessageRecord] = []
    for pair in pairs:
        sequence += 1
        records.append(
            dp.build_send_payload_for_pair(
                pair=pair,
                sequence=sequence,
                benchmark_concurrency=None,
                force_contact_id=True,
            )
        )
    if not records:
        return sequence
    dp.set_api_phase("endpoint_warmup_create_rooms", None)
    dp.log_progress(f"Endpoint benchmark warmup: creating {len(records)} direct rooms...")
    await dp.send_concurrently(client, records=records, concurrency=min(10, len(records)))
    dp.apply_room_ids_to_pairs(records, pairs_by_index)
    failed = [record for record in records if not record.ok]
    if failed:
        raise RuntimeError(f"Endpoint warmup failed for {len(failed)} send-message requests.")
    return sequence


def write_endpoint_reports(report: dict[str, Any]) -> tuple[Path, Path]:
    report_dir = Path(str(dp.CONFIG["REPORT_DIR"]))
    report_dir.mkdir(parents=True, exist_ok=True)
    prefix = dp.safe_report_filename_part(dp.CONFIG["REPORT_FILE_PREFIX"])
    mode = dp.safe_report_filename_part(report.get("service_url_mode"))
    stem = f"{dp.report_timestamp_for_filename()}_{prefix}_{mode}_{dp.TEST_RUN_ID}"
    json_path = report_dir / f"{stem}.json"
    md_path = report_dir / f"{stem}.md"
    report["report_file_stem"] = stem
    report["report_file_timestamp"] = dp.report_timestamp_for_filename()
    json_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    lines = [
        "# Myna Endpoint Gap Benchmark Report",
        "",
        f"**Result:** {'PASS' if report.get('passed') else 'FAIL'}  ",
        f"**Run ID:** `{report.get('run_id')}`  ",
        f"**Cleanup success:** `{report.get('cleanup_success')}`  ",
        "",
        "| endpoint | concurrency | requests | success | failure | client_avg_ms | requests_per_second |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in report.get("benchmark", {}).get("per_level", []):
        lines.append(
            "| {endpoint} | {concurrency} | {requests} | {success} | {failure} | {client} | {rps} |".format(
                endpoint=row.get("endpoint"),
                concurrency=row.get("concurrency"),
                requests=row.get("total_requests"),
                success=row.get("success_count"),
                failure=row.get("failure_count"),
                client=(row.get("latency_ms") or {}).get("avg"),
                rps=row.get("requests_per_second"),
            )
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


async def run() -> int:
    started_at = dp.utc_now_iso()
    levels = endpoint_levels()
    per_level_request_count = requests_per_level()
    configured_pair_count = int(dp.CONFIG["DISTRIBUTED_PAIR_COUNT"] or 0)
    pair_count = max(max(levels), per_level_request_count, configured_pair_count)
    report: dict[str, Any] = {
        "run_id": dp.TEST_RUN_ID,
        "started_at": started_at,
        "service_url_mode": dp.CONFIG["SERVICE_URL_MODE"],
        "identity_base_url": dp.CONFIG["IDENTITY_BASE_URL"],
        "messenger_base_url": dp.CONFIG["MESSENGER_BASE_URL"],
        "traffic_mode": "endpoint_gap_comparison",
        "config": {
            **dp.CONFIG,
            "ENDPOINT_BENCHMARK_LEVELS": levels,
            "ENDPOINT_BENCHMARK_REQUESTS_PER_LEVEL": per_level_request_count,
        },
        "runtime_environment": dp.collect_runtime_environment_snapshot(),
        "passed": False,
    }
    pairs: list[dp.PairContext] = []
    all_summaries: list[dict[str, Any]] = []
    sequence = 0
    benchmark_ok = False
    http_limits = httpx.Limits(
        max_connections=int(dp.CONFIG["HTTP_MAX_CONNECTIONS"]),
        max_keepalive_connections=int(dp.CONFIG["HTTP_MAX_KEEPALIVE_CONNECTIONS"]),
        keepalive_expiry=float(dp.CONFIG["HTTP_KEEPALIVE_EXPIRY_SECONDS"]),
    )
    timeout = httpx.Timeout(
        connect=10.0,
        read=float(dp.CONFIG["REQUEST_TIMEOUT_SECONDS"]),
        write=10.0,
        pool=float(dp.CONFIG["HTTP_POOL_TIMEOUT_SECONDS"]),
    )

    async with httpx.AsyncClient(timeout=timeout, limits=http_limits, follow_redirects=False) as client:
        try:
            report["preflight"] = await dp.preflight_service_urls(client)
            pairs = await dp.setup_pairs(client, pair_count)
            report["setup"] = {
                "pair_count": len(pairs),
                "sender_user_ids_sample": [pair.sender.user_id for pair in pairs[:10]],
                "recipient_user_ids_sample": [pair.recipient.user_id for pair in pairs[:10]],
            }
            if dp.CONFIG["WARMUP_ALL_PAIRS"]:
                sequence = await warmup_rooms(client, pairs=pairs, sequence_start=sequence)

            for endpoint in ENDPOINTS:
                for level in levels:
                    phase = f"endpoint_{endpoint['endpoint']}_concurrency_{level}"
                    dp.set_api_phase(phase, level)
                    dp.log_progress(
                        f"Endpoint={endpoint['endpoint']} concurrency={level}: "
                        f"sending {per_level_request_count} requests..."
                    )
                    started = time.perf_counter()
                    if endpoint["endpoint"] == "send_message":
                        records: list[dp.SentMessageRecord] = []
                        for index in range(per_level_request_count):
                            pair = pairs[index % len(pairs)]
                            sequence += 1
                            records.append(
                                dp.build_send_payload_for_pair(
                                    pair=pair,
                                    sequence=sequence,
                                    benchmark_concurrency=level,
                                    force_contact_id=not bool(pair.room_id),
                                )
                            )
                        dp.assign_benchmark_headers(records, concurrency=level, phase=phase)
                        await dp.send_concurrently(client, records=records, concurrency=level)
                        elapsed_ms = (time.perf_counter() - started) * 1000
                        dp.apply_room_ids_to_pairs(records, {pair.index: pair for pair in pairs})
                        summary = adapt_send_message_summary(
                            dp.summarize_records(records, concurrency=level),
                            concurrency=level,
                            elapsed_ms=elapsed_ms,
                        )
                    else:
                        generic_records: list[EndpointRequestRecord] = []
                        for index in range(per_level_request_count):
                            token = None
                            if endpoint["requires_auth"]:
                                token = pairs[index % len(pairs)].sender.token
                            generic_records.append(
                                EndpointRequestRecord(
                                    endpoint=endpoint["endpoint"],
                                    method=endpoint["method"],
                                    path=endpoint["path"],
                                    sequence=index + 1,
                                    token=token,
                                )
                            )
                        assign_endpoint_headers(generic_records, concurrency=level, phase=phase)
                        await send_endpoint_requests(client, records=generic_records, concurrency=level)
                        elapsed_ms = (time.perf_counter() - started) * 1000
                        summary = summarize_endpoint_records(
                            generic_records,
                            endpoint=endpoint,
                            concurrency=level,
                            elapsed_ms=elapsed_ms,
                        )
                    all_summaries.append(summary)
                    dp.log_progress(
                        f"Endpoint={endpoint['endpoint']} concurrency={level} done: "
                        f"success={summary['success_count']} failure={summary['failure_count']} "
                        f"avg_ms={(summary.get('latency_ms') or {}).get('avg')} "
                        f"req_per_sec={summary.get('requests_per_second')}"
                    )
                    cooldown = float(dp.CONFIG["BENCHMARK_COOLDOWN_SECONDS"])
                    if cooldown > 0:
                        await asyncio.sleep(cooldown)

            benchmark_ok = all(item.get("failure_count", 0) == 0 for item in all_summaries)
            report["benchmark"] = {
                "enabled": True,
                "levels_requested": levels,
                "requests_per_level": per_level_request_count,
                "endpoints": ENDPOINTS,
                "per_level": all_summaries,
            }
            report["summary"] = {
                "endpoint_count": len(ENDPOINTS),
                "level_count": len(levels),
                "total_measured_requests": sum(int(item.get("total_requests") or 0) for item in all_summaries),
                "total_success_count": sum(int(item.get("success_count") or 0) for item in all_summaries),
                "total_failure_count": sum(int(item.get("failure_count") or 0) for item in all_summaries),
            }
        except Exception as exc:
            report["fatal_error"] = repr(exc)
            report["traceback"] = traceback.format_exc()
        finally:
            dp.set_api_phase("cleanup")
            dp.log_progress("Starting endpoint benchmark cleanup...")
            messenger_cleanup = await asyncio.to_thread(dp.cleanup_messenger_with_django, pairs)
            identity_cleanup = await dp.cleanup_identity_users(client, pairs)
            report["cleanup"] = {"messenger": messenger_cleanup, "identity": identity_cleanup}
            report["cleanup_success"] = bool(
                messenger_cleanup.get("success", True)
                and identity_cleanup.get("success", True)
            )
            report["api_timings"] = dp.summarize_api_calls(dp.API_CALL_RECORDS)
            report["finished_at"] = dp.utc_now_iso()
            report["passed"] = bool(benchmark_ok and report["cleanup_success"])
            json_path, md_path = write_endpoint_reports(report)
            dp.log_progress(f"Endpoint reports written: {json_path} and {md_path}")
            print(json.dumps({
                "passed": report.get("passed"),
                "run_id": dp.TEST_RUN_ID,
                "json_report": str(json_path),
                "markdown_report": str(md_path),
                "summary": report.get("summary"),
                "cleanup_success": report.get("cleanup_success"),
                "fatal_error": report.get("fatal_error"),
            }, indent=2, default=str))

    return 0 if report.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))

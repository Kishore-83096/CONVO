#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime
import json
import re
import statistics
from pathlib import Path
from typing import Any


GUNICORN_KV_RE = re.compile(
    r"(?P<key>[A-Za-z_][A-Za-z0-9_-]*)="
    r'(?P<value>"[^"]*"|<[^>]*>|[^\s]+)'
)

SERVER_BOUNDARY_LOG_FIELDS = (
    "view_entry_us",
    "view_exit_us",
    "server_pre_view_us",
    "view_total_us",
    "server_post_view_us",
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
    "post_view_to_response_start_us",
    "response_send_us",
    "asgi_after_response_complete_us",
    "server_boundary_reconciliation_delta_us",
    "server_outside_view_reconciliation_delta_us",
    "instrumentation_warning_count",
    "instrumentation_warnings",
)

PRE_VIEW_LOG_US_FIELDS = (
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

THREAD_LOG_FIELDS = tuple(
    f"thread_{boundary}_{field}"
    for boundary in THREAD_OBSERVATION_BOUNDARIES
    for field in ("id", "name")
)

SERVER_BOUNDARY_LOG_FIELDS = SERVER_BOUNDARY_LOG_FIELDS + THREAD_LOG_FIELDS

PRE_VIEW_STRUCTURAL_LABELS = {
    "pre_view_asgi_to_django_ms": "ASGI wrapper -> Django ASGI entry",
    "pre_view_django_to_middleware_ms": "Django ASGI entry -> first Django middleware",
    "pre_view_middleware_to_drf_dispatch_ms": "first Django middleware -> DRF dispatch",
    "pre_view_django_to_drf_dispatch_ms": "Django ASGI entry -> DRF dispatch",
    "drf_dispatch_pre_initialize_ms": "DRF dispatch -> initialize_request",
    "drf_initialize_request_ms": "DRF initialize_request",
    "drf_dispatch_pre_initial_ms": "initialize_request -> DRF initial",
    "drf_initial_total_ms": "DRF initial total",
    "drf_initial_to_post_ms": "DRF initial exit -> post entry",
    "pre_view_unattributed_ms": "pre-view unattributed",
}

RECONCILIATION_TOLERANCE_MS = 0.5


def unquote_log_value(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        return value[1:-1]
    if len(value) >= 2 and value[0] == "<" and value[-1] == ">":
        return value[1:-1]
    return value


def parse_gunicorn_line(line: str) -> dict[str, str]:
    return {
        match.group("key"): unquote_log_value(match.group("value"))
        for match in GUNICORN_KV_RE.finditer(line)
    }


def number(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_timestamp(value: Any) -> datetime.datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed.astimezone(datetime.timezone.utc)


def iso_from_epoch(value: float | None) -> str | None:
    if value is None:
        return None
    return datetime.datetime.fromtimestamp(value, tz=datetime.timezone.utc).isoformat()


def clamp_tiny_negative(value: float) -> tuple[float, bool]:
    if -2.0 <= value < 0:
        return 0.0, False
    return value, value < -2.0


def microseconds_to_ms(value: Any) -> float | None:
    text = str(value or "").strip()
    if not text or text == "-":
        return None
    try:
        return round(float(text) / 1000.0, 2)
    except (TypeError, ValueError):
        return None


def microseconds_to_ms_raw(value: Any) -> float | None:
    text = str(value or "").strip()
    if not text or text == "-":
        return None
    try:
        return float(text) / 1000.0
    except (TypeError, ValueError):
        return None


def timing_value(timings: dict[str, Any], name: str) -> float:
    return number(timings.get(name))


def derived_unattributed(
    parent: float,
    children: list[float],
) -> tuple[float, bool]:
    return clamp_tiny_negative(parent - sum(children))


def dominant_outside_view_region(
    server_pre_view_ms: Any,
    server_post_view_ms: Any,
    *,
    tolerance_ms: float = RECONCILIATION_TOLERANCE_MS,
) -> str:
    pre = number(server_pre_view_ms, None)
    post = number(server_post_view_ms, None)
    if pre is None or post is None:
        return "unavailable"
    if abs(pre - post) <= tolerance_ms:
        return "tie / approximately equal"
    if pre > post:
        return "server pre-view"
    return "server post-view"


def pre_view_structural_metric_names(row: dict[str, Any]) -> list[str]:
    if (
        row.get("pre_view_django_to_middleware_ms") is not None
        and row.get("pre_view_middleware_to_drf_dispatch_ms") is not None
    ):
        django_region_names = [
            "pre_view_django_to_middleware_ms",
            "pre_view_middleware_to_drf_dispatch_ms",
        ]
    else:
        django_region_names = ["pre_view_django_to_drf_dispatch_ms"]
    return [
        "pre_view_asgi_to_django_ms",
        *django_region_names,
        "drf_dispatch_pre_initialize_ms",
        "drf_initialize_request_ms",
        "drf_dispatch_pre_initial_ms",
        "drf_initial_total_ms",
        "drf_initial_to_post_ms",
        "pre_view_unattributed_ms",
    ]


def dominant_pre_view_region_for_level(item: dict[str, Any]) -> tuple[str, float | None]:
    names = pre_view_structural_metric_names(
        {
            name: metric.get("avg")
            for name, metric in item.items()
            if isinstance(metric, dict)
        }
    )
    candidates: dict[str, float] = {}
    for name in names:
        metric_summary = item.get(name)
        if not isinstance(metric_summary, dict):
            continue
        avg = number(metric_summary.get("avg"), None)
        if avg is not None:
            candidates[PRE_VIEW_STRUCTURAL_LABELS.get(name, name)] = avg
    if not candidates:
        return "unavailable", None
    name = max(candidates, key=candidates.get)
    return name, candidates[name]


def thread_context_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    unique_names: dict[str, list[str]] = {}
    for boundary in THREAD_OBSERVATION_BOUNDARIES:
        key = f"thread_{boundary}_name"
        names = sorted(
            {
                str(row.get(key))
                for row in rows
                if row.get(key) not in {None, "", "-"}
            }
        )
        unique_names[boundary] = names

    changes: dict[str, dict[str, Any]] = {}
    for start, end in [
        ("server_entry", "django_asgi_entry"),
        ("django_asgi_entry", "drf_dispatch_entry"),
        ("drf_dispatch_entry", "drf_initial_entry"),
        ("drf_initial_entry", "drf_initial_exit"),
        ("drf_initial_exit", "post_entry"),
        ("drf_dispatch_entry", "post_entry"),
    ]:
        comparable = 0
        changed = 0
        start_key = f"thread_{start}_id"
        end_key = f"thread_{end}_id"
        for row in rows:
            start_value = row.get(start_key)
            end_value = row.get(end_key)
            if start_value in {None, "", "-"} or end_value in {None, "", "-"}:
                continue
            comparable += 1
            if str(start_value) != str(end_value):
                changed += 1
        changes[f"{start}->{end}"] = {
            "sample_count": comparable,
            "changed_count": changed,
            "changed_percent": (
                round((changed / comparable) * 100, 2)
                if comparable
                else None
            ),
        }

    return {
        "unique_thread_names_by_boundary": unique_names,
        "thread_identity_change": changes,
        "semantics": (
            "Observation only. A thread identity change is not evidence of "
            "executor queue wait or scheduling overhead by itself."
        ),
    }


def material_negative(value: Any) -> bool:
    value_num = number(value, None)
    return value_num is not None and value_num < -RECONCILIATION_TOLERANCE_MS


def reconciliation_failed(value: Any) -> bool:
    value_num = number(value, None)
    return (
        value_num is not None
        and abs(value_num) > RECONCILIATION_TOLERANCE_MS
    )


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return round(ordered[0], 2)
    rank = (len(ordered) - 1) * pct
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    weight = rank - lower
    return round(ordered[lower] * (1 - weight) + ordered[upper] * weight, 2)


def summary(values: list[float]) -> dict[str, float | None]:
    clean = [float(value) for value in values if value is not None]
    if not clean:
        return {
            "min": None,
            "max": None,
            "avg": None,
            "median": None,
            "p50": None,
            "p75": None,
            "p90": None,
            "p95": None,
            "p99": None,
        }
    return {
        "min": round(min(clean), 2),
        "max": round(max(clean), 2),
        "avg": round(sum(clean) / len(clean), 2),
        "median": round(statistics.median(clean), 2),
        "p50": percentile(clean, 0.50),
        "p75": percentile(clean, 0.75),
        "p90": percentile(clean, 0.90),
        "p95": percentile(clean, 0.95),
        "p99": percentile(clean, 0.99),
    }


def timing_spent_summary(values: list[float]) -> dict[str, float | None]:
    item = summary(values)
    item["total"] = round(sum(float(value) for value in values if value is not None), 2) if values else None
    return item


def load_gunicorn_rows(path: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        timestamp = parse_timestamp(line.split(maxsplit=1)[0] if line[:4].isdigit() else None)
        fields = parse_gunicorn_line(line)
        if not fields:
            continue
        request_id = fields.get("req", "").strip()
        if not request_id or request_id == "-":
            continue
        duration_us = fields.get("duration_us", "").strip()
        if not duration_us.isdigit():
            continue
        row = {
            "run_id": fields.get("run", ""),
            "request_id": request_id,
            "phase": fields.get("phase", ""),
            "concurrency": fields.get("concurrency", ""),
            "duration_us": int(duration_us),
            "response_start_us": fields.get("response_start_us", ""),
            "response_complete_us": fields.get("response_complete_us", ""),
            "method": fields.get("method", ""),
            "path": fields.get("path", ""),
            "pid": fields.get("pid", ""),
            "timestamp": timestamp.isoformat() if timestamp else None,
            "timestamp_epoch": timestamp.timestamp() if timestamp else None,
            "raw": line,
        }
        for field in SERVER_BOUNDARY_LOG_FIELDS:
            row[field] = fields.get(field, "")
        rows[request_id] = row
    return rows


def load_server_exception_rows(path: Path | None) -> dict[str, list[dict[str, Any]]]:
    rows: dict[str, list[dict[str, Any]]] = {}
    if path is None or not path.exists():
        return rows
    for lineno, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            rows.setdefault("__malformed__", []).append({"line_number": lineno, "raw": line})
            continue
        request_id = str(item.get("benchmark_request_id") or "").strip()
        if not request_id:
            rows.setdefault("__missing_request_id__", []).append(item)
            continue
        rows.setdefault(request_id, []).append(item)
    return rows


def load_host_stats_summary(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"available": False, "path": str(path)}
    rows: list[dict[str, str]] = []
    with path.open(newline="", encoding="utf-8-sig", errors="replace") as handle:
        rows = list(csv.DictReader(handle))
    samples: list[dict[str, Any]] = []
    for row in rows:
        timestamp = parse_timestamp(row.get("timestamp"))
        if timestamp is None or not row.get("container"):
            continue
        samples.append(
            {
                "timestamp": timestamp.isoformat(),
                "timestamp_epoch": timestamp.timestamp(),
                "container": row.get("container"),
                "cpu_percent": number(row.get("cpu_percent"), None),
                "mem_percent": number(row.get("mem_percent"), None),
            }
        )
    by_container: dict[str, dict[str, Any]] = {}
    for container in sorted({row.get("container", "") for row in rows if row.get("container")}):
        container_rows = [row for row in rows if row.get("container") == container]
        cpu = [number(row.get("cpu_percent"), None) for row in container_rows]
        mem = [number(row.get("mem_percent"), None) for row in container_rows]
        by_container[container] = {
            "sample_count": len(container_rows),
            "cpu_percent": summary([value for value in cpu if value is not None]),
            "mem_percent": summary([value for value in mem if value is not None]),
        }
    return {
        "available": True,
        "path": str(path),
        "sample_count": len(rows),
        "containers": by_container,
        "_samples": samples,
    }


def host_stats_public(host_stats: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in host_stats.items() if not key.startswith("_")}


def summarize_host_samples(samples: list[dict[str, Any]]) -> dict[str, Any]:
    by_container: dict[str, dict[str, Any]] = {}
    for container in sorted({sample.get("container", "") for sample in samples if sample.get("container")}):
        container_samples = [sample for sample in samples if sample.get("container") == container]
        cpu = [sample.get("cpu_percent") for sample in container_samples]
        mem = [sample.get("mem_percent") for sample in container_samples]
        by_container[container] = {
            "sample_count": len(container_samples),
            "cpu_percent": summary([value for value in cpu if value is not None]),
            "mem_percent": summary([value for value in mem if value is not None]),
        }
    return {
        "sample_count": len(samples),
        "containers": by_container,
    }


def host_stats_for_window(host_stats: dict[str, Any], start: float | None, end: float | None) -> dict[str, Any]:
    samples = host_stats.get("_samples") or []
    if not samples or start is None or end is None:
        return {
            "available": False,
            "sample_source": "none",
            "sample_count": 0,
            "containers": {},
            "window_start": iso_from_epoch(start),
            "window_end": iso_from_epoch(end),
        }

    window_samples = [
        sample
        for sample in samples
        if start <= float(sample.get("timestamp_epoch") or 0) <= end
    ]
    sample_source = "window"
    if not window_samples:
        center = (start + end) / 2.0
        nearest_by_container: dict[str, dict[str, Any]] = {}
        for sample in samples:
            container = str(sample.get("container") or "")
            if not container:
                continue
            current = nearest_by_container.get(container)
            current_distance = abs(float(current.get("timestamp_epoch") or 0) - center) if current else None
            distance = abs(float(sample.get("timestamp_epoch") or 0) - center)
            if current is None or current_distance is None or distance < current_distance:
                nearest_by_container[container] = sample
        window_samples = list(nearest_by_container.values())
        sample_source = "nearest_sample"

    result = summarize_host_samples(window_samples)
    result.update(
        {
            "available": bool(window_samples),
            "sample_source": sample_source,
            "window_start": iso_from_epoch(start),
            "window_end": iso_from_epoch(end),
        }
    )
    return result


def iter_level_records(report: dict[str, Any]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for level in report.get("benchmark", {}).get("per_level", []) or []:
        for record in level.get("request_records", []) or []:
            pairs.append((level, record))
    return pairs


def level_identity(level: dict[str, Any]) -> str:
    endpoint = str(level.get("endpoint") or "").strip()
    method = str(level.get("method") or "").strip()
    path = str(level.get("path") or "").strip()
    concurrency = str(level.get("concurrency"))
    return "\x1f".join([endpoint, method, path, concurrency])


def server_exception_summary(exception_rows: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    by_type: dict[str, int] = {}
    by_signature: dict[str, int] = {}
    request_count = 0
    for request_id, rows in exception_rows.items():
        if request_id.startswith("__"):
            continue
        request_count += 1
        for row in rows:
            exc_type = str(row.get("exception_type") or "unknown")
            signature = str(row.get("exception_signature") or row.get("exception_message") or exc_type)
            by_type[exc_type] = by_type.get(exc_type, 0) + 1
            by_signature[signature] = by_signature.get(signature, 0) + 1
    return {
        "available": bool(exception_rows),
        "request_count_with_server_exception": request_count,
        "by_exception_type": by_type,
        "by_exception_signature": by_signature,
        "malformed_count": len(exception_rows.get("__malformed__", [])),
        "missing_request_id_count": len(exception_rows.get("__missing_request_id__", [])),
    }


def attach_server_exceptions(report: dict[str, Any], exception_rows: dict[str, list[dict[str, Any]]]) -> None:
    if not exception_rows:
        return
    for _level, record in iter_level_records(report):
        request_id = str(record.get("benchmark_request_id") or "").strip()
        if not request_id:
            continue
        rows = exception_rows.get(request_id) or []
        if not rows:
            continue
        latest = rows[-1]
        record["server_exception"] = {
            "exception_type": latest.get("exception_type"),
            "exception_message": latest.get("exception_message"),
            "exception_signature": latest.get("exception_signature"),
            "benchmark_phase": latest.get("benchmark_phase"),
            "benchmark_concurrency": latest.get("benchmark_concurrency"),
            "traceback_available": bool(latest.get("traceback")),
            "traceback": latest.get("traceback"),
            "duplicate_record_count": len(rows),
        }
        if not record.get("ok"):
            record["error"] = record["server_exception"]["exception_signature"]


def analyze(report: dict[str, Any], gunicorn_rows: dict[str, dict[str, Any]], host_stats: dict[str, Any], exception_rows: dict[str, list[dict[str, Any]] | Any]) -> dict[str, Any]:
    per_level_records: dict[str, list[dict[str, Any]]] = {}
    per_level_timestamps: dict[str, list[float]] = {}
    unmatched = 0
    matched = 0
    suspicious_negative_count = 0
    reconciliation_warning_count = 0

    for level, record in iter_level_records(report):
        request_id = str(record.get("benchmark_request_id") or "").strip()
        if not request_id:
            unmatched += 1
            continue
        gunicorn = gunicorn_rows.get(request_id)
        if not gunicorn:
            unmatched += 1
            continue

        matched += 1
        server_timing = record.get("server_timing_ms") or {}
        client_latency_ms = number(record.get("latency_ms"))
        server_total_ms = number(gunicorn.get("duration_us")) / 1000.0
        gunicorn_request_ms = server_total_ms
        server_response_start_ms = microseconds_to_ms(
            gunicorn.get("response_start_us")
        )
        server_response_complete_ms = microseconds_to_ms(
            gunicorn.get("response_complete_us")
        )
        correlated_view_total_ms = microseconds_to_ms_raw(
            gunicorn.get("view_total_us")
        )
        view_total_ms = (
            correlated_view_total_ms
            if correlated_view_total_ms is not None
            else timing_value(server_timing, "view_total")
        )
        server_pre_view_ms = microseconds_to_ms_raw(
            gunicorn.get("server_pre_view_us")
        )
        server_post_view_ms = microseconds_to_ms_raw(
            gunicorn.get("server_post_view_us")
        )
        pre_view_metrics_ms = {
            field[:-2] + "ms": microseconds_to_ms_raw(gunicorn.get(field))
            for field in PRE_VIEW_LOG_US_FIELDS
        }
        post_view_to_response_start_ms = microseconds_to_ms_raw(
            gunicorn.get("post_view_to_response_start_us")
        )
        response_send_ms = microseconds_to_ms_raw(
            gunicorn.get("response_send_us")
        )
        asgi_after_response_complete_ms = microseconds_to_ms_raw(
            gunicorn.get("asgi_after_response_complete_us")
        )
        server_boundary_reconciliation_delta_ms = microseconds_to_ms_raw(
            gunicorn.get("server_boundary_reconciliation_delta_us")
        )
        server_outside_view_reconciliation_delta_ms = microseconds_to_ms_raw(
            gunicorn.get("server_outside_view_reconciliation_delta_us")
        )
        boundary_instrumentation_warning_count = int(
            number(gunicorn.get("instrumentation_warning_count"), 0) or 0
        )
        auth_jwt_raw = (
            server_timing.get("auth_jwt_ms")
            if "auth_jwt_ms" in server_timing
            else server_timing.get("auth_jwt")
        )
        auth_jwt_ms = number(auth_jwt_raw, None)
        drf_authentication_unattributed_ms = None
        drf_authentication_total_ms = pre_view_metrics_ms.get(
            "drf_authentication_total_ms"
        )
        if drf_authentication_total_ms is not None and auth_jwt_ms is not None:
            drf_authentication_unattributed_ms = (
                drf_authentication_total_ms - auth_jwt_ms
            )
        service_total_ms = timing_value(server_timing, "service_total")
        recovery_total_ms = timing_value(server_timing, "recovery_total")
        nested_service_boundary_ms = recovery_total_ms or service_total_ms
        view_service_call_ms = timing_value(server_timing, "view_service_call")
        view_service_call_unattributed_ms, view_call_negative = derived_unattributed(
            view_service_call_ms,
            [nested_service_boundary_ms],
        )
        view_child_names = [
            "view_serializer_validation",
            "view_authenticated_user",
            "view_payload_prepare",
            "view_recipient_resolution",
            "view_service_call",
            "view_response_build",
        ]
        view_unattributed_ms, view_negative = derived_unattributed(
            view_total_ms,
            [timing_value(server_timing, name) for name in view_child_names],
        )
        service_child_names = [
            "service_validate_input",
            "service_policy_snapshot",
            "service_existing_room_validation",
            "service_device_lookup",
            "service_room_validation",
            "service_contact_state_upsert",
            "service_reply_lookup",
            "service_message_insert",
            "service_attachment_validation",
            "service_key_envelope_bulk_insert",
            "service_receipt_decision_insert",
            "service_room_update",
            "service_realtime_outbox_persist",
        ]
        service_unattributed_ms, service_negative = derived_unattributed(
            service_total_ms,
            [timing_value(server_timing, name) for name in service_child_names],
        )
        recovery_child_names = [
            "recovery_normalize_input",
            "recovery_policy_snapshot",
            "recovery_bundle_check",
            "recovery_validate_envelopes",
            "recovery_base_send_total",
            "recovery_envelope_bulk_insert",
        ]
        recovery_unattributed_ms, recovery_negative = derived_unattributed(
            recovery_total_ms,
            [timing_value(server_timing, name) for name in recovery_child_names],
        )
        legacy_realtime_enqueue_ms = number(
            server_timing.get("view_realtime_outbox_enqueue")
        )
        durable_outbox_persist_value = server_timing.get(
            "service_realtime_outbox_persist"
        )
        durable_outbox_persist_ms = number(durable_outbox_persist_value)
        has_durable_outbox_persist = durable_outbox_persist_value not in {
            None,
            "",
        }
        realtime_or_outbox_ms = (
            durable_outbox_persist_ms
            if has_durable_outbox_persist
            else legacy_realtime_enqueue_ms
        )
        view_without_realtime_ms = view_total_ms - realtime_or_outbox_ms
        client_outside_server_ms, client_suspicious = clamp_tiny_negative(
            client_latency_ms - server_total_ms
        )
        server_outside_view_ms, gunicorn_suspicious = clamp_tiny_negative(
            server_total_ms - view_total_ms
        )
        if client_suspicious or gunicorn_suspicious:
            suspicious_negative_count += 1
        boundary_warning = (
            boundary_instrumentation_warning_count > 0
            or reconciliation_failed(server_boundary_reconciliation_delta_ms)
            or reconciliation_failed(server_outside_view_reconciliation_delta_ms)
            or reconciliation_failed(
                pre_view_metrics_ms.get(
                    "pre_view_boundary_reconciliation_delta_ms"
                )
            )
            or reconciliation_failed(
                pre_view_metrics_ms.get("drf_initial_reconciliation_delta_ms")
            )
            or material_negative(server_pre_view_ms)
            or material_negative(view_total_ms)
            or material_negative(server_post_view_ms)
            or any(
                material_negative(value)
                for value in pre_view_metrics_ms.values()
            )
            or material_negative(drf_authentication_unattributed_ms)
            or material_negative(post_view_to_response_start_ms)
            or material_negative(response_send_ms)
            or material_negative(asgi_after_response_complete_ms)
        )
        if (
            view_call_negative
            or view_negative
            or service_negative
            or recovery_negative
            or boundary_warning
        ):
            reconciliation_warning_count += 1

        key = level_identity(level)
        timestamp_epoch = gunicorn.get("timestamp_epoch")
        if timestamp_epoch is not None:
            per_level_timestamps.setdefault(key, []).append(float(timestamp_epoch))
        row = {
            "request_id": request_id,
            "ok": bool(record.get("ok")),
            "client_latency_ms": round(client_latency_ms, 2),
            "client_to_response_headers_ms": number(record.get("client_to_response_headers_ms"), None),
            "client_transport_to_response_headers_ms": number(record.get("client_transport_to_response_headers_ms"), None),
            "client_response_body_read_ms": number(record.get("client_response_body_read_ms"), None),
            "client_request_hook_delay_ms": number(record.get("client_request_hook_delay_ms"), None),
            "client_outside_server_ms": round(client_outside_server_ms, 2),
            "client_or_network_gap_ms": round(client_outside_server_ms, 2),
            "server_total_ms": round(server_total_ms, 2),
            "gunicorn_request_ms": round(gunicorn_request_ms, 2),
            "server_response_start_ms": server_response_start_ms,
            "server_response_complete_ms": server_response_complete_ms,
            "server_outside_view_ms": round(server_outside_view_ms, 2),
            "gunicorn_outside_view_ms": round(server_outside_view_ms, 2),
            "server_pre_view_ms": (
                round(server_pre_view_ms, 2)
                if server_pre_view_ms is not None
                else None
            ),
            "server_post_view_ms": (
                round(server_post_view_ms, 2)
                if server_post_view_ms is not None
                else None
            ),
            "post_view_to_response_start_ms": (
                round(post_view_to_response_start_ms, 2)
                if post_view_to_response_start_ms is not None
                else None
            ),
            "response_send_ms": (
                round(response_send_ms, 2)
                if response_send_ms is not None
                else None
            ),
            "asgi_after_response_complete_ms": (
                round(asgi_after_response_complete_ms, 2)
                if asgi_after_response_complete_ms is not None
                else None
            ),
            "server_boundary_reconciliation_delta_ms": (
                round(server_boundary_reconciliation_delta_ms, 4)
                if server_boundary_reconciliation_delta_ms is not None
                else None
            ),
            "server_outside_view_reconciliation_delta_ms": (
                round(server_outside_view_reconciliation_delta_ms, 4)
                if server_outside_view_reconciliation_delta_ms is not None
                else None
            ),
            "view_total_ms": round(view_total_ms, 2),
            "django_total_ms": round(view_total_ms, 2),
            "view_without_realtime_ms": round(view_without_realtime_ms, 2),
            "view_service_call_ms": round(view_service_call_ms, 2),
            "view_service_call_unattributed_ms": round(view_service_call_unattributed_ms, 2),
            "view_unattributed_ms": round(view_unattributed_ms, 2),
            "request_parse_validation_ms": round(timing_value(server_timing, "view_serializer_validation"), 2),
            "recovery_total_ms": round(recovery_total_ms, 2),
            "recovery_unattributed_ms": round(recovery_unattributed_ms, 2),
            "realtime_enqueue_ms": round(realtime_or_outbox_ms, 2),
            "durable_outbox_persist_ms": round(durable_outbox_persist_ms, 2),
            "service_total_ms": round(service_total_ms, 2),
            "service_unattributed_ms": round(service_unattributed_ms, 2),
            "instrumentation_warning": bool(
                view_call_negative
                or view_negative
                or service_negative
                or recovery_negative
                or boundary_warning
            ),
        }
        for metric_name, metric_value in pre_view_metrics_ms.items():
            row[metric_name] = (
                round(metric_value, 4)
                if metric_value is not None
                else None
            )
        if auth_jwt_ms is not None:
            row["auth_jwt_ms"] = round(auth_jwt_ms, 4)
        if drf_authentication_unattributed_ms is not None:
            row["drf_authentication_unattributed_ms"] = round(
                drf_authentication_unattributed_ms,
                4,
            )
        for field in THREAD_LOG_FIELDS:
            row[field] = gunicorn.get(field, "")
        for timing_name, timing in server_timing.items():
            try:
                raw_name = str(timing_name)
                if (
                    raw_name.endswith("_ms")
                    or raw_name.endswith("_count")
                    or raw_name.startswith("db_connection_")
                ):
                    metric_name = raw_name
                else:
                    metric_name = f"{raw_name}_ms"
                if (
                    metric_name == "view_total_ms"
                    and correlated_view_total_ms is not None
                ):
                    continue
                row[metric_name] = round(float(timing), 2)
            except (TypeError, ValueError):
                continue
        per_level_records.setdefault(key, []).append(row)

    per_level = []
    levels = report.get("benchmark", {}).get("per_level", []) or []
    level_keys = [level_identity(level) for level in levels]
    timestamp_ranges: dict[str, dict[str, float]] = {}
    for key, timestamps in per_level_timestamps.items():
        if not timestamps:
            continue
        start = min(timestamps)
        end = max(timestamps)
        timestamp_ranges[key] = {
            "request_start": start,
            "request_end": end,
            "center": (start + end) / 2.0,
        }
    ranged_level_keys = [key for key in level_keys if key in timestamp_ranges]
    host_windows: dict[str, tuple[float | None, float | None]] = {}
    for index, key in enumerate(ranged_level_keys):
        current = timestamp_ranges[key]
        previous_center = timestamp_ranges[ranged_level_keys[index - 1]]["center"] if index > 0 else None
        next_center = timestamp_ranges[ranged_level_keys[index + 1]]["center"] if index + 1 < len(ranged_level_keys) else None
        start = (previous_center + current["center"]) / 2.0 if previous_center is not None else current["request_start"]
        end = (current["center"] + next_center) / 2.0 if next_center is not None else current["request_end"]
        host_windows[key] = (
            min(start, current["request_start"]),
            max(end, current["request_end"]),
        )

    for level in levels:
        key = level_identity(level)
        rows = per_level_records.get(key, [])
        total_requests = level.get("total_messages", level.get("total_requests", 0))
        host_window_start, host_window_end = host_windows.get(key, (None, None))
        item: dict[str, Any] = {
            "endpoint": level.get("endpoint"),
            "method": level.get("method"),
            "path": level.get("path"),
            "concurrency": level.get("concurrency"),
            "total_messages": total_requests,
            "total_requests": total_requests,
            "success_count": level.get("success_count"),
            "failure_count": level.get("failure_count"),
            "messages_per_second": level.get("messages_per_second"),
            "messages_per_second_semantics": level.get("messages_per_second_semantics", "successful_messages_per_second"),
            "offered_requests_per_second": level.get("offered_requests_per_second"),
            "completed_requests_per_second": level.get("completed_requests_per_second"),
            "successful_messages_per_second": level.get("successful_messages_per_second", level.get("messages_per_second")),
            "failed_requests_per_second": level.get("failed_requests_per_second"),
            "requests_per_second": level.get("completed_requests_per_second", level.get("requests_per_second", level.get("messages_per_second"))),
            "matched_request_count": len(rows),
            "unmatched_request_count": max(0, int(total_requests or 0) - len(rows)),
            "host_docker_stats": host_stats_for_window(host_stats, host_window_start, host_window_end),
            "request_gap_records": rows,
        }
        numeric_metrics = sorted(
            {
                name
                for row in rows
                for name, value in row.items()
                if name not in {"request_id", "ok", "instrumentation_warning"}
                and isinstance(value, (int, float))
                and value is not None
            }
        )
        for metric in numeric_metrics:
            item[metric] = summary(
                [
                    row.get(metric)
                    for row in rows
                    if isinstance(row.get(metric), (int, float))
                ]
            )
        item["dominant_outside_view_region"] = dominant_outside_view_region(
            item.get("server_pre_view_ms", {}).get("avg")
            if isinstance(item.get("server_pre_view_ms"), dict)
            else None,
            item.get("server_post_view_ms", {}).get("avg")
            if isinstance(item.get("server_post_view_ms"), dict)
            else None,
        )
        dominant_pre_view_region, dominant_pre_view_avg_ms = (
            dominant_pre_view_region_for_level(item)
        )
        item["dominant_pre_view_region"] = dominant_pre_view_region
        item["dominant_pre_view_region_avg_ms"] = dominant_pre_view_avg_ms
        item["dominant_pre_view_region_percent_of_pre_view"] = (
            round(
                (dominant_pre_view_avg_ms / item["server_pre_view_ms"]["avg"]) * 100,
                2,
            )
            if (
                dominant_pre_view_avg_ms is not None
                and isinstance(item.get("server_pre_view_ms"), dict)
                and item["server_pre_view_ms"].get("avg")
            )
            else None
        )
        item["dominant_pre_view_region_percent_of_client"] = (
            round(
                (dominant_pre_view_avg_ms / item["client_latency_ms"]["avg"]) * 100,
                2,
            )
            if (
                dominant_pre_view_avg_ms is not None
                and isinstance(item.get("client_latency_ms"), dict)
                and item["client_latency_ms"].get("avg")
            )
            else None
        )
        item["thread_context_observations"] = thread_context_summary(rows)
        item["overall_client_request_time_ms"] = timing_spent_summary(
            [row["client_latency_ms"] for row in rows]
        )
        item["main_django_logic_time_ms"] = timing_spent_summary(
            [row["view_total_ms"] for row in rows]
        )
        item["server_total_time_ms"] = timing_spent_summary(
            [row["server_total_ms"] for row in rows]
        )
        item["instrumentation_warning_count"] = sum(
            1
            for row in rows
            if row.get("instrumentation_warning")
        )
        failed_rows = [row for row in rows if not row.get("ok")]
        item["failed_client_latency_ms"] = summary([row["client_latency_ms"] for row in failed_rows])
        item["failed_gunicorn_request_ms"] = summary([row["gunicorn_request_ms"] for row in failed_rows])
        per_level.append(item)

    total = matched + unmatched
    unmatched_percent = round((unmatched / total) * 100, 2) if total else 0.0
    return {
        "method": "client_latency_minus_server_asgi_wrapper_minus_view_timing",
        "metric_semantics": {
            "server_total_ms": (
                "Benchmark ASGI wrapper duration. This replaces the old "
                "gunicorn_request_ms wording for ASGI runs; it is not pure "
                "Gunicorn CPU time."
            ),
            "client_or_network_gap_ms": (
                "Legacy alias of client_outside_server_ms. "
                "Broad client/server admission and transport delta: client "
                "observed request time minus server ASGI-wrapper time. "
                "It may include benchmark scheduling, HTTPX pool wait, "
                "connection setup, socket queues, Docker networking, server "
                "accept/admission wait before request timing, response "
                "transport, and client response scheduling."
            ),
            "gunicorn_outside_view_ms": (
                "Legacy alias of server_outside_view_ms. It is server "
                "ASGI-wrapper time minus SendDirectMessageView.post time, "
                "not a pure Gunicorn interval. This aggregate combines "
                "server pre-view and post-view latency; use "
                "server_pre_view_ms and server_post_view_ms for root-cause "
                "investigation."
            ),
            "server_pre_view_ms": (
                "Measured time from benchmark ASGI wrapper entry to "
                "SendDirectMessageView.post entry, correlated by request-local "
                "contextvars."
            ),
            "server_post_view_ms": (
                "Measured time from SendDirectMessageView.post exit to "
                "benchmark ASGI wrapper return, correlated by request-local "
                "contextvars."
            ),
            "post_view_to_response_start_ms": (
                "Measured time from view exit to the first ASGI "
                "http.response.start message observed by the benchmark "
                "wrapper."
            ),
            "response_send_ms": (
                "Measured interval from first ASGI http.response.start to "
                "final ASGI http.response.body inside the wrapper. It is not "
                "network latency."
            ),
            "asgi_after_response_complete_ms": (
                "Measured time from final ASGI http.response.body to benchmark "
                "ASGI wrapper return. No cleanup sub-layer is inferred."
            ),
            "pre_view_django_to_drf_dispatch_ms": (
                "Observation from Django ASGI app entry to DRF dispatch entry. "
                "When first-middleware timing is available, the structural "
                "pre-view timeline uses the smaller Django-to-middleware and "
                "middleware-to-DRF regions instead of this overlapping span."
            ),
            "realtime_enqueue_ms": (
                "Legacy column. For new reports this is durable database "
                "outbox persistence from service_realtime_outbox_persist, "
                "not Redis publication."
            ),
        },
        "matched_request_count": matched,
        "unmatched_request_count": unmatched,
        "unmatched_percent": unmatched_percent,
        "suspicious_negative_gap_count": suspicious_negative_count,
        "reconciliation_warning_count": reconciliation_warning_count,
        "gunicorn_access_log_path": None,
        "server_exception_summary": server_exception_summary(exception_rows),
        "host_docker_stats": host_stats_public(host_stats),
        "per_level": per_level,
    }


def bottleneck_for_level(item: dict[str, Any]) -> str:
    metrics = {
        "client/admission/transport gap": number(item.get("client_or_network_gap_ms", {}).get("avg")),
        "server pre-view": number(item.get("server_pre_view_ms", {}).get("avg")),
        "server post-view": number(item.get("server_post_view_ms", {}).get("avg")),
        "gunicorn/asgi/django outside-view": number(item.get("gunicorn_outside_view_ms", {}).get("avg")),
        "messenger view without realtime": number(item.get("view_without_realtime_ms", {}).get("avg")),
        "durable outbox persistence": number(item.get("realtime_enqueue_ms", {}).get("avg")),
        "service/database": number(item.get("service_total_ms", {}).get("avg")),
    }
    return max(metrics, key=metrics.get)


def write_markdown(report: dict[str, Any], markdown_path: Path) -> None:
    analysis = report.get("request_gap_analysis") or {}
    rows = analysis.get("per_level") or []
    has_endpoint_rows = any(row.get("endpoint") for row in rows)
    dominant = "unknown"
    if rows:
        totals: dict[str, float] = {}
        for row in rows:
            name = bottleneck_for_level(row)
            totals[name] = totals.get(name, 0.0) + 1
        dominant = max(totals, key=totals.get)

    lines = [
        "# Myna Request Gap Analysis",
        "",
        "## Executive Summary",
        "",
        f"- Matched requests: `{analysis.get('matched_request_count', 0)}`",
        f"- Unmatched requests: `{analysis.get('unmatched_request_count', 0)}` (`{analysis.get('unmatched_percent', 0)}`%)",
        f"- Most common top bottleneck: `{dominant}`",
        "",
        "## Per-Concurrency Timing",
        "",
    ]
    if has_endpoint_rows:
        lines.extend(
            [
                "| endpoint | method | path | concurrency | requests | success | overall_req_total_ms | main_django_total_ms | client_avg_ms | gunicorn_avg_ms | server_pre_view_avg_ms | view_total_avg_ms | server_post_view_avg_ms | gunicorn_outside_view_avg_ms | dominant_outside_view_region | client_admission_transport_gap_avg_ms | service_total_avg_ms | requests_per_second |",
                "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: |",
            ]
        )
    else:
        lines.extend(
            [
                "| concurrency | messages | success | overall_req_total_ms | main_django_total_ms | client_avg_ms | gunicorn_avg_ms | server_pre_view_avg_ms | view_total_avg_ms | server_post_view_avg_ms | gunicorn_outside_view_avg_ms | dominant_outside_view_region | client_admission_transport_gap_avg_ms | view_without_outbox_avg_ms | durable_outbox_persist_avg_ms | service_total_avg_ms | messages_per_second |",
                "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
    for row in rows:
        get_avg = lambda name: row.get(name, {}).get("avg")
        get_total = lambda name: row.get(name, {}).get("total")
        if has_endpoint_rows:
            lines.append(
                "| {endpoint} | {method} | {path} | {concurrency} | {requests} | {success} | {overall_total} | {main_total} | {client} | {gunicorn} | {pre_view} | {view} | {post_view} | {outside} | {dominant_outside} | {client_gap} | {service} | {rps} |".format(
                    endpoint=row.get("endpoint") or "",
                    method=row.get("method") or "",
                    path=row.get("path") or "",
                    concurrency=row.get("concurrency"),
                    requests=row.get("total_requests"),
                    success=row.get("success_count"),
                    overall_total=get_total("overall_client_request_time_ms"),
                    main_total=get_total("main_django_logic_time_ms"),
                    client=get_avg("client_latency_ms"),
                    gunicorn=get_avg("gunicorn_request_ms"),
                    pre_view=get_avg("server_pre_view_ms"),
                    post_view=get_avg("server_post_view_ms"),
                    client_gap=get_avg("client_or_network_gap_ms"),
                    outside=get_avg("gunicorn_outside_view_ms"),
                    dominant_outside=row.get("dominant_outside_view_region"),
                    view=get_avg("view_total_ms"),
                    service=get_avg("service_total_ms"),
                    rps=row.get("requests_per_second"),
                )
            )
        else:
            lines.append(
                "| {concurrency} | {messages} | {success} | {overall_total} | {main_total} | {client} | {gunicorn} | {pre_view} | {view} | {post_view} | {outside} | {dominant_outside} | {client_gap} | {view_no_rt} | {rt} | {service} | {mps} |".format(
                    concurrency=row.get("concurrency"),
                    messages=row.get("total_messages"),
                    success=row.get("success_count"),
                    overall_total=get_total("overall_client_request_time_ms"),
                    main_total=get_total("main_django_logic_time_ms"),
                    client=get_avg("client_latency_ms"),
                    gunicorn=get_avg("gunicorn_request_ms"),
                    pre_view=get_avg("server_pre_view_ms"),
                    post_view=get_avg("server_post_view_ms"),
                    client_gap=get_avg("client_or_network_gap_ms"),
                    outside=get_avg("gunicorn_outside_view_ms"),
                    dominant_outside=row.get("dominant_outside_view_region"),
                    view=get_avg("view_total_ms"),
                    view_no_rt=get_avg("view_without_realtime_ms"),
                    rt=get_avg("realtime_enqueue_ms"),
                    service=get_avg("service_total_ms"),
                    mps=row.get("messages_per_second"),
                )
            )

    lines.extend(["", "## Top Bottleneck Per Level", ""])
    for row in rows:
        label = f"{row.get('endpoint')} concurrency `{row.get('concurrency')}`" if row.get("endpoint") else f"concurrency `{row.get('concurrency')}`"
        lines.append(f"- {label}: `{bottleneck_for_level(row)}`")

    lines.extend(
        [
            "",
            "## Metric Semantics",
            "",
            "- `client_admission_transport_gap_avg_ms`: broad client/server delta, not pure network latency.",
            "- `durable_outbox_persist_avg_ms`: database outbox row persistence in the direct-send transaction, not Redis publication.",
        ]
    )

    lines.extend(["", "## Docker Stats Summary", ""])
    host_stats = analysis.get("host_docker_stats") or {}
    if host_stats.get("available"):
        for container, stats in (host_stats.get("containers") or {}).items():
            lines.append(
                f"- `{container}`: samples `{stats.get('sample_count')}`, "
                f"cpu avg `{stats.get('cpu_percent', {}).get('avg')}`, "
                f"mem avg `{stats.get('mem_percent', {}).get('avg')}`"
            )
    else:
        lines.append("- Host-side Docker stats CSV was not available.")

    exception_summary = analysis.get("server_exception_summary") or {}
    lines.extend(["", "## Server Exception Diagnostics", ""])
    if exception_summary.get("available"):
        lines.append(f"- Requests with server exceptions: `{exception_summary.get('request_count_with_server_exception')}`")
        lines.append(f"- By exception type: `{json.dumps(exception_summary.get('by_exception_type', {}), sort_keys=True)}`")
        lines.append(f"- By exception signature: `{json.dumps(exception_summary.get('by_exception_signature', {}), sort_keys=True)}`")
    else:
        lines.append("- No benchmark ASGI exception diagnostics were available.")

    lines.extend(
        [
            "",
            "## Warnings",
            "",
            f"- Unmatched request percent: `{analysis.get('unmatched_percent', 0)}`%",
            f"- Suspicious negative gap count: `{analysis.get('suspicious_negative_gap_count', 0)}`",
            "",
            "## Next Recommended Optimization Target",
            "",
            f"Start with `{dominant}` based on the largest average gap category across levels.",
            "",
        ]
    )
    markdown_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-report", required=True)
    parser.add_argument("--gunicorn-log", required=True)
    parser.add_argument("--server-exception-log", default="")
    parser.add_argument("--docker-stats-csv", required=True)
    parser.add_argument("--runtime-config-json", default="")
    parser.add_argument("--output-json", default="")
    parser.add_argument("--output-md", default="")
    parser.add_argument("--skip-md", action="store_true")
    args = parser.parse_args()

    json_path = Path(args.json_report)
    output_json = Path(args.output_json) if args.output_json else json_path
    markdown_path = None if args.skip_md else (
        Path(args.output_md)
        if args.output_md
        else output_json.with_name(output_json.stem + "_request_gap_analysis.md")
    )
    gunicorn_path = Path(args.gunicorn_log)
    exception_path = Path(args.server_exception_log) if args.server_exception_log else None
    docker_stats_path = Path(args.docker_stats_csv)
    runtime_config_path = Path(args.runtime_config_json) if args.runtime_config_json else None

    report = json.loads(json_path.read_text(encoding="utf-8-sig"))
    gunicorn_rows = load_gunicorn_rows(gunicorn_path)
    exception_rows = load_server_exception_rows(exception_path)
    attach_server_exceptions(report, exception_rows)
    host_stats = load_host_stats_summary(docker_stats_path)
    analysis = analyze(report, gunicorn_rows, host_stats, exception_rows)
    analysis["gunicorn_access_log_path"] = str(gunicorn_path)
    analysis["server_exception_log_path"] = str(exception_path) if exception_path else None
    report["request_gap_analysis"] = analysis
    report["server_exception_log_path"] = str(exception_path) if exception_path else None
    if runtime_config_path and runtime_config_path.exists():
        runtime_config = json.loads(runtime_config_path.read_text(encoding="utf-8-sig"))
        report.setdefault("effective_runtime_config", {})["services"] = runtime_config
        report["service_runtime_config_path"] = str(runtime_config_path)
    report["host_docker_stats_csv_path"] = str(docker_stats_path)
    report["request_gap_analysis_markdown_path"] = str(markdown_path) if markdown_path else None
    output_json.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    if markdown_path:
        write_markdown(report, markdown_path)

    print(json.dumps({
        "json_report": str(output_json),
        "markdown_report": str(markdown_path) if markdown_path else None,
        "gunicorn_access_log": str(gunicorn_path),
        "server_exception_log": str(exception_path) if exception_path else None,
        "docker_stats_csv": str(docker_stats_path),
        "server_exception_summary": analysis.get("server_exception_summary"),
        "matched_request_count": analysis["matched_request_count"],
        "unmatched_request_count": analysis["unmatched_request_count"],
        "unmatched_percent": analysis["unmatched_percent"],
    }, indent=2))
    return 0 if analysis["unmatched_percent"] < 50 else 2


if __name__ == "__main__":
    raise SystemExit(main())

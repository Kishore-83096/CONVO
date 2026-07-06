#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any

try:
    from benchmark_metric_definitions import METRIC_DEFINITIONS
except ModuleNotFoundError:  # pragma: no cover - direct import by path in tests
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from benchmark_metric_definitions import METRIC_DEFINITIONS


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def num(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def fmt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    value_num = num(value)
    if value_num is not None:
        return f"{value_num:.2f}".rstrip("0").rstrip(".")
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True)
    return str(value).replace("|", "\\|").replace("\n", " ")


def metric(row: dict[str, Any] | None, name: str, field: str = "avg") -> Any:
    if not row:
        return None
    value = row.get(name)
    if isinstance(value, dict):
        return value.get(field)
    return None


def markdown_table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    return [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
        *["| " + " | ".join(fmt(cell) for cell in row) + " |" for row in rows],
    ]


def metric_definition_rows() -> list[list[Any]]:
    return [
        [
            definition.name,
            definition.metric_type,
            definition.unit,
            definition.start_boundary,
            definition.end_boundary,
            definition.parent,
            definition.included_in_http_latency,
            definition.notes,
        ]
        for definition in METRIC_DEFINITIONS
    ]


def metric_definitions_section() -> list[str]:
    return [
        "## Metric Definitions",
        "",
        *markdown_table(
            [
                "metric",
                "type",
                "unit",
                "start boundary",
                "end boundary",
                "parent",
                "in HTTP latency",
                "notes",
            ],
            metric_definition_rows(),
        ),
    ]


def first_present(row: dict[str, Any] | None, names: list[str], field: str = "avg") -> Any:
    for name in names:
        value = metric(row, name, field)
        if value is not None:
            return value
    return None


def percent_of(value: Any, total: Any) -> float | None:
    value_num = num(value)
    total_num = num(total)
    if value_num is None or total_num in (None, 0):
        return None
    return round((value_num / total_num) * 100, 2)


def dominant_outside_view_region(
    pre_view_ms: Any,
    post_view_ms: Any,
    *,
    tolerance_ms: float = 0.5,
) -> str:
    pre = num(pre_view_ms)
    post = num(post_view_ms)
    if pre is None or post is None:
        return "unavailable"
    if abs(pre - post) <= tolerance_ms:
        return "tie / approximately equal"
    return "server pre-view" if pre > post else "server post-view"


def dominant_outside_view_region_for_row(row: dict[str, Any] | None) -> str:
    if not row:
        return "unavailable"
    existing = row.get("dominant_outside_view_region")
    if existing:
        return str(existing)
    return dominant_outside_view_region(
        metric(row, "server_pre_view_ms", "avg"),
        metric(row, "server_post_view_ms", "avg"),
    )


def gap_for_level(report: dict[str, Any], concurrency: int | None) -> dict[str, Any] | None:
    if concurrency is None:
        return None
    return rows_by_concurrency(gap_rows(report)).get(concurrency)


def largest_latency_region(row: dict[str, Any] | None) -> str:
    if not row:
        return ""
    pre_view = metric(row, "server_pre_view_ms", "avg")
    post_view = metric(row, "server_post_view_ms", "avg")
    candidates = {
        "client outside server": metric(row, "client_outside_server_ms", "avg"),
        "request parse and validation": metric(row, "request_parse_validation_ms", "avg"),
        "view recipient resolution": metric(row, "view_recipient_resolution_ms", "avg"),
        "view service call": metric(row, "view_service_call_ms", "avg"),
        "recovery service": metric(row, "recovery_total_ms", "avg"),
        "direct send service": metric(row, "service_total_ms", "avg"),
        "outbox persistence": metric(row, "service_realtime_outbox_persist_ms", "avg") or metric(row, "durable_outbox_persist_ms", "avg"),
        "view unattributed": metric(row, "view_unattributed_ms", "avg"),
        "recovery unattributed": metric(row, "recovery_unattributed_ms", "avg"),
        "service unattributed": metric(row, "service_unattributed_ms", "avg"),
    }
    if pre_view is not None or post_view is not None:
        candidates["server pre-view"] = pre_view
        candidates["server post-view"] = post_view
    else:
        candidates["server outside view"] = metric(
            row,
            "server_outside_view_ms",
            "avg",
        )
    clean = {
        name: float(value)
        for name, value in candidates.items()
        if value is not None
    }
    return max(clean, key=clean.get) if clean else ""


def largest_latency_stage(row: dict[str, Any] | None) -> str:
    return largest_latency_region(row)


def largest_unattributed_region(row: dict[str, Any] | None) -> tuple[str, Any, Any]:
    if not row:
        return "", None, None
    client_total = metric(row, "client_latency_ms", "avg")
    pre_view = metric(row, "server_pre_view_ms", "avg")
    post_view = metric(row, "server_post_view_ms", "avg")
    candidates = {
        "client outside server": metric(row, "client_outside_server_ms", "avg"),
        "view unattributed": metric(row, "view_unattributed_ms", "avg"),
        "service unattributed": metric(row, "service_unattributed_ms", "avg"),
        "recovery unattributed": metric(row, "recovery_unattributed_ms", "avg"),
    }
    if pre_view is not None or post_view is not None:
        candidates["server pre-view"] = pre_view
        candidates["server post-view"] = post_view
    else:
        candidates["server outside view"] = metric(
            row,
            "server_outside_view_ms",
            "avg",
        )
    clean = {
        name: value
        for name, value in candidates.items()
        if value is not None
    }
    if not clean:
        return "", None, None
    name = max(clean, key=lambda key: float(clean[key]))
    value = clean[name]
    return name, value, percent_of(value, client_total)


def target_summary_rows(report: dict[str, Any], concurrency: int | None) -> list[list[Any]]:
    level = find_level(report, concurrency)
    gap = gap_for_level(report, concurrency)
    source = gap or level or {}
    largest_unattributed_name, largest_unattributed_ms, largest_unattributed_pct = (
        largest_unattributed_region(source)
    )
    client_avg = metric(source, "client_latency_ms", "avg") or metric(source, "latency_ms", "avg")
    server_avg = metric(source, "server_total_ms", "avg") or metric(source, "gunicorn_request_ms", "avg")
    pre_view_avg = metric(source, "server_pre_view_ms", "avg")
    post_view_avg = metric(source, "server_post_view_ms", "avg")
    outside_view_avg = metric(source, "server_outside_view_ms", "avg") or metric(source, "gunicorn_outside_view_ms", "avg")
    dominant_pre_view_name, dominant_pre_view_avg, dominant_pre_view_pct, dominant_pre_view_client_pct = (
        dominant_pre_view_region_for_row(source)
    )
    pre_view_unattributed_avg = metric(source, "pre_view_unattributed_ms", "avg")
    return [
        ["target_concurrency", concurrency],
        ["client_p50_ms", first_present(source, ["client_latency_ms", "latency_ms"], "p50") or first_present(source, ["client_latency_ms", "latency_ms"], "median")],
        ["client_p95_ms", first_present(source, ["client_latency_ms", "latency_ms"], "p95")],
        ["client_p99_ms", first_present(source, ["client_latency_ms", "latency_ms"], "p99")],
        ["throughput_msg_per_sec", (level or {}).get("successful_messages_per_second", (level or {}).get("messages_per_second"))],
        ["server_avg_ms", server_avg],
        ["server_pre_view_avg_ms", pre_view_avg],
        ["server_pre_view_percent_of_server", percent_of(pre_view_avg, server_avg)],
        ["server_pre_view_percent_of_client", percent_of(pre_view_avg, client_avg)],
        ["view_avg_ms", metric(source, "view_total_ms", "avg")],
        ["server_post_view_avg_ms", post_view_avg],
        ["server_post_view_percent_of_server", percent_of(post_view_avg, server_avg)],
        ["server_post_view_percent_of_client", percent_of(post_view_avg, client_avg)],
        ["server_outside_view_avg_ms", outside_view_avg],
        ["server_outside_view_percent_of_client", percent_of(outside_view_avg, client_avg)],
        ["dominant_outside_view_region", dominant_outside_view_region_for_row(source)],
        ["dominant_pre_view_region", dominant_pre_view_name],
        ["dominant_pre_view_region_avg_ms", dominant_pre_view_avg],
        ["dominant_pre_view_region_percent_of_pre_view", dominant_pre_view_pct],
        ["dominant_pre_view_region_percent_of_client", dominant_pre_view_client_pct],
        ["pre_view_unattributed_avg_ms", pre_view_unattributed_avg],
        ["pre_view_unattributed_percent_of_pre_view", percent_of(pre_view_unattributed_avg, pre_view_avg)],
        ["drf_initial_avg_ms", metric(source, "drf_initial_total_ms", "avg")],
        ["service_avg_ms", metric(source, "service_total_ms", "avg")],
        ["db_query_total_avg_ms", metric(source, "db_query_total_ms", "avg")],
        ["db_connection_ensure_avg_ms", metric(source, "db_connection_ensure_ms", "avg")],
        ["db_connection_was_present_before_ensure_avg", metric(source, "db_connection_was_present_before_ensure", "avg")],
        ["largest_latency_region", largest_latency_region(source)],
        ["largest_unattributed_region", largest_unattributed_name],
        ["largest_unattributed_avg_ms", largest_unattributed_ms],
        ["largest_unattributed_percent_of_client_avg", largest_unattributed_pct],
        ["instrumentation_warning_count", (source or {}).get("instrumentation_warning_count")],
    ]


def latency_decomposition_rows(row: dict[str, Any] | None) -> list[list[Any]]:
    if not row:
        return []
    client_avg = metric(row, "client_latency_ms", "avg")
    server_avg = metric(row, "server_total_ms", "avg") or metric(row, "gunicorn_request_ms", "avg")
    server_pre_view_avg = metric(row, "server_pre_view_ms", "avg")
    view_avg = metric(row, "view_total_ms", "avg")
    server_post_view_avg = metric(row, "server_post_view_ms", "avg")
    view_service_call_avg = metric(row, "view_service_call_ms", "avg")
    recovery_avg = metric(row, "recovery_total_ms", "avg")
    recovery_base_send_avg = metric(row, "recovery_base_send_total_ms", "avg")
    service_avg = metric(row, "service_total_ms", "avg")
    service_parent_avg = recovery_base_send_avg or view_service_call_avg
    items = [
        ("CLIENT TOTAL", "client_latency_ms", client_avg, None, client_avg),
        ("client outside server", "client_outside_server_ms", metric(row, "client_outside_server_ms", "avg"), client_avg, client_avg),
        ("SERVER TOTAL", "server_total_ms", server_avg, client_avg, client_avg),
        ("server pre-view", "server_pre_view_ms", server_pre_view_avg, server_avg, client_avg),
        ("VIEW TOTAL", "view_total_ms", view_avg, server_avg, client_avg),
        ("server post-view", "server_post_view_ms", server_post_view_avg, server_avg, client_avg),
        ("request parse and validation", "request_parse_validation_ms", metric(row, "request_parse_validation_ms", "avg"), view_avg, client_avg),
        ("view authenticated user", "view_authenticated_user_ms", metric(row, "view_authenticated_user_ms", "avg"), view_avg, client_avg),
        ("view payload prepare", "view_payload_prepare_ms", metric(row, "view_payload_prepare_ms", "avg"), view_avg, client_avg),
        ("view recipient resolution", "view_recipient_resolution_ms", metric(row, "view_recipient_resolution_ms", "avg"), view_avg, client_avg),
        ("view service call", "view_service_call_ms", view_service_call_avg, view_avg, client_avg),
        ("view response build", "view_response_build_ms", metric(row, "view_response_build_ms", "avg"), view_avg, client_avg),
        ("view unattributed", "view_unattributed_ms", metric(row, "view_unattributed_ms", "avg"), view_avg, client_avg),
        ("RECOVERY TOTAL", "recovery_total_ms", recovery_avg, view_service_call_avg, client_avg),
        ("recovery normalize input", "recovery_normalize_input_ms", metric(row, "recovery_normalize_input_ms", "avg"), recovery_avg, client_avg),
        ("recovery policy snapshot", "recovery_policy_snapshot_ms", metric(row, "recovery_policy_snapshot_ms", "avg"), recovery_avg, client_avg),
        ("recovery bundle check", "recovery_bundle_check_ms", metric(row, "recovery_bundle_check_ms", "avg"), recovery_avg, client_avg),
        ("recovery validate envelopes", "recovery_validate_envelopes_ms", metric(row, "recovery_validate_envelopes_ms", "avg"), recovery_avg, client_avg),
        ("recovery base direct send", "recovery_base_send_total_ms", recovery_base_send_avg, recovery_avg, client_avg),
        ("recovery envelope bulk insert", "recovery_envelope_bulk_insert_ms", metric(row, "recovery_envelope_bulk_insert_ms", "avg"), recovery_avg, client_avg),
        ("recovery unattributed", "recovery_unattributed_ms", metric(row, "recovery_unattributed_ms", "avg"), recovery_avg, client_avg),
        ("SERVICE TOTAL", "service_total_ms", service_avg, service_parent_avg, client_avg),
        ("service input validation", "service_validate_input_ms", metric(row, "service_validate_input_ms", "avg"), service_avg, client_avg),
        ("service policy snapshot", "service_policy_snapshot_ms", metric(row, "service_policy_snapshot_ms", "avg"), service_avg, client_avg),
        ("service existing-room validation", "service_existing_room_validation_ms", metric(row, "service_existing_room_validation_ms", "avg"), service_avg, client_avg),
        ("service device lookup", "service_device_lookup_ms", metric(row, "service_device_lookup_ms", "avg"), service_avg, client_avg),
        ("service room validation", "service_room_validation_ms", metric(row, "service_room_validation_ms", "avg"), service_avg, client_avg),
        ("service contact-state upsert", "service_contact_state_upsert_ms", metric(row, "service_contact_state_upsert_ms", "avg"), service_avg, client_avg),
        ("service reply lookup", "service_reply_lookup_ms", metric(row, "service_reply_lookup_ms", "avg"), service_avg, client_avg),
        ("service message insert", "service_message_insert_ms", metric(row, "service_message_insert_ms", "avg"), service_avg, client_avg),
        ("service attachment validation", "service_attachment_validation_ms", metric(row, "service_attachment_validation_ms", "avg"), service_avg, client_avg),
        ("service key-envelope bulk insert", "service_key_envelope_bulk_insert_ms", metric(row, "service_key_envelope_bulk_insert_ms", "avg"), service_avg, client_avg),
        ("service receipt-decision insert", "service_receipt_decision_insert_ms", metric(row, "service_receipt_decision_insert_ms", "avg"), service_avg, client_avg),
        ("service room update", "service_room_update_ms", metric(row, "service_room_update_ms", "avg"), service_avg, client_avg),
        ("outbox persistence", "service_realtime_outbox_persist_ms", metric(row, "service_realtime_outbox_persist_ms", "avg") or metric(row, "durable_outbox_persist_ms", "avg"), service_avg, client_avg),
        ("service unattributed", "service_unattributed_ms", metric(row, "service_unattributed_ms", "avg"), service_avg, client_avg),
    ]
    return [
        [
            label,
            metric_name,
            avg,
            percent_of(avg, parent),
            percent_of(avg, client),
            metric(row, metric_name, "p50") or metric(row, metric_name, "median"),
            metric(row, metric_name, "p95"),
            metric(row, metric_name, "p99"),
        ]
        for label, metric_name, avg, parent, client in items
        if avg is not None
    ]


def server_boundary_decomposition_rows(row: dict[str, Any] | None) -> list[list[Any]]:
    if not row:
        return []
    server_avg = metric(row, "server_total_ms", "avg") or metric(row, "gunicorn_request_ms", "avg")
    client_avg = metric(row, "client_latency_ms", "avg")
    regions = [
        ("server pre-view", "server_pre_view_ms"),
        ("view", "view_total_ms"),
        ("server post-view", "server_post_view_ms"),
    ]
    rows = []
    for label, metric_name in regions:
        avg = metric(row, metric_name, "avg")
        if avg is None:
            continue
        rows.append(
            [
                label,
                avg,
                metric(row, metric_name, "p50") or metric(row, metric_name, "median"),
                metric(row, metric_name, "p75"),
                metric(row, metric_name, "p90"),
                metric(row, metric_name, "p95"),
                metric(row, metric_name, "p99"),
                metric(row, metric_name, "max"),
                percent_of(avg, server_avg),
                percent_of(avg, client_avg),
            ]
        )
    return rows


def server_boundary_cross_check_rows(row: dict[str, Any] | None) -> list[list[Any]]:
    if not row:
        return []
    pre = metric(row, "server_pre_view_ms", "avg")
    post = metric(row, "server_post_view_ms", "avg")
    outside = metric(row, "server_outside_view_ms", "avg") or metric(row, "gunicorn_outside_view_ms", "avg")
    rows = [
        [
            "server_outside_view_ms",
            outside,
            "compatibility aggregate: server_total_ms - view_total_ms",
        ],
        [
            "server_pre_view_ms + server_post_view_ms",
            (num(pre) or 0) + (num(post) or 0) if pre is not None and post is not None else None,
            "measured outside-view split",
        ],
        [
            "server_boundary_reconciliation_delta_ms",
            metric(row, "server_boundary_reconciliation_delta_ms", "avg"),
            "server_total_ms - (server_pre_view_ms + view_total_ms + server_post_view_ms)",
        ],
        [
            "server_outside_view_reconciliation_delta_ms",
            metric(row, "server_outside_view_reconciliation_delta_ms", "avg"),
            "server_outside_view_ms - (server_pre_view_ms + server_post_view_ms)",
        ],
    ]
    return [row for row in rows if row[1] is not None]


def outside_view_share_rows(row: dict[str, Any] | None) -> list[list[Any]]:
    if not row:
        return []
    outside = metric(row, "server_outside_view_ms", "avg") or metric(row, "gunicorn_outside_view_ms", "avg")
    rows = []
    for label, metric_name in [
        ("pre-view", "server_pre_view_ms"),
        ("post-view", "server_post_view_ms"),
    ]:
        avg = metric(row, metric_name, "avg")
        if avg is None:
            continue
        rows.append([label, avg, percent_of(avg, outside)])
    return rows


def post_view_decomposition_rows(row: dict[str, Any] | None) -> list[list[Any]]:
    if not row:
        return []
    post_view_avg = metric(row, "server_post_view_ms", "avg")
    regions = [
        ("view exit -> response start", "post_view_to_response_start_ms"),
        ("response start -> response complete", "response_send_ms"),
        ("response complete -> ASGI return", "asgi_after_response_complete_ms"),
    ]
    rows = []
    for label, metric_name in regions:
        avg = metric(row, metric_name, "avg")
        if avg is None:
            continue
        rows.append(
            [
                label,
                avg,
                metric(row, metric_name, "p50") or metric(row, metric_name, "median"),
                metric(row, metric_name, "p95"),
                metric(row, metric_name, "p99"),
                percent_of(avg, post_view_avg),
            ]
        )
    return rows


PRE_VIEW_STRUCTURAL_REGIONS = {
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


def pre_view_structural_metric_names(row: dict[str, Any] | None) -> list[str]:
    if not row:
        return []
    if (
        metric(row, "pre_view_django_to_middleware_ms", "avg") is not None
        and metric(row, "pre_view_middleware_to_drf_dispatch_ms", "avg") is not None
    ):
        django_regions = [
            "pre_view_django_to_middleware_ms",
            "pre_view_middleware_to_drf_dispatch_ms",
        ]
    else:
        django_regions = ["pre_view_django_to_drf_dispatch_ms"]
    return [
        "pre_view_asgi_to_django_ms",
        *django_regions,
        "drf_dispatch_pre_initialize_ms",
        "drf_initialize_request_ms",
        "drf_dispatch_pre_initial_ms",
        "drf_initial_total_ms",
        "drf_initial_to_post_ms",
        "pre_view_unattributed_ms",
    ]


def dominant_pre_view_region_for_row(row: dict[str, Any] | None) -> tuple[str, Any, Any, Any]:
    if not row:
        return "unavailable", None, None, None
    existing = row.get("dominant_pre_view_region")
    existing_avg = row.get("dominant_pre_view_region_avg_ms")
    if existing and existing != "unavailable":
        return (
            str(existing),
            existing_avg,
            row.get("dominant_pre_view_region_percent_of_pre_view"),
            row.get("dominant_pre_view_region_percent_of_client"),
        )
    candidates = []
    for name in pre_view_structural_metric_names(row):
        avg = metric(row, name, "avg")
        if avg is not None:
            candidates.append((PRE_VIEW_STRUCTURAL_REGIONS.get(name, name), avg, name))
    if not candidates:
        return "unavailable", None, None, None
    label, avg, _metric_name = max(candidates, key=lambda item: num(item[1]) or -1)
    return (
        label,
        avg,
        percent_of(avg, metric(row, "server_pre_view_ms", "avg")),
        percent_of(avg, metric(row, "client_latency_ms", "avg")),
    )


def pre_view_decomposition_rows(row: dict[str, Any] | None) -> list[list[Any]]:
    if not row:
        return []
    pre_view_avg = metric(row, "server_pre_view_ms", "avg")
    server_avg = metric(row, "server_total_ms", "avg") or metric(row, "gunicorn_request_ms", "avg")
    client_avg = metric(row, "client_latency_ms", "avg")
    rows = []
    for name in pre_view_structural_metric_names(row):
        avg = metric(row, name, "avg")
        if avg is None:
            continue
        rows.append(
            [
                PRE_VIEW_STRUCTURAL_REGIONS.get(name, name),
                avg,
                metric(row, name, "p50") or metric(row, name, "median"),
                metric(row, name, "p75"),
                metric(row, name, "p90"),
                metric(row, name, "p95"),
                metric(row, name, "p99"),
                metric(row, name, "max"),
                percent_of(avg, pre_view_avg),
                percent_of(avg, server_avg),
                percent_of(avg, client_avg),
            ]
        )
    return rows


def drf_initial_decomposition_rows(row: dict[str, Any] | None) -> list[list[Any]]:
    if not row:
        return []
    drf_initial_avg = metric(row, "drf_initial_total_ms", "avg")
    pre_view_avg = metric(row, "server_pre_view_ms", "avg")
    regions = [
        ("content negotiation", "drf_content_negotiation_ms"),
        ("versioning", "drf_versioning_ms"),
        ("authentication total", "drf_authentication_total_ms"),
        ("permissions", "drf_permission_ms"),
        ("throttling", "drf_throttle_ms"),
        ("DRF initial unattributed", "drf_initial_unattributed_ms"),
    ]
    rows = []
    for label, name in regions:
        avg = metric(row, name, "avg")
        if avg is None:
            continue
        rows.append(
            [
                label,
                avg,
                metric(row, name, "p50") or metric(row, name, "median"),
                metric(row, name, "p95"),
                metric(row, name, "p99"),
                percent_of(avg, drf_initial_avg),
                percent_of(avg, pre_view_avg),
            ]
        )
    return rows


def authentication_diagnostic_rows(row: dict[str, Any] | None) -> list[list[Any]]:
    if not row:
        return []
    auth_total = metric(row, "drf_authentication_total_ms", "avg")
    pre_view_avg = metric(row, "server_pre_view_ms", "avg")
    rows = []
    for label, name, parent in [
        ("DRF authentication total", "drf_authentication_total_ms", pre_view_avg),
        ("JWT authentication", "auth_jwt_ms", auth_total),
        ("authentication unattributed", "drf_authentication_unattributed_ms", auth_total),
    ]:
        avg = metric(row, name, "avg")
        if avg is None:
            continue
        rows.append(
            [
                label,
                avg,
                metric(row, name, "p50") or metric(row, name, "median"),
                metric(row, name, "p95"),
                metric(row, name, "p99"),
                percent_of(avg, parent),
                percent_of(avg, pre_view_avg),
            ]
        )
    return rows


def thread_context_rows(row: dict[str, Any] | None) -> list[list[Any]]:
    observations = (row or {}).get("thread_context_observations") or {}
    changes = observations.get("thread_identity_change") or {}
    rows = []
    for transition, data in changes.items():
        rows.append(
            [
                transition,
                data.get("sample_count"),
                data.get("changed_count"),
                data.get("changed_percent"),
            ]
        )
    return rows


def timing_detail_rows(row: dict[str, Any] | None, names: list[str]) -> list[list[Any]]:
    if not row:
        return []
    rows = []
    for name in names:
        value = row.get(name)
        if not isinstance(value, dict) or value.get("avg") is None:
            continue
        rows.append(
            [
                name,
                value.get("avg"),
                value.get("p50") or value.get("median"),
                value.get("p75"),
                value.get("p90"),
                value.get("p95"),
                value.get("p99"),
                value.get("max"),
            ]
        )
    return rows


def database_operation_rows(row: dict[str, Any] | None) -> list[list[Any]]:
    if not row:
        return []
    total_count = metric(row, "db_query_count", "avg")
    operations = [
        ("SELECT", "select"),
        ("INSERT", "insert"),
        ("UPDATE", "update"),
        ("DELETE", "delete"),
        ("OTHER", "other"),
    ]
    rows = []
    for label, key in operations:
        count = metric(row, f"db_query_{key}_count", "avg")
        if count is None:
            continue
        rows.append(
            [
                label,
                count,
                percent_of(count, total_count),
            ]
        )
    return rows


def stage_database_rows(row: dict[str, Any] | None) -> list[list[Any]]:
    if not row:
        return []
    total_db_ms = metric(row, "db_query_total_ms", "avg")
    stages = [
        ("recipient resolution", "recipient_resolution"),
        ("service call boundary", "service_call"),
        ("recovery", "recovery"),
        ("direct send", "direct_send"),
        ("outbox", "outbox"),
        ("unattributed", "unattributed"),
    ]
    rows = []
    for label, key in stages:
        count = metric(row, f"{key}_db_query_count", "avg")
        total_ms = metric(row, f"{key}_db_query_total_ms", "avg")
        if count is None and total_ms is None:
            continue
        rows.append(
            [
                label,
                count,
                total_ms,
                percent_of(total_ms, total_db_ms),
                metric(row, f"{key}_db_query_avg_ms", "avg"),
                metric(row, f"{key}_db_query_p95_ms", "avg"),
                metric(row, f"{key}_db_query_p99_ms", "avg"),
                metric(row, f"{key}_db_query_select_count", "avg"),
                metric(row, f"{key}_db_query_insert_count", "avg"),
                metric(row, f"{key}_db_query_update_count", "avg"),
                metric(row, f"{key}_db_query_delete_count", "avg"),
                metric(row, f"{key}_db_query_other_count", "avg"),
            ]
        )
    return rows


def append_database_observation_tables(lines: list[str], row: dict[str, Any] | None) -> None:
    operation_rows = database_operation_rows(row)
    lines.extend(["", "**Database Operation Counts**", ""])
    if operation_rows:
        lines.extend(
            markdown_table(
                ["operation", "count_avg", "percent_of_queries"],
                operation_rows,
            )
        )
    else:
        lines.append("No target-concurrency operation count samples were available.")

    stage_rows = stage_database_rows(row)
    lines.extend(["", "**Stage-Attributed Database Timing**", ""])
    lines.append("These are cross-cutting DB observations, not structural latency children; independently aggregated stage averages may not sum exactly to `db_query_total_ms`.")
    lines.append("")
    if stage_rows:
        lines.extend(
            markdown_table(
                [
                    "stage",
                    "query_count_avg",
                    "query_total_avg_ms",
                    "percent_of_db_total",
                    "query_avg_ms",
                    "query_p95_ms",
                    "query_p99_ms",
                    "select_avg",
                    "insert_avg",
                    "update_avg",
                    "delete_avg",
                    "other_avg",
                ],
                stage_rows,
            )
        )
    else:
        lines.append("No target-concurrency stage-attributed DB samples were available.")


def runtime_services(report: dict[str, Any]) -> dict[str, Any]:
    return (
        report.get("effective_runtime_config", {})
        .get("services", {})
        or {}
    )


def messenger_env_from_report(report: dict[str, Any]) -> dict[str, Any]:
    services = runtime_services(report)
    messenger = services.get("messenger") or {}
    return messenger.get("env") or {}


def metadata_env(metadata: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    env = dict(messenger_env_from_report(report))
    env.update(metadata.get("messenger_env") or {})
    return env


def input_rows(
    report: dict[str, Any],
    *,
    json_report_path: str | Path | None = None,
    include_source_paths: bool = True,
) -> list[list[Any]]:
    rows: list[list[Any]] = [
        ["result", "PASS" if report.get("passed") else "FAIL"],
        ["run_id", report.get("run_id")],
        ["started_at", report.get("started_at")],
        ["finished_at", report.get("finished_at")],
        ["traffic_mode", report.get("traffic_mode")],
        ["service_url_mode", report.get("service_url_mode")],
        ["identity_base_url", report.get("identity_base_url")],
        ["messenger_base_url", report.get("messenger_base_url")],
    ]
    if json_report_path:
        rows.append(["primary_json", str(json_report_path)])

    config = report.get("config") or {}
    for key, value in config.items():
        if not include_source_paths and key in {"REPORT_DIR"}:
            continue
        rows.append([f"input.{key}", value])

    benchmark_http = (
        report.get("effective_runtime_config", {})
        .get("benchmark_http", {})
        or {}
    )
    for key, value in benchmark_http.items():
        rows.append([f"effective.benchmark_http.{key}", value])

    for service_name, service in runtime_services(report).items():
        rows.append([f"service.{service_name}.container", service.get("container")])
        for key, value in (service.get("env") or {}).items():
            rows.append([f"service.{service_name}.env.{key}", value])

    runtime = report.get("runtime_environment") or {}
    python_proc = runtime.get("python_process") or {}
    rows.extend(
        [
            ["runtime.platform", python_proc.get("platform")],
            ["runtime.cpu_count_seen_by_runner", python_proc.get("cpu_count_seen_by_test_runner")],
            ["runtime.mem_total_mb", (python_proc.get("meminfo") or {}).get("mem_total_mb")],
            ["runtime.mem_available_mb", (python_proc.get("meminfo") or {}).get("mem_available_mb")],
        ]
    )
    return rows


def success_failure_rows(report: dict[str, Any], metadata: dict[str, Any] | None = None) -> list[list[Any]]:
    summary = report.get("summary") or {}
    setup_diag = (report.get("setup") or {}).get("failure_diagnostics") or {}
    gap = report.get("request_gap_analysis") or {}
    exception_summary = gap.get("server_exception_summary") or {}
    drain = report.get("realtime_outbox_drain_validation") or {}
    metadata = metadata or {}

    rows = [
        ["benchmark_succeeded", metadata.get("benchmark_succeeded", report.get("passed"))],
        ["benchmark_error", metadata.get("benchmark_error") or report.get("fatal_error")],
        ["cleanup_success", report.get("cleanup_success")],
        ["outbox_worker_enabled", drain.get("worker_enabled")],
        ["outbox_drain_succeeded", drain.get("succeeded")],
        ["total_messages", summary.get("total_messages")],
        ["success_count", summary.get("success_count")],
        ["failure_count", summary.get("failure_count")],
        ["status_counts", summary.get("status_counts")],
        ["unique_message_id_count", summary.get("unique_message_id_count")],
        ["duplicate_message_id_count", summary.get("duplicate_message_id_count")],
        ["unique_room_id_count", summary.get("unique_room_id_count")],
        ["setup_pair_count_requested", setup_diag.get("pair_count_requested")],
        ["setup_pair_count_successful", setup_diag.get("pair_count_successful")],
        ["setup_failed_count", setup_diag.get("failed_count")],
        ["setup_top_reasons", setup_diag.get("top_reasons")],
        ["matched_request_count", gap.get("matched_request_count")],
        ["unmatched_request_count", gap.get("unmatched_request_count")],
        ["unmatched_percent", gap.get("unmatched_percent")],
        [
            "server_exception_request_count",
            exception_summary.get("request_count_with_server_exception"),
        ],
        ["server_exception_types", exception_summary.get("by_exception_type")],
    ]

    for service_name, result in (report.get("cleanup") or {}).items():
        if isinstance(result, dict):
            rows.append([f"cleanup.{service_name}.enabled", result.get("enabled")])
            rows.append([f"cleanup.{service_name}.success", result.get("success")])
            rows.append([f"cleanup.{service_name}.deleted_count", result.get("deleted_count")])
            rows.append([f"cleanup.{service_name}.failed_samples", result.get("failed_samples")])

    failures = (report.get("failure_diagnostics") or {}).get("phases") or []
    if failures:
        rows.append(["failure_phases", failures])
    failed_samples = summary.get("failed_samples") or []
    if failed_samples:
        rows.append(["failed_samples", failed_samples[:5]])
    return rows


def benchmark_rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    return list((report.get("benchmark") or {}).get("per_level") or [])


def gap_rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    rows = (report.get("request_gap_analysis") or {}).get("per_level") or []
    return [row for row in rows if not row.get("endpoint")]


def rows_by_concurrency(rows: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    result = {}
    for row in rows:
        try:
            result[int(row.get("concurrency"))] = row
        except (TypeError, ValueError):
            continue
    return result


def per_level_docker_stats(level: dict[str, Any], gap: dict[str, Any] | None = None) -> dict[str, Any]:
    blocks = []
    if gap:
        blocks.append(gap.get("host_docker_stats") or {})
    blocks.append(level.get("host_docker_stats") or {})
    blocks.append(((level.get("docker_stats") or {}).get("overall") or {}))

    for block in blocks:
        containers = block.get("containers") or {}
        if not containers:
            continue
        chosen_name = None
        for name in containers:
            name_lower = str(name).lower()
            if "messenger" in name_lower and "outbox" not in name_lower:
                chosen_name = name
                break
        if chosen_name is None:
            for name in containers:
                if "messenger" in str(name).lower():
                    chosen_name = name
                    break
        if chosen_name is None:
            chosen_name = sorted(containers)[0]
        stats = dict(containers.get(chosen_name) or {})
        stats["_container"] = chosen_name
        stats["_sample_source"] = block.get("sample_source")
        stats["_sample_count"] = stats.get("sample_count") or block.get("sample_count")
        return stats
    return {}


def accurate_timing_table_rows(report: dict[str, Any]) -> list[list[Any]]:
    levels = benchmark_rows(report)
    gap_by_c = rows_by_concurrency(gap_rows(report))
    rows = []
    for level in levels:
        try:
            concurrency = int(level.get("concurrency"))
        except (TypeError, ValueError):
            concurrency = level.get("concurrency")
        gap = gap_by_c.get(concurrency if isinstance(concurrency, int) else -1)
        source = gap or level
        docker_stats = per_level_docker_stats(level, gap)
        cpu = docker_stats.get("cpu_percent") or {}
        mem = docker_stats.get("mem_percent") or {}
        rows.append(
            [
                concurrency,
                "PASS" if int(level.get("failure_count") or 0) == 0 else "FAIL",
                level.get("total_messages", source.get("total_messages")),
                level.get("success_count", source.get("success_count")),
                level.get("failure_count", source.get("failure_count")),
                level.get("successful_messages_per_second", level.get("messages_per_second")),
                metric(source, "client_latency_ms", "avg") or metric(level, "latency_ms", "avg"),
                metric(source, "client_latency_ms", "p50") or metric(level, "latency_ms", "p50") or metric(source, "client_latency_ms", "median") or metric(level, "latency_ms", "median"),
                metric(source, "client_latency_ms", "p95") or metric(level, "latency_ms", "p95"),
                metric(source, "client_latency_ms", "p99") or metric(level, "latency_ms", "p99"),
                metric(source, "server_total_ms", "avg") or metric(source, "gunicorn_request_ms", "avg"),
                metric(source, "server_total_ms", "p95") or metric(source, "gunicorn_request_ms", "p95"),
                metric(source, "server_pre_view_ms", "avg"),
                metric(source, "view_total_ms", "avg") or metric(level, "main_django_logic_time_ms", "avg"),
                metric(source, "view_total_ms", "p95") or metric(level, "main_django_logic_time_ms", "p95"),
                metric(source, "server_post_view_ms", "avg"),
                metric(source, "server_outside_view_ms", "avg") or metric(source, "gunicorn_outside_view_ms", "avg"),
                dominant_outside_view_region_for_row(source),
                dominant_pre_view_region_for_row(source)[0],
                dominant_pre_view_region_for_row(source)[1],
                metric(source, "pre_view_unattributed_ms", "avg"),
                metric(source, "service_total_ms", "avg"),
                metric(source, "service_total_ms", "p95"),
                metric(source, "db_query_count", "avg"),
                metric(source, "db_query_total_ms", "avg"),
                metric(source, "db_connection_ensure_ms", "avg"),
                metric(source, "db_query_select_count", "avg"),
                metric(source, "db_query_insert_count", "avg"),
                metric(source, "db_query_update_count", "avg"),
                metric(source, "db_query_delete_count", "avg"),
                metric(source, "db_query_other_count", "avg"),
                metric(source, "service_realtime_outbox_persist_ms", "avg") or metric(source, "durable_outbox_persist_ms", "avg") or metric(source, "realtime_enqueue_ms", "avg"),
                metric(source, "client_outside_server_ms", "avg") or metric(source, "client_or_network_gap_ms", "avg"),
                metric(source, "view_unattributed_ms", "avg"),
                metric(source, "service_unattributed_ms", "avg"),
                largest_unattributed_region(source)[2],
                metric(source, "overall_client_request_time_ms", "total") or metric(level, "overall_client_request_time_ms", "total"),
                metric(source, "main_django_logic_time_ms", "total") or metric(level, "main_django_logic_time_ms", "total"),
                source.get("matched_request_count"),
                source.get("unmatched_request_count"),
                docker_stats.get("_sample_count"),
                docker_stats.get("_sample_source"),
                cpu.get("min"),
                cpu.get("avg"),
                cpu.get("max"),
                mem.get("min"),
                mem.get("avg"),
                mem.get("max"),
            ]
        )
    return rows


def accurate_timing_headers() -> list[str]:
    return [
        "concurrency",
        "result",
        "requests",
        "success",
        "failure",
        "msg/s",
        "client_avg_ms",
        "client_p50_ms",
        "client_p95_ms",
        "client_p99_ms",
        "server_avg_ms",
        "server_p95_ms",
        "server_pre_view_avg_ms",
        "view_avg_ms",
        "view_p95_ms",
        "server_post_view_avg_ms",
        "server_outside_view_avg_ms",
        "dominant_outside_view_region",
        "dominant_pre_view_region",
        "dominant_pre_view_region_avg_ms",
        "pre_view_unattributed_avg_ms",
        "service_avg_ms",
        "service_p95_ms",
        "db_query_count_avg",
        "db_query_total_avg_ms",
        "db_connection_ensure_avg_ms",
        "db_select_count_avg",
        "db_insert_count_avg",
        "db_update_count_avg",
        "db_delete_count_avg",
        "db_other_count_avg",
        "outbox_enqueue_avg_ms",
        "client_outside_server_avg_ms",
        "view_unattributed_avg_ms",
        "service_unattributed_avg_ms",
        "largest_unattributed_pct",
        "overall_client_total_ms",
        "view_total_ms",
        "matched_requests",
        "unmatched_requests",
        "docker_samples",
        "docker_sample_source",
        "docker_cpu_min",
        "docker_cpu_avg",
        "docker_cpu_max",
        "docker_mem_min",
        "docker_mem_avg",
        "docker_mem_max",
    ]


def docker_usage_rows(report: dict[str, Any]) -> list[list[Any]]:
    host_stats = (
        (report.get("request_gap_analysis") or {})
        .get("host_docker_stats", {})
        .get("containers", {})
        or {}
    )
    rows = []
    for container, stats in host_stats.items():
        cpu = stats.get("cpu_percent") or {}
        mem = stats.get("mem_percent") or {}
        rows.append(
            [
                container,
                stats.get("sample_count"),
                cpu.get("min"),
                cpu.get("avg"),
                cpu.get("max"),
                cpu.get("p95"),
                mem.get("min"),
                mem.get("avg"),
                mem.get("max"),
                mem.get("p95"),
            ]
        )
    return rows


def write_accurate_readme(
    report: dict[str, Any],
    output_md: Path,
    *,
    json_report_path: str | Path | None = None,
    metadata: dict[str, Any] | None = None,
    include_source_paths: bool = True,
) -> None:
    lines: list[str] = ["# Accurate Timing Test", ""]
    lines.extend(["## 1. Test Details", ""])
    lines.extend(
        markdown_table(
            ["Input", "Value"],
            input_rows(
                report,
                json_report_path=json_report_path if include_source_paths else None,
                include_source_paths=include_source_paths,
            ),
        )
    )

    lines.extend(["", "## 2. Success And Failure Data", ""])
    lines.extend(markdown_table(["Task", "Value"], success_failure_rows(report, metadata)))

    target = concurrency_target(report)
    target_gap = gap_for_level(report, target)
    lines.extend(["", "## 3. Target-Concurrency Summary", ""])
    lines.extend(markdown_table(["Metric", "Value"], target_summary_rows(report, target)))

    lines.extend(["", "## 4. Server Boundary Decomposition", ""])
    boundary_rows = server_boundary_decomposition_rows(target_gap)
    if boundary_rows:
        lines.extend(
            markdown_table(
                [
                    "region",
                    "avg_ms",
                    "p50_ms",
                    "p75_ms",
                    "p90_ms",
                    "p95_ms",
                    "p99_ms",
                    "max_ms",
                    "% server",
                    "% client",
                ],
                boundary_rows,
            )
        )
        lines.extend(
            [
                "",
                f"Dominant outside-view region: `{dominant_outside_view_region_for_row(target_gap)}`",
                "",
                "**Outside-View Latency Share**",
                "",
            ]
        )
        lines.extend(
            markdown_table(
                ["region", "avg_ms", "% outside-view"],
                outside_view_share_rows(target_gap),
            )
        )
        cross_check_rows = server_boundary_cross_check_rows(target_gap)
        if cross_check_rows:
            lines.extend(["", "**Compatibility Cross-Check**", ""])
            lines.extend(
                markdown_table(
                    ["metric", "avg_ms", "note"],
                    cross_check_rows,
                )
            )
    else:
        lines.append("No matched target-concurrency server boundary samples were available.")

    lines.extend(["", "## 5. Pre-View Decomposition", ""])
    pre_view_rows = pre_view_decomposition_rows(target_gap)
    if pre_view_rows:
        lines.extend(
            markdown_table(
                [
                    "region",
                    "avg_ms",
                    "p50_ms",
                    "p75_ms",
                    "p90_ms",
                    "p95_ms",
                    "p99_ms",
                    "max_ms",
                    "% pre-view",
                    "% server",
                    "% client",
                ],
                pre_view_rows,
            )
        )
        dominant_name, dominant_avg, dominant_pct, dominant_client_pct = (
            dominant_pre_view_region_for_row(target_gap)
        )
        lines.extend(
            [
                "",
                f"Dominant pre-view region: `{dominant_name}` at `{fmt(dominant_avg)}` ms average (`{fmt(dominant_pct)}`% of pre-view, `{fmt(dominant_client_pct)}`% of client latency).",
            ]
        )
    else:
        lines.append("No matched target-concurrency pre-view sublayer samples were available.")

    lines.extend(["", "## 6. DRF Initial Decomposition", ""])
    drf_rows = drf_initial_decomposition_rows(target_gap)
    if drf_rows:
        lines.extend(
            markdown_table(
                ["region", "avg_ms", "p50_ms", "p95_ms", "p99_ms", "% DRF initial", "% pre-view"],
                drf_rows,
            )
        )
        auth_rows = authentication_diagnostic_rows(target_gap)
        if auth_rows:
            lines.extend(["", "**Authentication Diagnostics**", ""])
            lines.extend(
                markdown_table(
                    ["region", "avg_ms", "p50_ms", "p95_ms", "p99_ms", "% parent", "% pre-view"],
                    auth_rows,
                )
            )
    else:
        lines.append("No matched target-concurrency DRF initial samples were available.")

    lines.extend(["", "## 7. Remaining Pre-View Unattributed Time", ""])
    pre_view_unattributed_avg = metric(target_gap, "pre_view_unattributed_ms", "avg")
    lines.extend(
        markdown_table(
            ["metric", "value"],
            [
                ["avg_ms", pre_view_unattributed_avg],
                ["p50_ms", metric(target_gap, "pre_view_unattributed_ms", "p50") or metric(target_gap, "pre_view_unattributed_ms", "median")],
                ["p95_ms", metric(target_gap, "pre_view_unattributed_ms", "p95")],
                ["p99_ms", metric(target_gap, "pre_view_unattributed_ms", "p99")],
                ["percent_of_pre_view", percent_of(pre_view_unattributed_avg, metric(target_gap, "server_pre_view_ms", "avg"))],
                ["percent_of_client", percent_of(pre_view_unattributed_avg, metric(target_gap, "client_latency_ms", "avg"))],
            ],
        )
    )
    if percent_of(pre_view_unattributed_avg, metric(target_gap, "server_pre_view_ms", "avg")) and percent_of(pre_view_unattributed_avg, metric(target_gap, "server_pre_view_ms", "avg")) > 10:
        lines.append("")
        lines.append("PRE-VIEW INSTRUMENTATION IS STILL INCOMPLETE.")

    lines.extend(["", "## 8. Thread / Execution Context Observations", ""])
    thread_rows = thread_context_rows(target_gap)
    if thread_rows:
        lines.extend(
            markdown_table(
                ["transition", "samples", "changed", "changed_percent"],
                thread_rows,
            )
        )
        lines.append("")
        lines.append("Thread identity changes are observations only; they do not prove executor queue wait or scheduling overhead.")
    else:
        lines.append("No thread context observations were available.")

    lines.extend(["", "## 9. Post-View Decomposition", ""])
    post_view_rows = post_view_decomposition_rows(target_gap)
    if post_view_rows:
        lines.extend(
            markdown_table(
                ["region", "avg_ms", "p50_ms", "p95_ms", "p99_ms", "% post-view"],
                post_view_rows,
            )
        )
        lines.append("")
        lines.append("`response_send_ms` is an ASGI application-boundary response emission interval, not end-to-end network latency.")
    else:
        lines.append("No matched target-concurrency post-view boundary samples were available.")

    lines.extend(["", "## 10. Latency Decomposition", ""])
    decomposition = latency_decomposition_rows(target_gap)
    if decomposition:
        lines.extend(
            markdown_table(
                [
                    "stage",
                    "metric",
                    "avg_ms",
                    "percent_of_parent",
                    "percent_of_client_total",
                    "p50_ms",
                    "p95_ms",
                    "p99_ms",
                ],
                decomposition,
            )
        )
    else:
        lines.append("No matched target-concurrency timing rows were available for decomposition.")

    lines.extend(["", "## 11. Database Observations", ""])
    append_database_observation_tables(lines, target_gap)

    lines.extend(["", "## 12. Concurrent Run Timing Table", ""])
    lines.extend(markdown_table(accurate_timing_headers(), accurate_timing_table_rows(report)))

    lines.extend(["", *metric_definitions_section()])
    docker_rows = docker_usage_rows(report)
    if docker_rows:
        lines.extend(["", "**Docker Usage Across The Accurate Timing Run**", ""])
        lines.extend(
            markdown_table(
                [
                    "container",
                    "samples",
                    "cpu_min",
                    "cpu_avg",
                    "cpu_max",
                    "cpu_p95",
                    "mem_min",
                    "mem_avg",
                    "mem_max",
                    "mem_p95",
                ],
                docker_rows,
            )
        )
    else:
        lines.extend(["", "**Docker Usage Across The Accurate Timing Run**", "", "No Docker usage samples were present in the primary JSON."])

    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def concurrency_target(report: dict[str, Any], preferred: int = 100) -> int | None:
    levels = []
    for row in benchmark_rows(report):
        try:
            levels.append(int(row.get("concurrency")))
        except (TypeError, ValueError):
            continue
    if not levels:
        return None
    return preferred if preferred in levels else max(levels)


def find_level(report: dict[str, Any], concurrency: int | None) -> dict[str, Any] | None:
    if concurrency is None:
        return None
    for row in benchmark_rows(report):
        try:
            if int(row.get("concurrency")) == concurrency:
                return row
        except (TypeError, ValueError):
            continue
    return None


def matrix_run_summary(metadata: dict[str, Any], report: dict[str, Any] | None, index: int, preferred_concurrency: int = 100) -> dict[str, Any]:
    report = report or {}
    target = concurrency_target(report, preferred_concurrency)
    level = find_level(report, target)
    gap = rows_by_concurrency(gap_rows(report)).get(target or -1)
    messenger_env = metadata_env(metadata, report)
    summary = report.get("summary") or {}
    status_counts = summary.get("status_counts") or {}
    dominant_pre_view_name, dominant_pre_view_avg, dominant_pre_view_pct, dominant_pre_view_client_pct = (
        dominant_pre_view_region_for_row(gap)
    )
    failure_count = int(summary.get("failure_count") or metadata.get("measured_failure_count") or 0)
    http_5xx = sum(
        int(count)
        for status, count in status_counts.items()
        if str(status).isdigit() and int(status) >= 500
    )
    disqualified = []
    if metadata.get("benchmark_succeeded") is False or report.get("passed") is False:
        disqualified.append("benchmark_failed")
    if failure_count:
        disqualified.append("measured_failures_present")
    if http_5xx:
        disqualified.append("http_5xx_present")
    if report and report.get("cleanup_success") is not True:
        disqualified.append("cleanup_failed")
    if not level:
        disqualified.append("missing_target_concurrency")

    return {
        "index": index,
        "config_name": metadata.get("run_label") or f"matrix_{index}",
        "target_concurrency": target,
        "eligible": not disqualified,
        "disqualification_reasons": disqualified,
        "web_concurrency": messenger_env.get("WEB_CONCURRENCY"),
        "asgi_threads": messenger_env.get("ASGI_THREADS"),
        "gunicorn_threads": messenger_env.get("GUNICORN_THREADS"),
        "gunicorn_backlog": messenger_env.get("GUNICORN_BACKLOG"),
        "db_conn_max_age": messenger_env.get("DB_CONN_MAX_AGE"),
        "client_avg_ms": metric(gap, "client_latency_ms", "avg") or metric(level, "latency_ms", "avg"),
        "client_p50_ms": metric(gap, "client_latency_ms", "p50") or metric(level, "latency_ms", "p50") or metric(gap, "client_latency_ms", "median") or metric(level, "latency_ms", "median"),
        "client_p95_ms": metric(gap, "client_latency_ms", "p95") or metric(level, "latency_ms", "p95"),
        "client_p99_ms": metric(gap, "client_latency_ms", "p99") or metric(level, "latency_ms", "p99"),
        "msg_per_sec": (level or {}).get("successful_messages_per_second", (level or {}).get("messages_per_second")),
        "server_avg_ms": metric(gap, "server_total_ms", "avg") or metric(gap, "gunicorn_request_ms", "avg"),
        "server_pre_view_avg_ms": metric(gap, "server_pre_view_ms", "avg"),
        "view_avg_ms": metric(gap, "view_total_ms", "avg") or metric(level, "main_django_logic_time_ms", "avg"),
        "django_avg_ms": metric(gap, "view_total_ms", "avg") or metric(level, "main_django_logic_time_ms", "avg"),
        "server_post_view_avg_ms": metric(gap, "server_post_view_ms", "avg"),
        "service_avg_ms": metric(gap, "service_total_ms", "avg"),
        "db_avg_ms": metric(gap, "db_query_total_ms", "avg"),
        "db_connection_ensure_avg_ms": metric(gap, "db_connection_ensure_ms", "avg"),
        "client_outside_server_avg_ms": metric(gap, "client_outside_server_ms", "avg") or metric(gap, "client_or_network_gap_ms", "avg"),
        "server_outside_view_avg_ms": metric(gap, "server_outside_view_ms", "avg") or metric(gap, "gunicorn_outside_view_ms", "avg"),
        "dominant_outside_view_region": dominant_outside_view_region_for_row(gap),
        "dominant_pre_view_region": dominant_pre_view_name,
        "dominant_pre_view_region_avg_ms": dominant_pre_view_avg,
        "dominant_pre_view_region_percent_of_pre_view": dominant_pre_view_pct,
        "dominant_pre_view_region_percent_of_client": dominant_pre_view_client_pct,
        "pre_view_unattributed_avg_ms": metric(gap, "pre_view_unattributed_ms", "avg"),
        "client_gap_avg_ms": metric(gap, "client_outside_server_ms", "avg") or metric(gap, "client_or_network_gap_ms", "avg"),
        "gunicorn_outside_view_avg_ms": metric(gap, "server_outside_view_ms", "avg") or metric(gap, "gunicorn_outside_view_ms", "avg"),
        "largest_latency_region": largest_latency_region(gap),
        "largest_measured_stage": largest_latency_region(gap),
        "largest_unattributed_region": largest_unattributed_region(gap)[0],
        "largest_unattributed_pct": largest_unattributed_region(gap)[2],
        "failure_count": failure_count,
        "http_5xx_count": http_5xx,
        "cleanup_success": report.get("cleanup_success"),
        "json_report_path": metadata.get("json_report_path"),
    }


def recommendation_key(row: dict[str, Any]) -> tuple[float, float, float, float]:
    return (
        num(row.get("client_p95_ms")) or 1e12,
        num(row.get("client_p99_ms")) or 1e12,
        num(row.get("client_avg_ms")) or 1e12,
        -(num(row.get("msg_per_sec")) or 0),
    )


def median_numeric(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [
        float(value)
        for row in rows
        if (value := num(row.get(key))) is not None
    ]
    if not values:
        return None
    return round(statistics.median(values), 2)


def cv_percent(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [
        float(value)
        for row in rows
        if (value := num(row.get(key))) is not None
    ]
    if len(values) < 2:
        return None
    mean = statistics.mean(values)
    if mean == 0:
        return None
    return round((statistics.stdev(values) / mean) * 100, 2)


def matrix_fingerprint(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row.get("web_concurrency"),
        row.get("asgi_threads"),
        row.get("gunicorn_backlog"),
        row.get("db_conn_max_age"),
    )


def aggregate_matrix_summaries(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(matrix_fingerprint(row), []).append(row)

    aggregated = []
    for index, (fingerprint, group_rows) in enumerate(groups.items(), start=1):
        web, asgi_threads, backlog, db_conn_max_age = fingerprint
        disqualification_reasons = sorted(
            {
                reason
                for row in group_rows
                for reason in (row.get("disqualification_reasons") or [])
            }
        )
        eligible_rows = [row for row in group_rows if row.get("eligible")]
        eligible = len(eligible_rows) == len(group_rows) and bool(group_rows)
        if not eligible and not disqualification_reasons:
            disqualification_reasons.append("one_or_more_repetitions_not_eligible")
        first = group_rows[0]
        server_pre_view_avg_ms = median_numeric(
            group_rows,
            "server_pre_view_avg_ms",
        )
        server_post_view_avg_ms = median_numeric(
            group_rows,
            "server_post_view_avg_ms",
        )
        dominant_pre_view_counts: dict[str, int] = {}
        for row in group_rows:
            name = str(row.get("dominant_pre_view_region") or "unavailable")
            dominant_pre_view_counts[name] = dominant_pre_view_counts.get(name, 0) + 1
        dominant_pre_view_region = (
            max(dominant_pre_view_counts, key=dominant_pre_view_counts.get)
            if dominant_pre_view_counts
            else "unavailable"
        )
        aggregated.append(
            {
                "index": index,
                "config_name": (
                    f"WEB_CONCURRENCY={fmt(web)} "
                    f"ASGI_THREADS={fmt(asgi_threads)} "
                    f"GUNICORN_BACKLOG={fmt(backlog)} "
                    f"DB_CONN_MAX_AGE={fmt(db_conn_max_age)}"
                ),
                "run_count": len(group_rows),
                "eligible": eligible,
                "disqualification_reasons": disqualification_reasons,
                "web_concurrency": web,
                "asgi_threads": asgi_threads,
                "gunicorn_threads": first.get("gunicorn_threads"),
                "gunicorn_backlog": backlog,
                "db_conn_max_age": db_conn_max_age,
                "target_concurrency": first.get("target_concurrency"),
                "client_avg_ms": median_numeric(group_rows, "client_avg_ms"),
                "client_p50_ms": median_numeric(group_rows, "client_p50_ms"),
                "client_p95_ms": median_numeric(group_rows, "client_p95_ms"),
                "client_p99_ms": median_numeric(group_rows, "client_p99_ms"),
                "client_p95_cv_pct": cv_percent(group_rows, "client_p95_ms"),
                "msg_per_sec": median_numeric(group_rows, "msg_per_sec"),
                "server_avg_ms": median_numeric(group_rows, "server_avg_ms"),
                "server_pre_view_avg_ms": server_pre_view_avg_ms,
                "view_avg_ms": median_numeric(group_rows, "view_avg_ms"),
                "server_post_view_avg_ms": server_post_view_avg_ms,
                "service_avg_ms": median_numeric(group_rows, "service_avg_ms"),
                "db_avg_ms": median_numeric(group_rows, "db_avg_ms"),
                "db_connection_ensure_avg_ms": median_numeric(group_rows, "db_connection_ensure_avg_ms"),
                "server_outside_view_avg_ms": median_numeric(group_rows, "server_outside_view_avg_ms"),
                "dominant_outside_view_region": dominant_outside_view_region(
                    server_pre_view_avg_ms,
                    server_post_view_avg_ms,
                ),
                "dominant_pre_view_region": dominant_pre_view_region,
                "dominant_pre_view_region_avg_ms": median_numeric(group_rows, "dominant_pre_view_region_avg_ms"),
                "dominant_pre_view_region_percent_of_pre_view": median_numeric(group_rows, "dominant_pre_view_region_percent_of_pre_view"),
                "dominant_pre_view_region_percent_of_client": median_numeric(group_rows, "dominant_pre_view_region_percent_of_client"),
                "dominant_pre_view_region_stable": len(dominant_pre_view_counts) == 1,
                "pre_view_unattributed_avg_ms": median_numeric(group_rows, "pre_view_unattributed_avg_ms"),
                "pre_view_unattributed_cv_pct": cv_percent(group_rows, "pre_view_unattributed_avg_ms"),
                "server_pre_view_cv_pct": cv_percent(group_rows, "server_pre_view_avg_ms"),
                "dominant_pre_view_region_cv_pct": cv_percent(group_rows, "dominant_pre_view_region_avg_ms"),
                "largest_latency_region": first.get("largest_latency_region") or first.get("largest_measured_stage"),
                "largest_measured_stage": first.get("largest_latency_region") or first.get("largest_measured_stage"),
                "largest_unattributed_region": first.get("largest_unattributed_region"),
                "largest_unattributed_pct": median_numeric(group_rows, "largest_unattributed_pct"),
                "failure_count": sum(int(row.get("failure_count") or 0) for row in group_rows),
                "http_5xx_count": sum(int(row.get("http_5xx_count") or 0) for row in group_rows),
                "cleanup_success": all(row.get("cleanup_success") is True for row in group_rows),
            }
        )
    return aggregated


def outside_view_evidence_line(row: dict[str, Any]) -> str | None:
    dominant = row.get("dominant_outside_view_region") or dominant_outside_view_region(
        row.get("server_pre_view_avg_ms"),
        row.get("server_post_view_avg_ms"),
    )
    if dominant not in {"server pre-view", "server post-view"}:
        return None
    avg_key = (
        "server_pre_view_avg_ms"
        if dominant == "server pre-view"
        else "server_post_view_avg_ms"
    )
    avg_ms = row.get(avg_key)
    return (
        f"- PROVEN: {dominant} is the dominant outside-view latency region. "
        f"It averages `{fmt(avg_ms)}` ms, representing "
        f"`{fmt(percent_of(avg_ms, row.get('client_avg_ms')))}`% of client latency and "
        f"`{fmt(percent_of(avg_ms, row.get('server_outside_view_avg_ms')))}`% of server outside-view latency."
    )


def pre_view_evidence_line(row: dict[str, Any]) -> str | None:
    name = row.get("dominant_pre_view_region")
    avg_ms = row.get("dominant_pre_view_region_avg_ms")
    if not name or name == "unavailable" or avg_ms is None:
        return None
    return (
        f"- PROVEN: the largest measured structural pre-view sublayer is `{fmt(name)}` "
        f"at `{fmt(avg_ms)}` ms average, representing "
        f"`{fmt(row.get('dominant_pre_view_region_percent_of_pre_view'))}`% of pre-view latency and "
        f"`{fmt(row.get('dominant_pre_view_region_percent_of_client'))}`% of client latency."
    )


def write_matrix_readme(
    manifest: dict[str, Any],
    output_md: Path,
    *,
    preferred_concurrency: int = 100,
    include_source_paths: bool = True,
) -> None:
    run_entries = manifest.get("runs") or []
    loaded: list[tuple[dict[str, Any], dict[str, Any] | None]] = []
    summaries: list[dict[str, Any]] = []
    for index, metadata in enumerate(run_entries, start=1):
        report = None
        json_path = metadata.get("json_report_path")
        if json_path and Path(json_path).exists():
            report = load_json(json_path)
        loaded.append((metadata, report))
        summaries.append(matrix_run_summary(metadata, report, index, preferred_concurrency))

    aggregated_summaries = aggregate_matrix_summaries(summaries)
    repeated_mode = any(row.get("run_count", 1) > 1 for row in aggregated_summaries)
    comparison_rows = aggregated_summaries if repeated_mode else summaries
    eligible = [row for row in comparison_rows if row.get("eligible")]
    recommended = min(eligible, key=recommendation_key) if eligible else None

    lines = ["# Matrix Tuning Test", "", "## Executive Summary", ""]
    if recommended:
        rec_unattributed_name = recommended.get("largest_unattributed_region")
        rec_unattributed_pct = recommended.get("largest_unattributed_pct")
        lines.extend(
            [
                f"**Recommended matrix:** {fmt(recommended.get('config_name'))}",
                "",
                f"Use WEB_CONCURRENCY `{fmt(recommended.get('web_concurrency'))}`, "
                f"ASGI_THREADS `{fmt(recommended.get('asgi_threads'))}`, "
                f"GUNICORN_BACKLOG `{fmt(recommended.get('gunicorn_backlog'))}`, "
                f"DB_CONN_MAX_AGE `{fmt(recommended.get('db_conn_max_age'))}`.",
                "",
                f"Why it won: among eligible runs it had the best target-concurrency client p95, with p99 and throughput used as tie-breakers.",
                "",
                f"Target concurrency `{fmt(recommended.get('target_concurrency'))}`: "
                f"client p50 `{fmt(recommended.get('client_p50_ms'))}` ms, "
                f"p95 `{fmt(recommended.get('client_p95_ms'))}` ms, "
                f"p99 `{fmt(recommended.get('client_p99_ms'))}` ms, "
                f"throughput `{fmt(recommended.get('msg_per_sec'))}` msg/s.",
                "",
                f"Largest latency region: `{fmt(recommended.get('largest_latency_region') or recommended.get('largest_measured_stage'))}`. "
                f"Largest remaining unattributed region: `{fmt(rec_unattributed_name)}` "
                f"at `{fmt(rec_unattributed_pct)}`% of client average.",
                "",
                f"Pre-view diagnosis: largest measured pre-view region is `{fmt(recommended.get('dominant_pre_view_region'))}` "
                f"at `{fmt(recommended.get('dominant_pre_view_region_avg_ms'))}` ms average.",
                "",
            ]
        )
    else:
        lines.extend(["**Recommended matrix:** NO VALID MATRIX WINNER", ""])

    lines.extend(metric_definitions_section())
    lines.extend(["", "## Cross-Matrix Comparison", ""])
    comparison_headers = [
        "matrix",
        "runs",
        "eligible",
        "web",
        "asgi_threads",
        "gunicorn_threads",
        "backlog",
        "db_conn_max_age",
        "target_c",
        "client_avg_ms",
        "client_p50_ms",
        "client_p95_ms",
        "client_p99_ms",
        "client_p95_cv_pct",
        "msg/s",
        "server_avg_ms",
        "server_pre_view_avg_ms",
        "view_avg_ms",
        "server_post_view_avg_ms",
        "dominant_outside_view_region",
        "dominant_pre_view_region",
        "dominant_pre_view_region_avg_ms",
        "pre_view_unattributed_avg_ms",
        "server_pre_view_cv_pct",
        "dominant_pre_view_region_cv_pct",
        "pre_view_unattributed_cv_pct",
        "service_avg_ms",
        "db_avg_ms",
        "db_connection_ensure_avg_ms",
        "largest_latency_region",
        "largest_unattributed_pct",
        "failures",
        "http_5xx",
        "cleanup",
        "disqualification_reasons",
    ]
    lines.extend(
        markdown_table(
            comparison_headers,
            [
                [
                    row.get("config_name"),
                    row.get("run_count", 1),
                    row.get("eligible"),
                    row.get("web_concurrency"),
                    row.get("asgi_threads"),
                    row.get("gunicorn_threads"),
                    row.get("gunicorn_backlog"),
                    row.get("db_conn_max_age"),
                    row.get("target_concurrency"),
                    row.get("client_avg_ms"),
                    row.get("client_p50_ms"),
                    row.get("client_p95_ms"),
                    row.get("client_p99_ms"),
                    row.get("client_p95_cv_pct"),
                    row.get("msg_per_sec"),
                    row.get("server_avg_ms"),
                    row.get("server_pre_view_avg_ms"),
                    row.get("view_avg_ms"),
                    row.get("server_post_view_avg_ms"),
                    row.get("dominant_outside_view_region"),
                    row.get("dominant_pre_view_region"),
                    row.get("dominant_pre_view_region_avg_ms"),
                    row.get("pre_view_unattributed_avg_ms"),
                    row.get("server_pre_view_cv_pct"),
                    row.get("dominant_pre_view_region_cv_pct"),
                    row.get("pre_view_unattributed_cv_pct"),
                    row.get("service_avg_ms"),
                    row.get("db_avg_ms"),
                    row.get("db_connection_ensure_avg_ms"),
                    row.get("largest_latency_region") or row.get("largest_measured_stage"),
                    row.get("largest_unattributed_pct"),
                    row.get("failure_count"),
                    row.get("http_5xx_count"),
                    row.get("cleanup_success"),
                    ", ".join(row.get("disqualification_reasons") or []),
                ]
                for row in comparison_rows
            ],
        )
    )
    lines.extend(
        [
            "",
            "## Repeated-Run Readiness",
            "",
            f"Matrix repetitions detected: `{repeated_mode}`.",
            "When more than one run exists for the same WEB_CONCURRENCY/ASGI_THREADS/backlog/DB connection-age tuple, ranking uses median target-concurrency metrics and reports client p95 coefficient of variation.",
            "Repeated rows also report coefficient of variation for server pre-view, the dominant pre-view sublayer, and remaining pre-view unattributed time.",
            "",
            "## Final Comparison Root-Cause Evidence",
            "",
        ]
    )
    if recommended:
        lines.append(
            f"- PROVEN: `{fmt(recommended.get('config_name'))}` is the best eligible matrix by the documented ranking strategy for target concurrency `{fmt(recommended.get('target_concurrency'))}`."
        )
        outside_evidence = outside_view_evidence_line(recommended)
        if outside_evidence:
            lines.append(outside_evidence)
        else:
            lines.append(
                f"- STRONGLY INDICATED: largest target-concurrency latency region for the recommendation is `{fmt(recommended.get('largest_latency_region') or recommended.get('largest_measured_stage'))}`."
            )
        pre_view_evidence = pre_view_evidence_line(recommended)
        if pre_view_evidence:
            lines.append(pre_view_evidence)
        lines.append(
            f"- POSSIBLE / REQUIRES MORE INSTRUMENTATION: the exact lower-level cause inside the dominant region remains unknown; executor wait, active ASGI thread count, executor queue depth, and transaction commit duration remain unavailable unless deeper supported instrumentation is added."
        )
    else:
        lines.append("- PROVEN: no eligible matrix was available for recommendation.")
    failed_rows = [row for row in comparison_rows if not row.get("eligible")]
    if failed_rows:
        lines.append(
            f"- PROVEN: `{len(failed_rows)}` matrix row(s) were disqualified by correctness, HTTP 5xx, cleanup, or missing target-concurrency data."
        )
    lines.extend(
        [
            "",
            "## Recommendation",
            "",
        ]
    )
    if recommended:
        lines.append(
            f"Run a smaller follow-up around `{fmt(recommended.get('config_name'))}` and the nearest competing ASGI thread count, with repetitions enabled, because one run per matrix is useful for direction but not production sizing."
        )
    else:
        lines.append("Fix correctness or cleanup failures first, then rerun the matrix before tuning latency.")

    for index, (metadata, report) in enumerate(loaded, start=1):
        lines.extend(["", f"## Matrix {index}: {fmt(metadata.get('run_label') or f'Run {index}')}", ""])
        if not report:
            lines.append(f"Missing primary JSON report: `{fmt(metadata.get('json_report_path'))}`")
            continue
        lines.extend(["**Test Details**", ""])
        lines.extend(
            markdown_table(
                ["Input", "Value"],
                input_rows(
                    report,
                    json_report_path=metadata.get("json_report_path") if include_source_paths else None,
                    include_source_paths=include_source_paths,
                ),
            )
        )
        lines.extend(["", "**Success And Failure Data**", ""])
        lines.extend(markdown_table(["Task", "Value"], success_failure_rows(report, metadata)))
        target = concurrency_target(report, preferred_concurrency)
        target_gap = gap_for_level(report, target)
        lines.extend(["", "**Target-Concurrency Summary**", ""])
        lines.extend(
            markdown_table(
                ["Metric", "Value"],
                target_summary_rows(report, target),
            )
        )
        lines.extend(["", "**Server Boundary Decomposition**", ""])
        boundary_rows = server_boundary_decomposition_rows(target_gap)
        if boundary_rows:
            lines.extend(
                markdown_table(
                    [
                        "region",
                        "avg_ms",
                        "p50_ms",
                        "p75_ms",
                        "p90_ms",
                        "p95_ms",
                        "p99_ms",
                        "max_ms",
                        "% server",
                        "% client",
                    ],
                    boundary_rows,
                )
            )
            lines.extend(
                [
                    "",
                    f"Dominant outside-view region: `{dominant_outside_view_region_for_row(target_gap)}`",
                    "",
                    "**Outside-View Latency Share**",
                    "",
                ]
            )
            lines.extend(
                markdown_table(
                    ["region", "avg_ms", "% outside-view"],
                    outside_view_share_rows(target_gap),
                )
            )
            cross_check_rows = server_boundary_cross_check_rows(target_gap)
            if cross_check_rows:
                lines.extend(["", "**Compatibility Cross-Check**", ""])
                lines.extend(
                    markdown_table(
                        ["metric", "avg_ms", "note"],
                        cross_check_rows,
                    )
                )
        else:
            lines.append("No matched target-concurrency server boundary samples were available.")

        lines.extend(["", "**Pre-View Decomposition**", ""])
        pre_view_rows = pre_view_decomposition_rows(target_gap)
        if pre_view_rows:
            lines.extend(
                markdown_table(
                    [
                        "region",
                        "avg_ms",
                        "p50_ms",
                        "p75_ms",
                        "p90_ms",
                        "p95_ms",
                        "p99_ms",
                        "max_ms",
                        "% pre-view",
                        "% server",
                        "% client",
                    ],
                    pre_view_rows,
                )
            )
            dominant_name, dominant_avg, dominant_pct, dominant_client_pct = (
                dominant_pre_view_region_for_row(target_gap)
            )
            lines.extend(
                [
                    "",
                    f"Dominant pre-view region: `{dominant_name}` at `{fmt(dominant_avg)}` ms average (`{fmt(dominant_pct)}`% of pre-view, `{fmt(dominant_client_pct)}`% of client latency).",
                ]
            )
        else:
            lines.append("No matched target-concurrency pre-view sublayer samples were available.")

        lines.extend(["", "**DRF Initial Decomposition**", ""])
        drf_rows = drf_initial_decomposition_rows(target_gap)
        if drf_rows:
            lines.extend(
                markdown_table(
                    ["region", "avg_ms", "p50_ms", "p95_ms", "p99_ms", "% DRF initial", "% pre-view"],
                    drf_rows,
                )
            )
            auth_rows = authentication_diagnostic_rows(target_gap)
            if auth_rows:
                lines.extend(["", "**Authentication Diagnostics**", ""])
                lines.extend(
                    markdown_table(
                        ["region", "avg_ms", "p50_ms", "p95_ms", "p99_ms", "% parent", "% pre-view"],
                        auth_rows,
                    )
                )
        else:
            lines.append("No matched target-concurrency DRF initial samples were available.")

        lines.extend(["", "**Remaining Pre-View Unattributed Time**", ""])
        pre_view_unattributed_avg = metric(target_gap, "pre_view_unattributed_ms", "avg")
        lines.extend(
            markdown_table(
                ["metric", "value"],
                [
                    ["avg_ms", pre_view_unattributed_avg],
                    ["p50_ms", metric(target_gap, "pre_view_unattributed_ms", "p50") or metric(target_gap, "pre_view_unattributed_ms", "median")],
                    ["p95_ms", metric(target_gap, "pre_view_unattributed_ms", "p95")],
                    ["p99_ms", metric(target_gap, "pre_view_unattributed_ms", "p99")],
                    ["percent_of_pre_view", percent_of(pre_view_unattributed_avg, metric(target_gap, "server_pre_view_ms", "avg"))],
                    ["percent_of_client", percent_of(pre_view_unattributed_avg, metric(target_gap, "client_latency_ms", "avg"))],
                ],
            )
        )
        if percent_of(pre_view_unattributed_avg, metric(target_gap, "server_pre_view_ms", "avg")) and percent_of(pre_view_unattributed_avg, metric(target_gap, "server_pre_view_ms", "avg")) > 10:
            lines.append("")
            lines.append("PRE-VIEW INSTRUMENTATION IS STILL INCOMPLETE.")

        lines.extend(["", "**Thread / Execution Context Observations**", ""])
        thread_rows = thread_context_rows(target_gap)
        if thread_rows:
            lines.extend(
                markdown_table(
                    ["transition", "samples", "changed", "changed_percent"],
                    thread_rows,
                )
            )
            lines.append("")
            lines.append("Thread identity changes are observations only; they do not prove executor queue wait or scheduling overhead.")
        else:
            lines.append("No thread context observations were available.")

        lines.extend(["", "**Post-View Decomposition**", ""])
        post_view_rows = post_view_decomposition_rows(target_gap)
        if post_view_rows:
            lines.extend(
                markdown_table(
                    ["region", "avg_ms", "p50_ms", "p95_ms", "p99_ms", "% post-view"],
                    post_view_rows,
                )
            )
            lines.append("")
            lines.append("`response_send_ms` is an ASGI application-boundary response emission interval, not end-to-end network latency.")
        else:
            lines.append("No matched target-concurrency post-view boundary samples were available.")

        lines.extend(["", "**Latency Decomposition**", ""])
        decomposition = latency_decomposition_rows(target_gap)
        if decomposition:
            lines.extend(
                markdown_table(
                    [
                        "stage",
                        "metric",
                        "avg_ms",
                        "percent_of_parent",
                        "percent_of_client_total",
                        "p50_ms",
                        "p95_ms",
                        "p99_ms",
                    ],
                    decomposition,
                )
            )
        else:
            lines.append("No matched target-concurrency timing rows were available for decomposition.")
        append_database_observation_tables(lines, target_gap)
        lines.extend(["", "**Concurrent Run Timing Table**", ""])
        lines.extend(
            markdown_table(
                accurate_timing_headers(),
                accurate_timing_table_rows(report),
            )
        )
        detail_tables = [
            (
                "**Client Timing**",
                [
                    "client_latency_ms",
                    "client_to_response_headers_ms",
                    "client_transport_to_response_headers_ms",
                    "client_response_body_read_ms",
                    "client_outside_server_ms",
                ],
            ),
            (
                "**View Timing**",
                [
                    "server_total_ms",
                    "server_pre_view_ms",
                    "pre_view_asgi_to_django_ms",
                    "pre_view_django_to_middleware_ms",
                    "pre_view_middleware_to_drf_dispatch_ms",
                    "pre_view_django_to_drf_dispatch_ms",
                    "drf_dispatch_pre_initialize_ms",
                    "drf_initialize_request_ms",
                    "drf_dispatch_pre_initial_ms",
                    "drf_initial_total_ms",
                    "drf_content_negotiation_ms",
                    "drf_versioning_ms",
                    "drf_authentication_total_ms",
                    "drf_authentication_unattributed_ms",
                    "drf_permission_ms",
                    "drf_throttle_ms",
                    "drf_initial_unattributed_ms",
                    "drf_initial_to_post_ms",
                    "pre_view_unattributed_ms",
                    "pre_view_boundary_reconciliation_delta_ms",
                    "drf_initial_reconciliation_delta_ms",
                    "server_outside_view_ms",
                    "auth_jwt_ms",
                    "view_total_ms",
                    "server_post_view_ms",
                    "post_view_to_response_start_ms",
                    "response_send_ms",
                    "asgi_after_response_complete_ms",
                    "server_boundary_reconciliation_delta_ms",
                    "server_outside_view_reconciliation_delta_ms",
                    "request_parse_validation_ms",
                    "view_authenticated_user_ms",
                    "view_payload_prepare_ms",
                    "view_recipient_resolution_ms",
                    "view_service_call_ms",
                    "view_response_build_ms",
                    "view_unattributed_ms",
                ],
            ),
            (
                "**Recovery Timing**",
                [
                    "recovery_total_ms",
                    "recovery_normalize_input_ms",
                    "recovery_policy_snapshot_ms",
                    "recovery_bundle_check_ms",
                    "recovery_validate_envelopes_ms",
                    "recovery_base_send_total_ms",
                    "recovery_envelope_bulk_insert_ms",
                    "recovery_unattributed_ms",
                ],
            ),
            (
                "**Direct Send Service Timing**",
                [
                    "service_total_ms",
                    "service_validate_input_ms",
                    "service_policy_snapshot_ms",
                    "service_existing_room_validation_ms",
                    "service_device_lookup_ms",
                    "service_room_validation_ms",
                    "service_contact_state_upsert_ms",
                    "service_reply_lookup_ms",
                    "service_message_insert_ms",
                    "service_attachment_validation_ms",
                    "service_key_envelope_bulk_insert_ms",
                    "service_receipt_decision_insert_ms",
                    "service_room_update_ms",
                    "service_realtime_outbox_persist_ms",
                    "service_unattributed_ms",
                ],
            ),
            (
                "**Database Metrics**",
                [
                    "db_query_count",
                    "db_query_total_ms",
                    "db_query_avg_ms",
                    "db_query_p50_ms",
                    "db_query_p95_ms",
                    "db_query_p99_ms",
                    "db_query_max_ms",
                    "db_connection_ensure_ms",
                    "db_connection_was_present_before_ensure",
                    "db_query_select_count",
                    "db_query_insert_count",
                    "db_query_update_count",
                    "db_query_delete_count",
                    "db_query_other_count",
                    "db_connection_observed_new",
                ],
            ),
            (
                "**Outbox Metrics**",
                [
                    "service_realtime_outbox_persist_ms",
                    "outbox_db_query_count",
                    "outbox_db_query_total_ms",
                    "outbox_db_query_avg_ms",
                    "outbox_db_query_p95_ms",
                    "outbox_db_query_p99_ms",
                    "outbox_db_query_select_count",
                    "outbox_db_query_insert_count",
                    "durable_outbox_persist_ms",
                    "realtime_enqueue_ms",
                ],
            ),
        ]
        for title, names in detail_tables:
            rows = timing_detail_rows(target_gap, names)
            lines.extend(["", title, ""])
            if rows:
                lines.extend(
                    markdown_table(
                        [
                            "metric",
                            "avg",
                            "p50",
                            "p75",
                            "p90",
                            "p95",
                            "p99",
                            "max",
                        ],
                        rows,
                    )
                )
            else:
                lines.append("No target-concurrency samples for this table.")
        lines.extend(
            [
                "",
                "**ASGI / Sync Adaptation Metrics**",
                "",
                "`server_outside_view_ms` is a compatibility aggregate. Use `server_pre_view_ms` and `server_post_view_ms` for root-cause location; exact executor wait, active thread count, and executor queue depth remain unavailable without unsupported ASGI/asgiref executor introspection.",
                "",
                "**Remaining Unattributed Time**",
                "",
            ]
        )
        unattr_name, unattr_ms, unattr_pct = largest_unattributed_region(target_gap)
        lines.extend(
            markdown_table(
                ["Region", "Avg ms", "Percent of client avg"],
                [
                    [
                        "client outside server",
                        metric(target_gap, "client_outside_server_ms", "avg"),
                        percent_of(metric(target_gap, "client_outside_server_ms", "avg"), metric(target_gap, "client_latency_ms", "avg")),
                    ],
                    [
                        "server pre-view",
                        metric(target_gap, "server_pre_view_ms", "avg"),
                        percent_of(metric(target_gap, "server_pre_view_ms", "avg"), metric(target_gap, "client_latency_ms", "avg")),
                    ],
                    [
                        "server post-view",
                        metric(target_gap, "server_post_view_ms", "avg"),
                        percent_of(metric(target_gap, "server_post_view_ms", "avg"), metric(target_gap, "client_latency_ms", "avg")),
                    ],
                    [
                        "view unattributed",
                        metric(target_gap, "view_unattributed_ms", "avg"),
                        percent_of(metric(target_gap, "view_unattributed_ms", "avg"), metric(target_gap, "client_latency_ms", "avg")),
                    ],
                    [
                        "service unattributed",
                        metric(target_gap, "service_unattributed_ms", "avg"),
                        percent_of(metric(target_gap, "service_unattributed_ms", "avg"), metric(target_gap, "client_latency_ms", "avg")),
                    ],
                    ["largest", unattr_ms, unattr_pct],
                ],
            )
        )
        docker_rows = docker_usage_rows(report)
        if docker_rows:
            lines.extend(["", "**Docker Usage Across This Matrix Run**", ""])
            lines.extend(
                markdown_table(
                    [
                        "container",
                        "samples",
                        "cpu_min",
                        "cpu_avg",
                        "cpu_max",
                        "cpu_p95",
                        "mem_min",
                        "mem_avg",
                        "mem_max",
                        "mem_p95",
                    ],
                    docker_rows,
                )
            )

    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="mode", required=True)

    accurate = subparsers.add_parser("accurate")
    accurate.add_argument("--json-report", required=True)
    accurate.add_argument("--output-md", required=True)
    accurate.add_argument("--run-metadata-json", default="")
    accurate.add_argument("--omit-source-paths", action="store_true")

    matrix = subparsers.add_parser("matrix")
    matrix.add_argument("--runs-manifest", required=True)
    matrix.add_argument("--output-md", required=True)
    matrix.add_argument("--preferred-concurrency", type=int, default=100)
    matrix.add_argument("--omit-source-paths", action="store_true")

    args = parser.parse_args()
    if args.mode == "accurate":
        report = load_json(args.json_report)
        metadata = load_json(args.run_metadata_json) if args.run_metadata_json else None
        write_accurate_readme(
            report,
            Path(args.output_md),
            json_report_path=args.json_report,
            metadata=metadata,
            include_source_paths=not args.omit_source_paths,
        )
        print(json.dumps({"output_md": args.output_md}, indent=2))
        return 0

    manifest = load_json(args.runs_manifest)
    write_matrix_readme(
        manifest,
        Path(args.output_md),
        preferred_concurrency=args.preferred_concurrency,
        include_source_paths=not args.omit_source_paths,
    )
    print(json.dumps({"output_md": args.output_md, "run_count": len(manifest.get("runs") or [])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

from typing import Any

from messenger_config.benchmark_timing import BenchmarkRequestTiming


_RECONCILIATION_TOLERANCE_US = 500

PRE_VIEW_WSGI_BOUNDARY_LOG_FIELDS = (
    "pre_view_wsgi_to_django_us",
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

POST_VIEW_WSGI_BOUNDARY_LOG_FIELDS = (
    "post_view_to_drf_finalize_entry_us",
    "drf_finalize_response_us",
    "drf_finalize_to_wsgi_start_response_us",
    "wsgi_start_response_to_app_return_us",
    "wsgi_app_return_to_response_iter_start_us",
    "wsgi_response_iter_us",
    "wsgi_after_response_complete_us",
    "post_view_unattributed_us",
    "post_view_boundary_reconciliation_delta_us",
)

THREAD_OBSERVATION_BOUNDARIES = (
    "server_entry",
    "django_wsgi_entry",
    "drf_dispatch_entry",
    "drf_initial_entry",
    "drf_initial_exit",
    "post_entry",
)


def duration_us(start_ns: int | None, end_ns: int | None) -> int | None:
    if start_ns is None or end_ns is None:
        return None
    return int((end_ns - start_ns) / 1_000)


def format_optional_us(value: int | None | str) -> str:
    return str(value) if value is not None else "-"


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
    return str(thread_id) if field == "id" else thread_name


def build_wsgi_boundary_fields(
    timing: BenchmarkRequestTiming,
) -> dict[str, int | None | str]:
    server_entry_ns = timing.server_entry_ns
    server_return_ns = timing.server_return_ns
    django_wsgi_entry_ns = timing.django_wsgi_entry_ns
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
    drf_finalize_entry_ns = timing.drf_finalize_response_entry_ns
    drf_finalize_exit_ns = timing.drf_finalize_response_exit_ns
    view_entry_ns = timing.view_entry_ns
    view_exit_ns = timing.view_exit_ns
    wsgi_start_response_ns = timing.wsgi_start_response_ns
    wsgi_app_return_ns = timing.wsgi_app_return_ns
    wsgi_response_iter_start_ns = timing.wsgi_response_iter_start_ns
    wsgi_response_complete_ns = timing.wsgi_response_complete_ns

    server_total_us = duration_us(server_entry_ns, server_return_ns)
    view_total_us = duration_us(view_entry_ns, view_exit_ns)
    server_pre_view_us = duration_us(server_entry_ns, view_entry_ns)
    server_post_view_us = duration_us(view_exit_ns, server_return_ns)

    pre_view_wsgi_to_django_us = duration_us(
        server_entry_ns,
        django_wsgi_entry_ns,
    )
    pre_view_django_to_middleware_us = duration_us(
        django_wsgi_entry_ns,
        django_middleware_entry_ns,
    )
    pre_view_middleware_to_drf_dispatch_us = duration_us(
        django_middleware_entry_ns,
        drf_dispatch_entry_ns,
    )
    pre_view_django_to_drf_dispatch_us = duration_us(
        django_wsgi_entry_ns,
        drf_dispatch_entry_ns,
    )
    drf_dispatch_pre_initialize_us = duration_us(
        drf_dispatch_entry_ns,
        drf_initialize_request_entry_ns,
    )
    drf_initialize_request_us = duration_us(
        drf_initialize_request_entry_ns,
        drf_initialize_request_exit_ns,
    )
    drf_dispatch_pre_initial_us = duration_us(
        drf_initialize_request_exit_ns,
        drf_initial_entry_ns,
    )
    drf_initial_total_us = duration_us(
        drf_initial_entry_ns,
        drf_initial_exit_ns,
    )
    drf_content_negotiation_us = duration_us(
        drf_content_negotiation_entry_ns,
        drf_content_negotiation_exit_ns,
    )
    drf_versioning_us = duration_us(
        drf_versioning_entry_ns,
        drf_versioning_exit_ns,
    )
    drf_authentication_total_us = duration_us(
        drf_authentication_entry_ns,
        drf_authentication_exit_ns,
    )
    drf_permission_us = duration_us(
        drf_permission_entry_ns,
        drf_permission_exit_ns,
    )
    drf_throttle_us = duration_us(
        drf_throttle_entry_ns,
        drf_throttle_exit_ns,
    )
    drf_initial_to_post_us = duration_us(
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

    if (
        pre_view_django_to_middleware_us is not None
        and pre_view_middleware_to_drf_dispatch_us is not None
    ):
        pre_view_children = [
            pre_view_wsgi_to_django_us,
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
            pre_view_wsgi_to_django_us,
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

    post_view_to_drf_finalize_entry_us = duration_us(
        view_exit_ns,
        drf_finalize_entry_ns,
    )
    drf_finalize_response_us = duration_us(
        drf_finalize_entry_ns,
        drf_finalize_exit_ns,
    )
    drf_finalize_to_wsgi_start_response_us = duration_us(
        drf_finalize_exit_ns,
        wsgi_start_response_ns,
    )
    wsgi_start_response_to_app_return_us = duration_us(
        wsgi_start_response_ns,
        wsgi_app_return_ns,
    )
    wsgi_app_return_to_response_iter_start_us = duration_us(
        wsgi_app_return_ns,
        wsgi_response_iter_start_ns,
    )
    wsgi_response_iter_us = duration_us(
        wsgi_response_iter_start_ns,
        wsgi_response_complete_ns,
    )
    wsgi_after_response_complete_us = duration_us(
        wsgi_response_complete_ns,
        server_return_ns,
    )

    post_view_children = [
        post_view_to_drf_finalize_entry_us,
        drf_finalize_response_us,
        drf_finalize_to_wsgi_start_response_us,
        wsgi_start_response_to_app_return_us,
        wsgi_app_return_to_response_iter_start_us,
        wsgi_response_iter_us,
        wsgi_after_response_complete_us,
    ]
    post_view_unattributed_us = _derived_delta_us(
        server_post_view_us,
        post_view_children,
    )
    post_view_boundary_reconciliation_delta_us = None
    if post_view_unattributed_us is not None:
        post_view_boundary_reconciliation_delta_us = _derived_delta_us(
            server_post_view_us,
            post_view_children + [post_view_unattributed_us],
        )

    server_boundary_reconciliation_delta_us = None
    if (
        server_total_us is not None
        and server_pre_view_us is not None
        and view_total_us is not None
        and server_post_view_us is not None
    ):
        server_boundary_reconciliation_delta_us = server_total_us - (
            server_pre_view_us + view_total_us + server_post_view_us
        )

    server_outside_view_reconciliation_delta_us = None
    if (
        server_total_us is not None
        and view_total_us is not None
        and server_pre_view_us is not None
        and server_post_view_us is not None
    ):
        server_outside_view_reconciliation_delta_us = (
            server_total_us - view_total_us
        ) - (server_pre_view_us + server_post_view_us)

    for field_name, value in {
        "server_pre_view_us": server_pre_view_us,
        "view_total_us": view_total_us,
        "server_post_view_us": server_post_view_us,
        "pre_view_wsgi_to_django_us": pre_view_wsgi_to_django_us,
        "pre_view_django_to_middleware_us": pre_view_django_to_middleware_us,
        "pre_view_middleware_to_drf_dispatch_us": pre_view_middleware_to_drf_dispatch_us,
        "drf_dispatch_pre_initialize_us": drf_dispatch_pre_initialize_us,
        "drf_initialize_request_us": drf_initialize_request_us,
        "drf_dispatch_pre_initial_us": drf_dispatch_pre_initial_us,
        "drf_initial_total_us": drf_initial_total_us,
        "drf_initial_to_post_us": drf_initial_to_post_us,
        "post_view_to_drf_finalize_entry_us": post_view_to_drf_finalize_entry_us,
        "drf_finalize_response_us": drf_finalize_response_us,
        "drf_finalize_to_wsgi_start_response_us": drf_finalize_to_wsgi_start_response_us,
        "wsgi_start_response_to_app_return_us": wsgi_start_response_to_app_return_us,
        "wsgi_app_return_to_response_iter_start_us": wsgi_app_return_to_response_iter_start_us,
        "wsgi_response_iter_us": wsgi_response_iter_us,
        "wsgi_after_response_complete_us": wsgi_after_response_complete_us,
    }.items():
        if value is not None and value < -_RECONCILIATION_TOLERANCE_US:
            _add_warning(timing, f"NEGATIVE_{field_name}".upper())

    for code, value in (
        (
            "SERVER_BOUNDARY_RECONCILIATION_FAILED",
            server_boundary_reconciliation_delta_us,
        ),
        (
            "SERVER_OUTSIDE_VIEW_RECONCILIATION_FAILED",
            server_outside_view_reconciliation_delta_us,
        ),
        (
            "PRE_VIEW_BOUNDARY_RECONCILIATION_FAILED",
            pre_view_boundary_reconciliation_delta_us,
        ),
        (
            "DRF_INITIAL_RECONCILIATION_FAILED",
            drf_initial_reconciliation_delta_us,
        ),
        (
            "POST_VIEW_BOUNDARY_RECONCILIATION_FAILED",
            post_view_boundary_reconciliation_delta_us,
        ),
    ):
        if value is not None and abs(value) > _RECONCILIATION_TOLERANCE_US:
            _add_warning(timing, code)

    if view_entry_ns is not None:
        for required_name, required_value in {
            "django_wsgi_entry": django_wsgi_entry_ns,
            "drf_dispatch_entry": drf_dispatch_entry_ns,
            "drf_initialize_request_entry": drf_initialize_request_entry_ns,
            "drf_initialize_request_exit": drf_initialize_request_exit_ns,
            "drf_initial_entry": drf_initial_entry_ns,
            "drf_initial_exit": drf_initial_exit_ns,
            "drf_finalize_response_entry": drf_finalize_entry_ns,
            "drf_finalize_response_exit": drf_finalize_exit_ns,
            "wsgi_start_response": wsgi_start_response_ns,
            "wsgi_app_return": wsgi_app_return_ns,
            "wsgi_response_iter_start": wsgi_response_iter_start_ns,
            "wsgi_response_complete": wsgi_response_complete_ns,
        }.items():
            if required_value is None:
                _add_warning(
                    timing,
                    f"MISSING_REQUIRED_{required_name}".upper(),
                )

    fields: dict[str, int | None | str] = {
        "timing_mode": "wsgi",
        "wsgi_timing_total_us": server_total_us,
        "view_entry_us": duration_us(server_entry_ns, view_entry_ns),
        "view_exit_us": duration_us(server_entry_ns, view_exit_ns),
        "server_pre_view_us": server_pre_view_us,
        "view_total_us": view_total_us,
        "server_post_view_us": server_post_view_us,
        "pre_view_wsgi_to_django_us": pre_view_wsgi_to_django_us,
        "pre_view_django_to_middleware_us": pre_view_django_to_middleware_us,
        "pre_view_middleware_to_drf_dispatch_us": pre_view_middleware_to_drf_dispatch_us,
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
        "pre_view_boundary_reconciliation_delta_us": pre_view_boundary_reconciliation_delta_us,
        "drf_initial_reconciliation_delta_us": drf_initial_reconciliation_delta_us,
        "post_view_to_drf_finalize_entry_us": post_view_to_drf_finalize_entry_us,
        "drf_finalize_response_us": drf_finalize_response_us,
        "drf_finalize_to_wsgi_start_response_us": drf_finalize_to_wsgi_start_response_us,
        "wsgi_start_response_to_app_return_us": wsgi_start_response_to_app_return_us,
        "wsgi_app_return_to_response_iter_start_us": wsgi_app_return_to_response_iter_start_us,
        "wsgi_response_iter_us": wsgi_response_iter_us,
        "wsgi_after_response_complete_us": wsgi_after_response_complete_us,
        "post_view_unattributed_us": post_view_unattributed_us,
        "post_view_boundary_reconciliation_delta_us": post_view_boundary_reconciliation_delta_us,
        "server_boundary_reconciliation_delta_us": server_boundary_reconciliation_delta_us,
        "server_outside_view_reconciliation_delta_us": server_outside_view_reconciliation_delta_us,
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

#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def install_benchmark_import_stubs() -> None:
    httpx = types.ModuleType("httpx")
    httpx.AsyncClient = object
    httpx.Limits = object
    httpx.Timeout = object
    httpx.Response = object
    sys.modules.setdefault("httpx", httpx)

    cryptography = types.ModuleType("cryptography")
    hazmat = types.ModuleType("cryptography.hazmat")
    primitives = types.ModuleType("cryptography.hazmat.primitives")
    hashes = types.ModuleType("cryptography.hazmat.primitives.hashes")
    serialization = types.ModuleType("cryptography.hazmat.primitives.serialization")
    asymmetric = types.ModuleType("cryptography.hazmat.primitives.asymmetric")
    x25519 = types.ModuleType("cryptography.hazmat.primitives.asymmetric.x25519")
    ciphers = types.ModuleType("cryptography.hazmat.primitives.ciphers")
    aead = types.ModuleType("cryptography.hazmat.primitives.ciphers.aead")
    kdf = types.ModuleType("cryptography.hazmat.primitives.kdf")
    hkdf = types.ModuleType("cryptography.hazmat.primitives.kdf.hkdf")

    class Dummy:
        pass

    hashes.SHA256 = Dummy
    serialization.Encoding = Dummy
    serialization.PublicFormat = Dummy
    x25519.X25519PrivateKey = Dummy
    x25519.X25519PublicKey = Dummy
    aead.AESGCM = Dummy
    hkdf.HKDF = Dummy

    for module in (
        cryptography,
        hazmat,
        primitives,
        hashes,
        serialization,
        asymmetric,
        x25519,
        ciphers,
        aead,
        kdf,
        hkdf,
    ):
        sys.modules.setdefault(module.__name__, module)


install_benchmark_import_stubs()
benchmark = load_module(
    "myna_benchmark",
    ROOT / "messenger/api_tests/full_api_flow/myna_distributed_pairs_latency_benchmark_test.py",
)
comparison = load_module(
    "build_asgi_http_tuning_comparison_report",
    ROOT / "scripts/build-asgi-http-tuning-comparison-report.py",
)
gap_analysis = load_module(
    "analyze_benchmark_request_gaps",
    ROOT / "scripts/analyze-benchmark-request-gaps.py",
)
readme_report = load_module(
    "build_benchmark_readme_report",
    ROOT / "scripts/build-benchmark-readme-report.py",
)


class BenchmarkThroughputTests(unittest.TestCase):
    def test_failed_requests_do_not_inflate_successful_message_throughput(self):
        summary = {
            "total_messages": 100,
            "success_count": 15,
            "failure_count": 85,
        }
        benchmark.add_throughput_metrics(summary, elapsed_ms=1405.64)

        self.assertAlmostEqual(summary["offered_requests_per_second"], 71.14)
        self.assertAlmostEqual(summary["completed_requests_per_second"], 71.14)
        self.assertAlmostEqual(summary["successful_messages_per_second"], 10.67)
        self.assertAlmostEqual(summary["failed_requests_per_second"], 60.47)
        self.assertEqual(summary["messages_per_second"], summary["successful_messages_per_second"])
        self.assertEqual(summary["messages_per_second_semantics"], "successful_messages_per_second")


class DiagnosticTimingTests(unittest.TestCase):
    def test_gap_analysis_derives_honest_server_and_unattributed_metrics(self):
        report = {
            "benchmark": {
                "per_level": [
                    {
                        "concurrency": 10,
                        "total_messages": 1,
                        "success_count": 1,
                        "failure_count": 0,
                        "messages_per_second": 20,
                        "request_records": [
                            {
                                "benchmark_request_id": "req-1",
                                "latency_ms": 120,
                                "ok": True,
                                "client_to_response_headers_ms": 110,
                                "client_response_body_read_ms": 10,
                                "server_timing_ms": {
                                    "auth_jwt_ms": 2,
                                    "view_total": 60,
                                    "view_serializer_validation": 5,
                                    "view_authenticated_user": 1,
                                    "view_payload_prepare": 2,
                                    "view_recipient_resolution": 3,
                                    "view_service_call": 40,
                                    "view_response_build": 4,
                                    "service_total": 30,
                                    "service_validate_input": 2,
                                    "service_policy_snapshot": 0,
                                    "service_existing_room_validation": 0,
                                    "service_device_lookup": 4,
                                    "service_room_validation": 3,
                                    "service_contact_state_upsert": 0,
                                    "service_reply_lookup": 0,
                                    "service_message_insert": 5,
                                    "service_attachment_validation": 0,
                                    "service_key_envelope_bulk_insert": 6,
                                    "service_receipt_decision_insert": 0,
                                    "service_room_update": 2,
                                    "service_realtime_outbox_persist": 5,
                                    "db_query_count": 7,
                                    "db_query_total_ms": 18,
                                    "db_query_select_count": 3,
                                    "db_query_insert_count": 2,
                                    "db_query_update_count": 1,
                                    "db_query_delete_count": 0,
                                    "db_query_other_count": 1,
                                    "db_connection_ensure_ms": 0.4,
                                    "db_connection_was_present_before_ensure": 1,
                                    "recipient_resolution_db_query_count": 1,
                                    "recipient_resolution_db_query_total_ms": 2,
                                    "recipient_resolution_db_query_select_count": 1,
                                    "recipient_resolution_db_query_insert_count": 0,
                                    "recipient_resolution_db_query_update_count": 0,
                                    "recipient_resolution_db_query_delete_count": 0,
                                    "recipient_resolution_db_query_other_count": 0,
                                    "direct_send_db_query_count": 5,
                                    "direct_send_db_query_total_ms": 13,
                                    "direct_send_db_query_select_count": 2,
                                    "direct_send_db_query_insert_count": 2,
                                    "direct_send_db_query_update_count": 1,
                                    "direct_send_db_query_delete_count": 0,
                                    "direct_send_db_query_other_count": 0,
                                    "outbox_db_query_count": 2,
                                    "outbox_db_query_total_ms": 5,
                                    "outbox_db_query_select_count": 1,
                                    "outbox_db_query_insert_count": 1,
                                    "outbox_db_query_update_count": 0,
                                    "outbox_db_query_delete_count": 0,
                                    "outbox_db_query_other_count": 0,
                                },
                            }
                        ],
                    }
                ]
            }
        }
        analyzed = gap_analysis.analyze(
            report,
            {
                "req-1": {
                    "duration_us": 100_000,
                    "response_start_us": "90_000".replace("_", ""),
                    "response_complete_us": "95_000".replace("_", ""),
                    "view_entry_us": "10_000".replace("_", ""),
                    "view_exit_us": "70_000".replace("_", ""),
                    "server_pre_view_us": "10_000".replace("_", ""),
                    "view_total_us": "60_000".replace("_", ""),
                    "server_post_view_us": "30_000".replace("_", ""),
                    "pre_view_asgi_to_django_us": "100",
                    "pre_view_django_to_middleware_us": "900",
                    "pre_view_middleware_to_drf_dispatch_us": "2600",
                    "pre_view_django_to_drf_dispatch_us": "3500",
                    "drf_dispatch_pre_initialize_us": "100",
                    "drf_initialize_request_us": "200",
                    "drf_dispatch_pre_initial_us": "100",
                    "drf_initial_total_us": "4000",
                    "drf_content_negotiation_us": "500",
                    "drf_versioning_us": "100",
                    "drf_authentication_total_us": "2000",
                    "drf_permission_us": "300",
                    "drf_throttle_us": "100",
                    "drf_initial_unattributed_us": "1000",
                    "drf_initial_to_post_us": "2000",
                    "pre_view_unattributed_us": "0",
                    "pre_view_boundary_reconciliation_delta_us": "0",
                    "drf_initial_reconciliation_delta_us": "0",
                    "post_view_to_response_start_us": "20_000".replace("_", ""),
                    "response_send_us": "5_000".replace("_", ""),
                    "asgi_after_response_complete_us": "5_000".replace("_", ""),
                    "server_boundary_reconciliation_delta_us": "0",
                    "server_outside_view_reconciliation_delta_us": "0",
                    "instrumentation_warning_count": "0",
                    "thread_server_entry_id": "1",
                    "thread_server_entry_name": "MainThread",
                    "thread_django_asgi_entry_id": "1",
                    "thread_django_asgi_entry_name": "MainThread",
                    "thread_drf_dispatch_entry_id": "2",
                    "thread_drf_dispatch_entry_name": "myna-asgi_0",
                    "thread_drf_initial_entry_id": "2",
                    "thread_drf_initial_entry_name": "myna-asgi_0",
                    "thread_drf_initial_exit_id": "2",
                    "thread_drf_initial_exit_name": "myna-asgi_0",
                    "thread_post_entry_id": "2",
                    "thread_post_entry_name": "myna-asgi_0",
                    "timestamp_epoch": 1.0,
                }
            },
            {},
            {},
        )

        row = analyzed["per_level"][0]
        self.assertEqual(row["server_total_ms"]["avg"], 100)
        self.assertEqual(row["client_outside_server_ms"]["avg"], 20)
        self.assertEqual(row["server_outside_view_ms"]["avg"], 40)
        self.assertEqual(row["server_pre_view_ms"]["avg"], 10)
        self.assertEqual(row["server_post_view_ms"]["avg"], 30)
        self.assertEqual(row["post_view_to_response_start_ms"]["avg"], 20)
        self.assertEqual(row["response_send_ms"]["avg"], 5)
        self.assertEqual(row["asgi_after_response_complete_ms"]["avg"], 5)
        self.assertEqual(row["pre_view_asgi_to_django_ms"]["avg"], 0.1)
        self.assertEqual(row["pre_view_django_to_middleware_ms"]["avg"], 0.9)
        self.assertEqual(row["pre_view_middleware_to_drf_dispatch_ms"]["avg"], 2.6)
        self.assertEqual(row["drf_initial_total_ms"]["avg"], 4)
        self.assertEqual(row["drf_authentication_total_ms"]["avg"], 2)
        self.assertEqual(row["drf_authentication_unattributed_ms"]["avg"], 0)
        self.assertEqual(row["pre_view_unattributed_ms"]["avg"], 0)
        self.assertEqual(row["pre_view_boundary_reconciliation_delta_ms"]["avg"], 0)
        self.assertEqual(row["drf_initial_reconciliation_delta_ms"]["avg"], 0)
        self.assertEqual(row["dominant_pre_view_region"], "DRF initial total")
        self.assertEqual(row["dominant_pre_view_region_avg_ms"], 4)
        self.assertEqual(row["dominant_pre_view_region_percent_of_pre_view"], 40)
        self.assertEqual(
            row["thread_context_observations"]["thread_identity_change"][
                "django_asgi_entry->drf_dispatch_entry"
            ]["changed_percent"],
            100,
        )
        self.assertEqual(row["server_boundary_reconciliation_delta_ms"]["avg"], 0)
        self.assertEqual(row["server_outside_view_reconciliation_delta_ms"]["avg"], 0)
        self.assertEqual(row["dominant_outside_view_region"], "server post-view")
        self.assertEqual(
            row["request_gap_records"][0]["server_post_view_ms"],
            30,
        )
        self.assertEqual(row["view_unattributed_ms"]["avg"], 5)
        self.assertEqual(row["service_unattributed_ms"]["avg"], 3)
        self.assertEqual(row["db_query_total_ms"]["avg"], 18)
        self.assertEqual(row["db_query_select_count"]["avg"], 3)
        self.assertEqual(row["db_connection_ensure_ms"]["avg"], 0.4)
        self.assertEqual(row["recipient_resolution_db_query_total_ms"]["avg"], 2)
        self.assertEqual(row["outbox_db_query_insert_count"]["avg"], 1)
        self.assertEqual(analyzed["reconciliation_warning_count"], 0)

    def test_old_gap_analysis_without_pre_view_sublayers_remains_compatible(self):
        report = {
            "benchmark": {
                "per_level": [
                    {
                        "concurrency": 100,
                        "total_messages": 1,
                        "success_count": 1,
                        "failure_count": 0,
                        "request_records": [
                            {
                                "benchmark_request_id": "old-req",
                                "latency_ms": 20,
                                "ok": True,
                                "server_timing_ms": {"view_total": 5},
                            }
                        ],
                    }
                ]
            }
        }

        analyzed = gap_analysis.analyze(
            report,
            {
                "old-req": {
                    "duration_us": "10_000".replace("_", ""),
                    "server_pre_view_us": "2_000".replace("_", ""),
                    "view_total_us": "5_000".replace("_", ""),
                    "server_post_view_us": "3_000".replace("_", ""),
                    "server_boundary_reconciliation_delta_us": "0",
                    "server_outside_view_reconciliation_delta_us": "0",
                    "instrumentation_warning_count": "0",
                }
            },
            {},
            {},
        )

        row = analyzed["per_level"][0]
        self.assertEqual(row["server_pre_view_ms"]["avg"], 2)
        self.assertEqual(row["dominant_pre_view_region"], "unavailable")
        self.assertNotIn("pre_view_asgi_to_django_ms", row)

    def test_percentile_summary_includes_full_distribution(self):
        summary = gap_analysis.summary([1, 2, 3, 4])

        self.assertEqual(summary["p50"], 2.5)
        self.assertEqual(summary["p75"], 3.25)
        self.assertEqual(summary["p90"], 3.7)
        self.assertEqual(summary["p95"], 3.85)
        self.assertEqual(summary["p99"], 3.97)


class DiagnosticReadmeTests(unittest.TestCase):
    def test_latency_decomposition_excludes_cross_cutting_db_total(self):
        row = {
            "client_latency_ms": {"avg": 120, "p50": 110, "p95": 150, "p99": 170},
            "server_total_ms": {"avg": 100},
            "client_outside_server_ms": {"avg": 20},
            "server_outside_view_ms": {"avg": 20},
            "view_total_ms": {"avg": 80},
            "request_parse_validation_ms": {"avg": 5},
            "view_recipient_resolution_ms": {"avg": 4},
            "view_service_call_ms": {"avg": 60},
            "view_unattributed_ms": {"avg": 11},
            "recovery_total_ms": {"avg": 55},
            "recovery_base_send_total_ms": {"avg": 45},
            "service_total_ms": {"avg": 40},
            "service_device_lookup_ms": {"avg": 6},
            "service_key_envelope_bulk_insert_ms": {"avg": 5},
            "service_realtime_outbox_persist_ms": {"avg": 6},
            "service_unattributed_ms": {"avg": 23},
            "db_query_total_ms": {"avg": 75},
        }

        rows = readme_report.latency_decomposition_rows(row)
        metrics = [item[1] for item in rows]

        self.assertNotIn("db_query_total_ms", metrics)
        self.assertIn("service_realtime_outbox_persist_ms", metrics)
        for item in rows:
            percent_of_parent = item[3]
            if percent_of_parent is not None:
                self.assertLessEqual(percent_of_parent, 100)

    def test_displayed_metrics_have_definitions_for_new_db_observations(self):
        definition_names = {
            definition.name
            for definition in readme_report.METRIC_DEFINITIONS
        }
        expected = {
            "db_connection_ensure_ms",
            "db_connection_was_present_before_ensure",
            "db_query_select_count",
            "db_query_insert_count",
            "recipient_resolution_db_query_total_ms",
            "direct_send_db_query_total_ms",
            "outbox_db_query_total_ms",
            "service_realtime_outbox_persist_ms",
            "recovery_base_send_total_ms",
            "service_device_lookup_ms",
            "server_pre_view_ms",
            "server_post_view_ms",
            "post_view_to_response_start_ms",
            "response_send_ms",
            "asgi_after_response_complete_ms",
            "server_boundary_reconciliation_delta_ms",
            "server_outside_view_reconciliation_delta_ms",
            "pre_view_asgi_to_django_ms",
            "pre_view_django_to_middleware_ms",
            "pre_view_middleware_to_drf_dispatch_ms",
            "drf_initial_total_ms",
            "drf_authentication_total_ms",
            "drf_permission_ms",
            "drf_throttle_ms",
            "pre_view_unattributed_ms",
            "pre_view_boundary_reconciliation_delta_ms",
            "drf_initial_reconciliation_delta_ms",
            "dominant_pre_view_region",
            "dominant_pre_view_region_avg_ms",
        }

        self.assertFalse(expected.difference(definition_names))

    def test_matrix_readme_contains_metric_definitions_and_decomposition(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            report = {
                "passed": True,
                "cleanup_success": True,
                "summary": {"failure_count": 0, "status_counts": {"201": 10}},
                "benchmark": {
                    "per_level": [
                        {
                            "concurrency": 100,
                            "total_messages": 10,
                            "success_count": 10,
                            "failure_count": 0,
                            "successful_messages_per_second": 50,
                        }
                    ]
                },
                "request_gap_analysis": {
                    "matched_request_count": 10,
                    "unmatched_request_count": 0,
                    "per_level": [
                        {
                            "concurrency": 100,
                            "success_count": 10,
                            "failure_count": 0,
                            "messages_per_second": 50,
                            "matched_request_count": 10,
                            "unmatched_request_count": 0,
                            "client_latency_ms": {"avg": 120, "p50": 110, "p95": 150, "p99": 170},
                            "server_total_ms": {"avg": 90, "p95": 120},
                            "client_outside_server_ms": {"avg": 30, "p95": 40},
                            "server_outside_view_ms": {"avg": 20, "p95": 30},
                            "server_pre_view_ms": {"avg": 8, "p50": 7, "p75": 8, "p90": 9, "p95": 10, "p99": 11, "max": 12},
                            "view_total_ms": {"avg": 70, "p50": 65, "p95": 95, "p99": 100},
                            "server_post_view_ms": {"avg": 12, "p50": 11, "p75": 12, "p90": 14, "p95": 15, "p99": 16, "max": 18},
                            "pre_view_asgi_to_django_ms": {"avg": 0.1, "p50": 0.1, "p75": 0.1, "p90": 0.1, "p95": 0.2, "p99": 0.3, "max": 0.3},
                            "pre_view_django_to_middleware_ms": {"avg": 1, "p50": 1, "p75": 1.1, "p90": 1.2, "p95": 1.3, "p99": 1.4, "max": 1.5},
                            "pre_view_middleware_to_drf_dispatch_ms": {"avg": 2, "p50": 2, "p75": 2.1, "p90": 2.2, "p95": 2.3, "p99": 2.4, "max": 2.5},
                            "pre_view_django_to_drf_dispatch_ms": {"avg": 3, "p50": 3, "p95": 3.5, "p99": 3.8},
                            "drf_dispatch_pre_initialize_ms": {"avg": 0.2, "p50": 0.2, "p95": 0.3, "p99": 0.4},
                            "drf_initialize_request_ms": {"avg": 0.4, "p50": 0.4, "p95": 0.5, "p99": 0.6},
                            "drf_dispatch_pre_initial_ms": {"avg": 0.1, "p50": 0.1, "p95": 0.2, "p99": 0.2},
                            "drf_initial_total_ms": {"avg": 3, "p50": 3, "p95": 4, "p99": 4.5},
                            "drf_content_negotiation_ms": {"avg": 0.2, "p50": 0.2, "p95": 0.3, "p99": 0.4},
                            "drf_versioning_ms": {"avg": 0.1, "p50": 0.1, "p95": 0.2, "p99": 0.2},
                            "drf_authentication_total_ms": {"avg": 1, "p50": 1, "p95": 1.3, "p99": 1.5},
                            "drf_permission_ms": {"avg": 0.2, "p50": 0.2, "p95": 0.3, "p99": 0.4},
                            "drf_throttle_ms": {"avg": 0.1, "p50": 0.1, "p95": 0.2, "p99": 0.2},
                            "drf_initial_unattributed_ms": {"avg": 1.4, "p50": 1.4, "p95": 1.7, "p99": 1.9},
                            "drf_initial_to_post_ms": {"avg": 1.2, "p50": 1.2, "p95": 1.4, "p99": 1.5},
                            "pre_view_unattributed_ms": {"avg": 0, "p50": 0, "p95": 0, "p99": 0},
                            "pre_view_boundary_reconciliation_delta_ms": {"avg": 0},
                            "drf_initial_reconciliation_delta_ms": {"avg": 0},
                            "dominant_pre_view_region": "DRF initial total",
                            "dominant_pre_view_region_avg_ms": 3,
                            "dominant_pre_view_region_percent_of_pre_view": 37.5,
                            "dominant_pre_view_region_percent_of_client": 2.5,
                            "thread_context_observations": {
                                "thread_identity_change": {
                                    "server_entry->django_asgi_entry": {"sample_count": 10, "changed_count": 0, "changed_percent": 0},
                                    "django_asgi_entry->drf_dispatch_entry": {"sample_count": 10, "changed_count": 10, "changed_percent": 100},
                                }
                            },
                            "post_view_to_response_start_ms": {"avg": 7, "p50": 6, "p95": 9, "p99": 10},
                            "response_send_ms": {"avg": 3, "p50": 3, "p95": 4, "p99": 5},
                            "asgi_after_response_complete_ms": {"avg": 2, "p50": 2, "p95": 3, "p99": 4},
                            "server_boundary_reconciliation_delta_ms": {"avg": 0},
                            "server_outside_view_reconciliation_delta_ms": {"avg": 0},
                            "dominant_outside_view_region": "server post-view",
                            "request_parse_validation_ms": {"avg": 5, "p50": 5, "p95": 8},
                            "view_service_call_ms": {"avg": 50, "p50": 45, "p95": 70},
                            "view_unattributed_ms": {"avg": 4, "p95": 6},
                            "service_total_ms": {"avg": 45, "p50": 40, "p95": 65},
                            "service_unattributed_ms": {"avg": 7, "p95": 10},
                            "db_query_count": {"avg": 8},
                            "db_query_total_ms": {"avg": 18, "p50": 16, "p95": 25},
                            "db_connection_ensure_ms": {"avg": 0.5, "p50": 0.4, "p95": 0.8},
                            "db_connection_was_present_before_ensure": {"avg": 1},
                            "db_query_select_count": {"avg": 3},
                            "db_query_insert_count": {"avg": 3},
                            "db_query_update_count": {"avg": 1},
                            "db_query_delete_count": {"avg": 0},
                            "db_query_other_count": {"avg": 1},
                            "recipient_resolution_db_query_count": {"avg": 1},
                            "recipient_resolution_db_query_total_ms": {"avg": 2, "p95": 3},
                            "recipient_resolution_db_query_select_count": {"avg": 1},
                            "direct_send_db_query_count": {"avg": 5},
                            "direct_send_db_query_total_ms": {"avg": 12, "p95": 18},
                            "direct_send_db_query_select_count": {"avg": 2},
                            "direct_send_db_query_insert_count": {"avg": 2},
                            "direct_send_db_query_update_count": {"avg": 1},
                            "outbox_db_query_count": {"avg": 2},
                            "outbox_db_query_total_ms": {"avg": 4, "p95": 6},
                            "outbox_db_query_select_count": {"avg": 1},
                            "outbox_db_query_insert_count": {"avg": 1},
                            "service_realtime_outbox_persist_ms": {"avg": 6, "p95": 9},
                        }
                    ],
                },
            }
            report_path = directory / "run.json"
            manifest_path = directory / "manifest.json"
            output_path = directory / "README.md"
            report_path.write_text(json.dumps(report), encoding="utf-8")
            manifest_path.write_text(
                json.dumps(
                    {
                        "runs": [
                            {
                                "run_label": "w8 t10",
                                "benchmark_succeeded": True,
                                "messenger_env": {
                                    "WEB_CONCURRENCY": "8",
                                    "ASGI_THREADS": "10",
                                    "GUNICORN_BACKLOG": "4096",
                                    "DB_CONN_MAX_AGE": "0",
                                },
                                "json_report_path": str(report_path),
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            readme_report.write_matrix_readme(
                json.loads(manifest_path.read_text(encoding="utf-8")),
                output_path,
            )

            markdown = output_path.read_text(encoding="utf-8")
            self.assertIn("## Metric Definitions", markdown)
            self.assertIn("server_outside_view_ms", markdown)
            self.assertIn("**Server Boundary Decomposition**", markdown)
            self.assertIn("**Post-View Decomposition**", markdown)
            self.assertIn("**Pre-View Decomposition**", markdown)
            self.assertIn("**DRF Initial Decomposition**", markdown)
            self.assertIn("dominant_pre_view_region", markdown)
            self.assertIn("DRF initial total", markdown)
            self.assertIn("server_pre_view_avg_ms", markdown)
            self.assertIn("dominant_outside_view_region", markdown)
            self.assertIn("server post-view is the dominant outside-view latency region", markdown)
            self.assertIn("response_send_ms", markdown)
            self.assertIn("**Latency Decomposition**", markdown)
            self.assertIn("**Database Metrics**", markdown)
            self.assertIn("**Database Operation Counts**", markdown)
            self.assertIn("**Stage-Attributed Database Timing**", markdown)
            self.assertNotIn("| DB query execution | db_query_total_ms |", markdown)

    def test_repeated_matrix_rows_aggregate_with_median_and_variability(self):
        rows = [
            {
                "eligible": True,
                "web_concurrency": "8",
                "asgi_threads": "10",
                "gunicorn_backlog": "4096",
                "db_conn_max_age": "0",
                "target_concurrency": 100,
                "client_p95_ms": 100,
                "client_p99_ms": 120,
                "client_avg_ms": 80,
                "msg_per_sec": 50,
                "server_pre_view_avg_ms": 30,
                "server_post_view_avg_ms": 10,
                "disqualification_reasons": [],
                "cleanup_success": True,
            },
            {
                "eligible": True,
                "web_concurrency": "8",
                "asgi_threads": "10",
                "gunicorn_backlog": "4096",
                "db_conn_max_age": "0",
                "target_concurrency": 100,
                "client_p95_ms": 140,
                "client_p99_ms": 170,
                "client_avg_ms": 90,
                "msg_per_sec": 45,
                "server_pre_view_avg_ms": 50,
                "server_post_view_avg_ms": 20,
                "disqualification_reasons": [],
                "cleanup_success": True,
            },
        ]

        aggregate = readme_report.aggregate_matrix_summaries(rows)[0]

        self.assertEqual(aggregate["run_count"], 2)
        self.assertEqual(aggregate["client_p95_ms"], 120)
        self.assertEqual(aggregate["server_pre_view_avg_ms"], 40)
        self.assertEqual(aggregate["server_post_view_avg_ms"], 15)
        self.assertEqual(aggregate["dominant_outside_view_region"], "server pre-view")
        self.assertGreater(aggregate["client_p95_cv_pct"], 0)
        self.assertTrue(aggregate["eligible"])


class MatrixRecommendationTests(unittest.TestCase):
    def write_report(self, directory: Path, name: str, *, failures: int, mps: float, client_avg: float) -> str:
        report = {
            "summary": {
                "failure_count": failures,
                "status_counts": {"201": 100 - failures, "500": failures},
            },
            "cleanup_success": True,
            "benchmark": {
                "per_level": [
                    {
                        "concurrency": 100,
                        "failure_count": failures,
                        "success_count": 100 - failures,
                        "successful_messages_per_second": mps,
                        "messages_per_second": mps,
                    }
                ]
            },
            "request_gap_analysis": {
                "per_level": [
                    {
                        "concurrency": 100,
                        "client_latency_ms": {"avg": client_avg},
                        "gunicorn_request_ms": {"avg": 50},
                        "client_or_network_gap_ms": {"avg": client_avg - 50},
                        "gunicorn_outside_view_ms": {"avg": 20},
                        "view_total_ms": {"avg": 30},
                        "service_total_ms": {"avg": 8},
                        "messages_per_second": mps,
                    }
                ]
            },
        }
        path = directory / f"{name}.json"
        path.write_text(json.dumps(report), encoding="utf-8")
        return str(path)

    def test_failed_high_throughput_row_cannot_win(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            failed = self.write_report(directory, "failed", failures=85, mps=71.14, client_avg=300)
            stable = self.write_report(directory, "stable", failures=0, mps=45.0, client_avg=500)
            rows = [
                comparison.summarize_run(
                    {
                        "run_label": "failed fast",
                        "benchmark_succeeded": False,
                        "messenger_env": {"WEB_CONCURRENCY": "6", "ASGI_THREADS": "16", "GUNICORN_BACKLOG": "4096"},
                        "json_report_path": failed,
                    }
                ),
                comparison.summarize_run(
                    {
                        "run_label": "stable",
                        "benchmark_succeeded": True,
                        "messenger_env": {"WEB_CONCURRENCY": "4", "ASGI_THREADS": "8", "GUNICORN_BACKLOG": "4096"},
                        "json_report_path": stable,
                    }
                ),
            ]

            eligible = [row for row in rows if row["eligible_for_recommendation"]]
            self.assertEqual(len(eligible), 1)
            self.assertEqual(eligible[0]["config_name"], "stable")
            self.assertIn("http_5xx_present", rows[0]["disqualification_reasons"])

    def test_all_failed_rows_have_no_valid_winner_and_diagnostic_baseline(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            first = self.write_report(directory, "first", failures=15, mps=10, client_avg=700)
            second = self.write_report(directory, "second", failures=85, mps=70, client_avg=300)
            rows = [
                comparison.summarize_run({"run_label": "first", "benchmark_succeeded": False, "messenger_env": {}, "json_report_path": first}),
                comparison.summarize_run({"run_label": "second", "benchmark_succeeded": False, "messenger_env": {}, "json_report_path": second}),
            ]

            self.assertFalse([row for row in rows if row["eligible_for_recommendation"]])
            self.assertEqual(comparison.lowest_failure_baseline(rows)["config_name"], "first")


if __name__ == "__main__":
    unittest.main()

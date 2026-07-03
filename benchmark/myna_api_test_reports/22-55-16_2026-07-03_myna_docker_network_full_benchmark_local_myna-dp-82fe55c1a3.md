# Myna Distributed-Pairs Latency Benchmark Report

**Result:** PASS  
**Run ID:** `myna-dp-82fe55c1a3`  
**Service URL mode:** `local`  
**Identity base URL:** `http://identity-service-local:5000`  
**Messenger base URL:** `http://messenger-service-local:8000`  
**Traffic mode:** `distributed_pairs`  
**Cleanup success:** `True`  
**Started at:** 2026-07-03T17:23:07.351132+00:00  
**Finished at:** 2026-07-03T17:25:16.808794+00:00  

## Configuration

```json
{
  "SERVICE_URL_MODE": "local",
  "IDENTITY_BASE_URL": "http://identity-service-local:5000",
  "MESSENGER_BASE_URL": "http://messenger-service-local:8000",
  "BENCHMARK_LEVELS": "1,5,10,20,30,40,50,60,70,80,90,100",
  "DISTRIBUTED_PAIR_COUNT": 100,
  "WARMUP_ALL_PAIRS": true,
  "REQUEST_TIMEOUT_SECONDS": 30.0,
  "SETUP_PAIR_CONCURRENCY": 1,
  "SETUP_PAIR_DELAY_SECONDS": 0.0,
  "BENCHMARK_COOLDOWN_SECONDS": 1.0,
  "STOP_ON_FIRST_FAILED_LEVEL": false,
  "DOCKER_STATS_ENABLED": false,
  "DOCKER_STATS_INTERVAL_SECONDS": 1.0,
  "CLEANUP_MESSENGER_DJANGO": false,
  "CLEANUP_IDENTITY_USERS": true,
  "CLEANUP_IDENTITY_DELAY_SECONDS": 0.0,
  "IDENTITY_BASE_URL_SOURCE": "MYNA_LOCAL_IDENTITY_BASE_URL/default",
  "MESSENGER_BASE_URL_SOURCE": "MYNA_LOCAL_MESSENGER_BASE_URL/default",
  "MESSENGER_DOCKER_CONTAINER": "messenger-service-local",
  "IDENTITY_DOCKER_CONTAINER": "identity-service-local",
  "REDIS_DOCKER_CONTAINER": "redis",
  "MYSQL_DOCKER_CONTAINER": "",
  "MESSENGER_PROJECT_ROOT": "/app",
  "DJANGO_SETTINGS_MODULE": "messenger_config.settings",
  "REPORT_DIR": "/reports/myna_api_test_reports",
  "REPORT_FILE_PREFIX": "myna_docker_network_full_benchmark",
  "REPORT_TIMEZONE": "Asia/Kolkata"
}
```

## Service Preflight

```json
{
  "mode": "local",
  "identity_base_url": "http://identity-service-local:5000",
  "messenger_base_url": "http://messenger-service-local:8000",
  "identity_base_url_source": "MYNA_LOCAL_IDENTITY_BASE_URL/default",
  "messenger_base_url_source": "MYNA_LOCAL_MESSENGER_BASE_URL/default",
  "identity": {
    "service": "identity",
    "base_url": "http://identity-service-local:5000",
    "health_url": "http://identity-service-local:5000/api/v1/health/",
    "ok": true,
    "status_code": 200,
    "latency_ms": 27.76,
    "response": {
      "data": {
        "component": "service",
        "latency_ms": 0.0,
        "message": "Identity Service service is running.",
        "status": "up"
      },
      "message": "Identity Service service is running.",
      "success": true
    }
  },
  "messenger": {
    "service": "messenger",
    "base_url": "http://messenger-service-local:8000",
    "health_url": "http://messenger-service-local:8000/api/v1/health/",
    "ok": true,
    "status_code": 200,
    "latency_ms": 19.45,
    "response": {
      "message": "Messenger service is running.",
      "service": "messenger-service",
      "environment": "local"
    }
  },
  "ok": true
}
```

## Runtime Environment

```json
{
  "python_process": {
    "platform": "linux",
    "executable": "/usr/local/bin/python",
    "cpu_count_seen_by_test_runner": 6,
    "meminfo": {
      "available": true,
      "mem_total_mb": 4918.73,
      "mem_available_mb": 2771.07,
      "swap_total_mb": 2048.0,
      "swap_free_mb": 2048.0
    }
  },
  "docker": {
    "service_url_mode": "local",
    "docker_version": {
      "ok": false,
      "error": "command not found: docker",
      "detail": "[Errno 2] No such file or directory: 'docker'"
    }
  }
}
```

## Setup

```json
{
  "pair_count": 100,
  "sender_user_ids_sample": [
    "1281",
    "1283",
    "1285",
    "1287",
    "1289",
    "1291",
    "1293",
    "1295",
    "1297",
    "1299"
  ],
  "recipient_user_ids_sample": [
    "1282",
    "1284",
    "1286",
    "1288",
    "1290",
    "1292",
    "1294",
    "1296",
    "1298",
    "1300"
  ],
  "docker_stats": {
    "enabled": false,
    "interval_seconds": 1.0,
    "container_names": [],
    "total_sample_rows": 0,
    "overall": {
      "sample_count": 0,
      "containers": {}
    },
    "by_phase": {}
  }
}
```

## Warmup

```json
{
  "total_messages": 100,
  "concurrency": "warmup",
  "success_count": 100,
  "failure_count": 0,
  "status_counts": {
    "201": 100
  },
  "unique_message_id_count": 100,
  "duplicate_message_id_count": 0,
  "unique_room_id_count": 100,
  "room_ids_sample": [
    "01549107-f761-465f-a139-e4b81d2b49ec",
    "01f4a2b5-84f1-43a6-a8e3-9c11c6804244",
    "06c0dfcb-15d4-430d-aeda-781bfd74150c",
    "07672fcd-a31c-4a1c-b067-0751e8b4f884",
    "0c973c64-62b8-473a-a50c-b33b02b0e57c",
    "0d6131f4-c64d-471f-a315-b030fc84e007",
    "0e942ca4-e3b0-43a4-ad7c-d8d2729827ce",
    "16dfc030-a47b-42cc-a216-6656d7d9deb6",
    "230b6b1b-b5f0-412a-adee-dc083693d7b3",
    "2d0091c9-6888-4202-bd7e-096dcfeabf9f",
    "2d0baf50-4764-46f1-947f-d41f25cf02df",
    "30c03a6d-d372-413e-8af4-2d401acc10ca",
    "3116d6e4-0adc-4d91-aa7a-ceb4f0b70ee3",
    "3217eda9-7093-4abf-a9f9-565ae8fc0597",
    "3a77aac4-4619-44e2-bfc8-46a023d3280a",
    "3b103137-18f5-45d1-a062-77c370078020",
    "3d2ac768-a439-437c-8e78-eb6e445d40c6",
    "40ecb577-c943-45a1-aa7b-b2694ade6b8a",
    "41e21054-ef27-47d5-ba44-c747090e311b",
    "44415f3e-1dd7-4d95-bd4a-16bf9f79282f"
  ],
  "latency_ms": {
    "min": 63.27,
    "max": 343.63,
    "avg": 186.6,
    "median": 200.73,
    "p95": 325.75
  },
  "server_timing_ms": {
    "recovery_base_send_total": {
      "min": 22.01,
      "max": 209.18,
      "avg": 71.99,
      "median": 78.16,
      "p95": 169.49
    },
    "recovery_bundle_check": {
      "min": 1.2,
      "max": 11.79,
      "avg": 4.26,
      "median": 3.84,
      "p95": 8.82
    },
    "recovery_envelope_bulk_insert": {
      "min": 0.01,
      "max": 0.07,
      "avg": 0.02,
      "median": 0.01,
      "p95": 0.03
    },
    "recovery_normalize_input": {
      "min": 0.0,
      "max": 0.0,
      "avg": 0.0,
      "median": 0.0,
      "p95": 0.0
    },
    "recovery_policy_snapshot": {
      "min": 0.97,
      "max": 12.02,
      "avg": 2.74,
      "median": 2.02,
      "p95": 6.23
    },
    "recovery_total": {
      "min": 25.2,
      "max": 214.95,
      "avg": 79.03,
      "median": 85.52,
      "p95": 178.1
    },
    "service_contact_state_upsert": {
      "min": 4.48,
      "max": 41.4,
      "avg": 15.47,
      "median": 16.23,
      "p95": 29.94
    },
    "service_device_lookup": {
      "min": 1.49,
      "max": 86.28,
      "avg": 5.55,
      "median": 3.8,
      "p95": 9.77
    },
    "service_key_envelope_bulk_insert": {
      "min": 0.69,
      "max": 79.45,
      "avg": 4.06,
      "median": 2.13,
      "p95": 8.75
    },
    "service_message_insert": {
      "min": 0.52,
      "max": 11.69,
      "avg": 2.53,
      "median": 1.81,
      "p95": 6.1
    },
    "service_policy_snapshot": {
      "min": 0.0,
      "max": 0.0,
      "avg": 0.0,
      "median": 0.0,
      "p95": 0.0
    },
    "service_receipt_decision_insert": {
      "min": 0.0,
      "max": 0.0,
      "avg": 0.0,
      "median": 0.0,
      "p95": 0.0
    },
    "service_reply_lookup": {
      "min": 0.0,
      "max": 0.04,
      "avg": 0.0,
      "median": 0.0,
      "p95": 0.0
    },
    "service_room_update": {
      "min": 0.61,
      "max": 8.03,
      "avg": 1.94,
      "median": 1.48,
      "p95": 5.18
    },
    "service_room_validation": {
      "min": 10.24,
      "max": 145.42,
      "avg": 35.87,
      "median": 33.12,
      "p95": 66.79
    },
    "service_total": {
      "min": 21.53,
      "max": 206.99,
      "avg": 68.95,
      "median": 74.87,
      "p95": 164.61
    },
    "service_validate_input": {
      "min": 0.06,
      "max": 0.74,
      "avg": 0.11,
      "median": 0.1,
      "p95": 0.15
    },
    "view_authenticated_user": {
      "min": 0.0,
      "max": 0.0,
      "avg": 0.0,
      "median": 0.0,
      "p95": 0.0
    },
    "view_payload_prepare": {
      "min": 0.0,
      "max": 0.01,
      "avg": 0.0,
      "median": 0.0,
      "p95": 0.01
    },
    "view_realtime_outbox_enqueue": {
      "min": 0.93,
      "max": 101.59,
      "avg": 6.6,
      "median": 3.79,
      "p95": 18.05
    },
    "view_recipient_resolution": {
      "min": 6.31,
      "max": 118.75,
      "avg": 14.89,
      "median": 12.4,
      "p95": 30.53
    },
    "view_response_build": {
      "min": 0.01,
      "max": 0.03,
      "avg": 0.01,
      "median": 0.01,
      "p95": 0.02
    },
    "view_serializer_validation": {
      "min": 0.74,
      "max": 75.55,
      "avg": 1.89,
      "median": 1.06,
      "p95": 1.52
    },
    "view_service_call": {
      "min": 33.52,
      "max": 242.12,
      "avg": 98.99,
      "median": 103.93,
      "p95": 224.24
    },
    "view_total": {
      "min": 42.17,
      "max": 268.63,
      "avg": 122.42,
      "median": 126.62,
      "p95": 247.82
    }
  },
  "failed_samples": [],
  "docker_stats": {
    "enabled": false,
    "interval_seconds": 1.0,
    "container_names": [],
    "total_sample_rows": 0,
    "overall": {
      "sample_count": 0,
      "containers": {}
    },
    "by_phase": {}
  }
}
```

## Benchmark Ladder

| Concurrency | Messages | Success | Failure | Unique rooms | Avg latency ms | P95 latency ms | Send elapsed ms | Messages/sec |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1 | 1 | 0 | 1 | 36.73 | 36.73 | 36.96 | 27.06 |
| 5 | 5 | 5 | 0 | 5 | 89.0 | 98.6 | 105.43 | 47.42 |
| 10 | 10 | 10 | 0 | 10 | 152.5 | 190.81 | 202.37 | 49.41 |
| 20 | 20 | 20 | 0 | 20 | 289.06 | 411.66 | 451.7 | 44.28 |
| 30 | 30 | 30 | 0 | 30 | 375.38 | 560.03 | 623.86 | 48.09 |
| 40 | 40 | 40 | 0 | 40 | 461.34 | 707.03 | 778.09 | 51.41 |
| 50 | 50 | 50 | 0 | 50 | 608.52 | 963.05 | 1068.64 | 46.79 |
| 60 | 60 | 60 | 0 | 60 | 733.43 | 1201.44 | 1300.8 | 46.13 |
| 70 | 70 | 70 | 0 | 70 | 837.54 | 1386.25 | 1536.05 | 45.57 |
| 80 | 80 | 80 | 0 | 80 | 997.47 | 1654.29 | 1821.03 | 43.93 |
| 90 | 90 | 90 | 0 | 90 | 1043.51 | 1722.27 | 1913.34 | 47.04 |
| 100 | 100 | 100 | 0 | 100 | 1219.98 | 2040.9 | 2217.32 | 45.1 |

## Benchmark Analysis

```json
{
  "available": true,
  "traffic_mode": "distributed_pairs",
  "baseline_concurrency": 1,
  "baseline_avg_latency_ms": 36.73,
  "baseline_p95_latency_ms": 36.73,
  "best_throughput_concurrency": 40,
  "best_throughput_messages_per_second": 51.41,
  "slowest_avg_latency_concurrency": 100,
  "slowest_avg_latency_ms": 1219.98,
  "slowest_p95_latency_concurrency": 100,
  "slowest_p95_latency_ms": 2040.9,
  "first_failure_concurrency": null,
  "first_avg_latency_2x_baseline_concurrency": 5,
  "first_p95_latency_over_3000_ms_concurrency": null
}
```

## Overall Summary

```json
{
  "total_messages": 556,
  "concurrency": "distributed_ladder",
  "success_count": 556,
  "failure_count": 0,
  "status_counts": {
    "201": 556
  },
  "unique_message_id_count": 556,
  "duplicate_message_id_count": 0,
  "unique_room_id_count": 100,
  "room_ids_sample": [
    "01549107-f761-465f-a139-e4b81d2b49ec",
    "01f4a2b5-84f1-43a6-a8e3-9c11c6804244",
    "06c0dfcb-15d4-430d-aeda-781bfd74150c",
    "07672fcd-a31c-4a1c-b067-0751e8b4f884",
    "0c973c64-62b8-473a-a50c-b33b02b0e57c",
    "0d6131f4-c64d-471f-a315-b030fc84e007",
    "0e942ca4-e3b0-43a4-ad7c-d8d2729827ce",
    "16dfc030-a47b-42cc-a216-6656d7d9deb6",
    "230b6b1b-b5f0-412a-adee-dc083693d7b3",
    "2d0091c9-6888-4202-bd7e-096dcfeabf9f",
    "2d0baf50-4764-46f1-947f-d41f25cf02df",
    "30c03a6d-d372-413e-8af4-2d401acc10ca",
    "3116d6e4-0adc-4d91-aa7a-ceb4f0b70ee3",
    "3217eda9-7093-4abf-a9f9-565ae8fc0597",
    "3a77aac4-4619-44e2-bfc8-46a023d3280a",
    "3b103137-18f5-45d1-a062-77c370078020",
    "3d2ac768-a439-437c-8e78-eb6e445d40c6",
    "40ecb577-c943-45a1-aa7b-b2694ade6b8a",
    "41e21054-ef27-47d5-ba44-c747090e311b",
    "44415f3e-1dd7-4d95-bd4a-16bf9f79282f"
  ],
  "latency_ms": {
    "min": 36.73,
    "max": 2175.61,
    "avg": 838.62,
    "median": 719.43,
    "p95": 1730.23
  },
  "server_timing_ms": {
    "recovery_base_send_total": {
      "min": 2.85,
      "max": 74.22,
      "avg": 10.64,
      "median": 8.8,
      "p95": 21.72
    },
    "recovery_bundle_check": {
      "min": 0.02,
      "max": 11.35,
      "avg": 1.55,
      "median": 1.55,
      "p95": 4.81
    },
    "recovery_envelope_bulk_insert": {
      "min": 0.01,
      "max": 0.09,
      "avg": 0.02,
      "median": 0.01,
      "p95": 0.04
    },
    "recovery_normalize_input": {
      "min": 0.0,
      "max": 0.06,
      "avg": 0.0,
      "median": 0.0,
      "p95": 0.0
    },
    "recovery_policy_snapshot": {
      "min": 0.05,
      "max": 7.31,
      "avg": 0.94,
      "median": 0.96,
      "p95": 2.81
    },
    "recovery_total": {
      "min": 2.98,
      "max": 80.96,
      "avg": 13.16,
      "median": 11.04,
      "p95": 27.88
    },
    "service_device_lookup": {
      "min": 0.05,
      "max": 11.31,
      "avg": 1.82,
      "median": 1.84,
      "p95": 5.82
    },
    "service_existing_room_validation": {
      "min": 0.0,
      "max": 0.06,
      "avg": 0.01,
      "median": 0.01,
      "p95": 0.01
    },
    "service_key_envelope_bulk_insert": {
      "min": 0.6,
      "max": 40.69,
      "avg": 1.94,
      "median": 1.16,
      "p95": 5.71
    },
    "service_message_insert": {
      "min": 0.56,
      "max": 50.54,
      "avg": 2.0,
      "median": 1.15,
      "p95": 5.95
    },
    "service_policy_snapshot": {
      "min": 0.0,
      "max": 0.0,
      "avg": 0.0,
      "median": 0.0,
      "p95": 0.0
    },
    "service_receipt_decision_insert": {
      "min": 0.0,
      "max": 0.0,
      "avg": 0.0,
      "median": 0.0,
      "p95": 0.0
    },
    "service_reply_lookup": {
      "min": 0.0,
      "max": 0.01,
      "avg": 0.0,
      "median": 0.0,
      "p95": 0.0
    },
    "service_room_update": {
      "min": 0.56,
      "max": 8.93,
      "avg": 1.33,
      "median": 1.04,
      "p95": 3.09
    },
    "service_room_validation": {
      "min": 0.0,
      "max": 0.0,
      "avg": 0.0,
      "median": 0.0,
      "p95": 0.0
    },
    "service_total": {
      "min": 2.53,
      "max": 68.11,
      "avg": 9.1,
      "median": 7.63,
      "p95": 18.35
    },
    "service_validate_input": {
      "min": 0.05,
      "max": 0.36,
      "avg": 0.1,
      "median": 0.09,
      "p95": 0.15
    },
    "view_authenticated_user": {
      "min": 0.0,
      "max": 0.03,
      "avg": 0.0,
      "median": 0.0,
      "p95": 0.0
    },
    "view_payload_prepare": {
      "min": 0.0,
      "max": 0.04,
      "avg": 0.0,
      "median": 0.0,
      "p95": 0.01
    },
    "view_realtime_outbox_enqueue": {
      "min": 0.85,
      "max": 16.16,
      "avg": 2.54,
      "median": 1.8,
      "p95": 6.56
    },
    "view_recipient_resolution": {
      "min": 6.97,
      "max": 41.16,
      "avg": 14.15,
      "median": 11.79,
      "p95": 27.19
    },
    "view_response_build": {
      "min": 0.01,
      "max": 0.08,
      "avg": 0.01,
      "median": 0.01,
      "p95": 0.03
    },
    "view_serializer_validation": {
      "min": 0.75,
      "max": 68.01,
      "avg": 1.29,
      "median": 1.05,
      "p95": 1.69
    },
    "view_service_call": {
      "min": 7.05,
      "max": 87.96,
      "avg": 19.48,
      "median": 16.98,
      "p95": 36.48
    },
    "view_total": {
      "min": 16.91,
      "max": 143.98,
      "avg": 37.51,
      "median": 32.21,
      "p95": 69.05
    }
  },
  "failed_samples": [],
  "benchmark_level_count": 12,
  "total_benchmark_messages": 556
}
```

## Server Timing Summary

```json
{
  "recovery_base_send_total": {
    "min": 2.85,
    "max": 74.22,
    "avg": 10.64,
    "median": 8.8,
    "p95": 21.72
  },
  "recovery_bundle_check": {
    "min": 0.02,
    "max": 11.35,
    "avg": 1.55,
    "median": 1.55,
    "p95": 4.81
  },
  "recovery_envelope_bulk_insert": {
    "min": 0.01,
    "max": 0.09,
    "avg": 0.02,
    "median": 0.01,
    "p95": 0.04
  },
  "recovery_normalize_input": {
    "min": 0.0,
    "max": 0.06,
    "avg": 0.0,
    "median": 0.0,
    "p95": 0.0
  },
  "recovery_policy_snapshot": {
    "min": 0.05,
    "max": 7.31,
    "avg": 0.94,
    "median": 0.96,
    "p95": 2.81
  },
  "recovery_total": {
    "min": 2.98,
    "max": 80.96,
    "avg": 13.16,
    "median": 11.04,
    "p95": 27.88
  },
  "service_device_lookup": {
    "min": 0.05,
    "max": 11.31,
    "avg": 1.82,
    "median": 1.84,
    "p95": 5.82
  },
  "service_existing_room_validation": {
    "min": 0.0,
    "max": 0.06,
    "avg": 0.01,
    "median": 0.01,
    "p95": 0.01
  },
  "service_key_envelope_bulk_insert": {
    "min": 0.6,
    "max": 40.69,
    "avg": 1.94,
    "median": 1.16,
    "p95": 5.71
  },
  "service_message_insert": {
    "min": 0.56,
    "max": 50.54,
    "avg": 2.0,
    "median": 1.15,
    "p95": 5.95
  },
  "service_policy_snapshot": {
    "min": 0.0,
    "max": 0.0,
    "avg": 0.0,
    "median": 0.0,
    "p95": 0.0
  },
  "service_receipt_decision_insert": {
    "min": 0.0,
    "max": 0.0,
    "avg": 0.0,
    "median": 0.0,
    "p95": 0.0
  },
  "service_reply_lookup": {
    "min": 0.0,
    "max": 0.01,
    "avg": 0.0,
    "median": 0.0,
    "p95": 0.0
  },
  "service_room_update": {
    "min": 0.56,
    "max": 8.93,
    "avg": 1.33,
    "median": 1.04,
    "p95": 3.09
  },
  "service_room_validation": {
    "min": 0.0,
    "max": 0.0,
    "avg": 0.0,
    "median": 0.0,
    "p95": 0.0
  },
  "service_total": {
    "min": 2.53,
    "max": 68.11,
    "avg": 9.1,
    "median": 7.63,
    "p95": 18.35
  },
  "service_validate_input": {
    "min": 0.05,
    "max": 0.36,
    "avg": 0.1,
    "median": 0.09,
    "p95": 0.15
  },
  "view_authenticated_user": {
    "min": 0.0,
    "max": 0.03,
    "avg": 0.0,
    "median": 0.0,
    "p95": 0.0
  },
  "view_payload_prepare": {
    "min": 0.0,
    "max": 0.04,
    "avg": 0.0,
    "median": 0.0,
    "p95": 0.01
  },
  "view_realtime_outbox_enqueue": {
    "min": 0.85,
    "max": 16.16,
    "avg": 2.54,
    "median": 1.8,
    "p95": 6.56
  },
  "view_recipient_resolution": {
    "min": 6.97,
    "max": 41.16,
    "avg": 14.15,
    "median": 11.79,
    "p95": 27.19
  },
  "view_response_build": {
    "min": 0.01,
    "max": 0.08,
    "avg": 0.01,
    "median": 0.01,
    "p95": 0.03
  },
  "view_serializer_validation": {
    "min": 0.75,
    "max": 68.01,
    "avg": 1.29,
    "median": 1.05,
    "p95": 1.69
  },
  "view_service_call": {
    "min": 7.05,
    "max": 87.96,
    "avg": 19.48,
    "median": 16.98,
    "p95": 36.48
  },
  "view_total": {
    "min": 16.91,
    "max": 143.98,
    "avg": 37.51,
    "median": 32.21,
    "p95": 69.05
  }
}
```

## Per-Level Server Timing

```json
[
  {
    "concurrency": 1,
    "server_timing_ms": {
      "recovery_base_send_total": {
        "min": 5.0,
        "max": 5.0,
        "avg": 5.0,
        "median": 5.0,
        "p95": 5.0
      },
      "recovery_bundle_check": {
        "min": 0.05,
        "max": 0.05,
        "avg": 0.05,
        "median": 0.05,
        "p95": 0.05
      },
      "recovery_envelope_bulk_insert": {
        "min": 0.02,
        "max": 0.02,
        "avg": 0.02,
        "median": 0.02,
        "p95": 0.02
      },
      "recovery_normalize_input": {
        "min": 0.0,
        "max": 0.0,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "recovery_policy_snapshot": {
        "min": 0.48,
        "max": 0.48,
        "avg": 0.48,
        "median": 0.48,
        "p95": 0.48
      },
      "recovery_total": {
        "min": 5.56,
        "max": 5.56,
        "avg": 5.56,
        "median": 5.56,
        "p95": 5.56
      },
      "service_device_lookup": {
        "min": 0.07,
        "max": 0.07,
        "avg": 0.07,
        "median": 0.07,
        "p95": 0.07
      },
      "service_existing_room_validation": {
        "min": 0.0,
        "max": 0.0,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "service_key_envelope_bulk_insert": {
        "min": 0.78,
        "max": 0.78,
        "avg": 0.78,
        "median": 0.78,
        "p95": 0.78
      },
      "service_message_insert": {
        "min": 2.01,
        "max": 2.01,
        "avg": 2.01,
        "median": 2.01,
        "p95": 2.01
      },
      "service_policy_snapshot": {
        "min": 0.0,
        "max": 0.0,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "service_receipt_decision_insert": {
        "min": 0.0,
        "max": 0.0,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "service_reply_lookup": {
        "min": 0.0,
        "max": 0.0,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "service_room_update": {
        "min": 0.71,
        "max": 0.71,
        "avg": 0.71,
        "median": 0.71,
        "p95": 0.71
      },
      "service_room_validation": {
        "min": 0.0,
        "max": 0.0,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "service_total": {
        "min": 4.39,
        "max": 4.39,
        "avg": 4.39,
        "median": 4.39,
        "p95": 4.39
      },
      "service_validate_input": {
        "min": 0.09,
        "max": 0.09,
        "avg": 0.09,
        "median": 0.09,
        "p95": 0.09
      },
      "view_authenticated_user": {
        "min": 0.0,
        "max": 0.0,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "view_payload_prepare": {
        "min": 0.0,
        "max": 0.0,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "view_realtime_outbox_enqueue": {
        "min": 1.2,
        "max": 1.2,
        "avg": 1.2,
        "median": 1.2,
        "p95": 1.2
      },
      "view_recipient_resolution": {
        "min": 11.17,
        "max": 11.17,
        "avg": 11.17,
        "median": 11.17,
        "p95": 11.17
      },
      "view_response_build": {
        "min": 0.01,
        "max": 0.01,
        "avg": 0.01,
        "median": 0.01,
        "p95": 0.01
      },
      "view_serializer_validation": {
        "min": 1.24,
        "max": 1.24,
        "avg": 1.24,
        "median": 1.24,
        "p95": 1.24
      },
      "view_service_call": {
        "min": 10.61,
        "max": 10.61,
        "avg": 10.61,
        "median": 10.61,
        "p95": 10.61
      },
      "view_total": {
        "min": 24.28,
        "max": 24.28,
        "avg": 24.28,
        "median": 24.28,
        "p95": 24.28
      }
    }
  },
  {
    "concurrency": 5,
    "server_timing_ms": {
      "recovery_base_send_total": {
        "min": 6.31,
        "max": 19.26,
        "avg": 10.08,
        "median": 7.77,
        "p95": 17.44
      },
      "recovery_bundle_check": {
        "min": 0.02,
        "max": 0.1,
        "avg": 0.04,
        "median": 0.03,
        "p95": 0.09
      },
      "recovery_envelope_bulk_insert": {
        "min": 0.01,
        "max": 0.04,
        "avg": 0.02,
        "median": 0.02,
        "p95": 0.04
      },
      "recovery_normalize_input": {
        "min": 0.0,
        "max": 0.0,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "recovery_policy_snapshot": {
        "min": 0.06,
        "max": 0.11,
        "avg": 0.08,
        "median": 0.07,
        "p95": 0.1
      },
      "recovery_total": {
        "min": 6.42,
        "max": 19.39,
        "avg": 10.24,
        "median": 7.97,
        "p95": 17.57
      },
      "service_device_lookup": {
        "min": 0.05,
        "max": 0.09,
        "avg": 0.07,
        "median": 0.07,
        "p95": 0.09
      },
      "service_existing_room_validation": {
        "min": 0.0,
        "max": 0.01,
        "avg": 0.01,
        "median": 0.01,
        "p95": 0.01
      },
      "service_key_envelope_bulk_insert": {
        "min": 0.77,
        "max": 9.79,
        "avg": 2.93,
        "median": 1.38,
        "p95": 8.13
      },
      "service_message_insert": {
        "min": 0.91,
        "max": 2.13,
        "avg": 1.44,
        "median": 1.4,
        "p95": 2.06
      },
      "service_policy_snapshot": {
        "min": 0.0,
        "max": 0.0,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "service_receipt_decision_insert": {
        "min": 0.0,
        "max": 0.0,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "service_reply_lookup": {
        "min": 0.0,
        "max": 0.0,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "service_room_update": {
        "min": 1.1,
        "max": 2.13,
        "avg": 1.5,
        "median": 1.39,
        "p95": 2.06
      },
      "service_room_validation": {
        "min": 0.0,
        "max": 0.0,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "service_total": {
        "min": 3.98,
        "max": 17.07,
        "avg": 8.15,
        "median": 6.29,
        "p95": 15.26
      },
      "service_validate_input": {
        "min": 0.05,
        "max": 0.1,
        "avg": 0.07,
        "median": 0.08,
        "p95": 0.1
      },
      "view_authenticated_user": {
        "min": 0.0,
        "max": 0.0,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "view_payload_prepare": {
        "min": 0.0,
        "max": 0.01,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.01
      },
      "view_realtime_outbox_enqueue": {
        "min": 1.01,
        "max": 4.09,
        "avg": 1.99,
        "median": 1.41,
        "p95": 3.74
      },
      "view_recipient_resolution": {
        "min": 13.52,
        "max": 23.29,
        "avg": 18.27,
        "median": 18.01,
        "p95": 22.57
      },
      "view_response_build": {
        "min": 0.01,
        "max": 0.02,
        "avg": 0.01,
        "median": 0.01,
        "p95": 0.02
      },
      "view_serializer_validation": {
        "min": 0.75,
        "max": 1.74,
        "avg": 1.12,
        "median": 0.95,
        "p95": 1.64
      },
      "view_service_call": {
        "min": 14.25,
        "max": 27.51,
        "avg": 17.8,
        "median": 15.31,
        "p95": 25.44
      },
      "view_total": {
        "min": 31.41,
        "max": 52.84,
        "avg": 39.22,
        "median": 34.54,
        "p95": 50.82
      }
    }
  },
  {
    "concurrency": 10,
    "server_timing_ms": {
      "recovery_base_send_total": {
        "min": 8.05,
        "max": 35.91,
        "avg": 15.41,
        "median": 13.62,
        "p95": 28.7
      },
      "recovery_bundle_check": {
        "min": 0.03,
        "max": 5.62,
        "avg": 1.52,
        "median": 0.05,
        "p95": 4.71
      },
      "recovery_envelope_bulk_insert": {
        "min": 0.01,
        "max": 0.05,
        "avg": 0.02,
        "median": 0.02,
        "p95": 0.04
      },
      "recovery_normalize_input": {
        "min": 0.0,
        "max": 0.01,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.01
      },
      "recovery_policy_snapshot": {
        "min": 0.11,
        "max": 2.57,
        "avg": 0.97,
        "median": 0.18,
        "p95": 2.52
      },
      "recovery_total": {
        "min": 10.35,
        "max": 36.07,
        "avg": 17.95,
        "median": 17.33,
        "p95": 29.87
      },
      "service_device_lookup": {
        "min": 0.06,
        "max": 3.83,
        "avg": 1.33,
        "median": 0.09,
        "p95": 3.79
      },
      "service_existing_room_validation": {
        "min": 0.0,
        "max": 0.01,
        "avg": 0.01,
        "median": 0.01,
        "p95": 0.01
      },
      "service_key_envelope_bulk_insert": {
        "min": 0.95,
        "max": 13.01,
        "avg": 4.18,
        "median": 2.79,
        "p95": 11.22
      },
      "service_message_insert": {
        "min": 0.88,
        "max": 13.96,
        "avg": 3.81,
        "median": 1.73,
        "p95": 11.08
      },
      "service_policy_snapshot": {
        "min": 0.0,
        "max": 0.0,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "service_receipt_decision_insert": {
        "min": 0.0,
        "max": 0.0,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "service_reply_lookup": {
        "min": 0.0,
        "max": 0.0,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "service_room_update": {
        "min": 0.9,
        "max": 2.72,
        "avg": 1.74,
        "median": 1.56,
        "p95": 2.68
      },
      "service_room_validation": {
        "min": 0.0,
        "max": 0.0,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "service_total": {
        "min": 6.99,
        "max": 34.14,
        "avg": 13.62,
        "median": 12.25,
        "p95": 26.46
      },
      "service_validate_input": {
        "min": 0.07,
        "max": 0.13,
        "avg": 0.11,
        "median": 0.11,
        "p95": 0.13
      },
      "view_authenticated_user": {
        "min": 0.0,
        "max": 0.0,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "view_payload_prepare": {
        "min": 0.0,
        "max": 0.01,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.01
      },
      "view_realtime_outbox_enqueue": {
        "min": 1.2,
        "max": 6.87,
        "avg": 2.83,
        "median": 2.74,
        "p95": 5.39
      },
      "view_recipient_resolution": {
        "min": 10.32,
        "max": 20.63,
        "avg": 15.72,
        "median": 15.67,
        "p95": 20.63
      },
      "view_response_build": {
        "min": 0.01,
        "max": 0.06,
        "avg": 0.02,
        "median": 0.01,
        "p95": 0.05
      },
      "view_serializer_validation": {
        "min": 0.98,
        "max": 1.34,
        "avg": 1.16,
        "median": 1.15,
        "p95": 1.32
      },
      "view_service_call": {
        "min": 14.96,
        "max": 43.84,
        "avg": 26.06,
        "median": 25.16,
        "p95": 38.31
      },
      "view_total": {
        "min": 30.57,
        "max": 58.89,
        "avg": 45.82,
        "median": 46.74,
        "p95": 57.98
      }
    }
  },
  {
    "concurrency": 20,
    "server_timing_ms": {
      "recovery_base_send_total": {
        "min": 7.08,
        "max": 23.3,
        "avg": 14.73,
        "median": 14.6,
        "p95": 21.67
      },
      "recovery_bundle_check": {
        "min": 0.03,
        "max": 8.51,
        "avg": 2.57,
        "median": 2.38,
        "p95": 7.89
      },
      "recovery_envelope_bulk_insert": {
        "min": 0.01,
        "max": 0.08,
        "avg": 0.03,
        "median": 0.02,
        "p95": 0.07
      },
      "recovery_normalize_input": {
        "min": 0.0,
        "max": 0.01,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "recovery_policy_snapshot": {
        "min": 0.06,
        "max": 4.62,
        "avg": 1.45,
        "median": 1.41,
        "p95": 3.14
      },
      "recovery_total": {
        "min": 8.11,
        "max": 30.98,
        "avg": 18.8,
        "median": 19.67,
        "p95": 29.67
      },
      "service_device_lookup": {
        "min": 0.06,
        "max": 6.99,
        "avg": 2.97,
        "median": 3.08,
        "p95": 6.7
      },
      "service_existing_room_validation": {
        "min": 0.0,
        "max": 0.01,
        "avg": 0.01,
        "median": 0.01,
        "p95": 0.01
      },
      "service_key_envelope_bulk_insert": {
        "min": 0.76,
        "max": 7.19,
        "avg": 2.56,
        "median": 1.55,
        "p95": 6.81
      },
      "service_message_insert": {
        "min": 0.85,
        "max": 6.99,
        "avg": 2.04,
        "median": 1.71,
        "p95": 3.06
      },
      "service_policy_snapshot": {
        "min": 0.0,
        "max": 0.0,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "service_receipt_decision_insert": {
        "min": 0.0,
        "max": 0.0,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "service_reply_lookup": {
        "min": 0.0,
        "max": 0.0,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "service_room_update": {
        "min": 0.91,
        "max": 2.9,
        "avg": 1.62,
        "median": 1.42,
        "p95": 2.79
      },
      "service_room_validation": {
        "min": 0.0,
        "max": 0.0,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "service_total": {
        "min": 3.81,
        "max": 20.91,
        "avg": 12.29,
        "median": 12.59,
        "p95": 18.39
      },
      "service_validate_input": {
        "min": 0.07,
        "max": 0.16,
        "avg": 0.11,
        "median": 0.11,
        "p95": 0.15
      },
      "view_authenticated_user": {
        "min": 0.0,
        "max": 0.0,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "view_payload_prepare": {
        "min": 0.0,
        "max": 0.01,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "view_realtime_outbox_enqueue": {
        "min": 1.21,
        "max": 7.29,
        "avg": 3.76,
        "median": 3.62,
        "p95": 6.08
      },
      "view_recipient_resolution": {
        "min": 10.48,
        "max": 41.16,
        "avg": 21.13,
        "median": 21.31,
        "p95": 30.14
      },
      "view_response_build": {
        "min": 0.01,
        "max": 0.05,
        "avg": 0.01,
        "median": 0.01,
        "p95": 0.02
      },
      "view_serializer_validation": {
        "min": 0.84,
        "max": 1.5,
        "avg": 1.12,
        "median": 1.12,
        "p95": 1.41
      },
      "view_service_call": {
        "min": 13.98,
        "max": 42.35,
        "avg": 26.33,
        "median": 26.19,
        "p95": 38.48
      },
      "view_total": {
        "min": 26.87,
        "max": 75.5,
        "avg": 52.4,
        "median": 52.09,
        "p95": 74.64
      }
    }
  },
  {
    "concurrency": 30,
    "server_timing_ms": {
      "recovery_base_send_total": {
        "min": 4.15,
        "max": 25.93,
        "avg": 10.56,
        "median": 10.1,
        "p95": 18.41
      },
      "recovery_bundle_check": {
        "min": 0.02,
        "max": 4.4,
        "avg": 1.03,
        "median": 0.04,
        "p95": 3.82
      },
      "recovery_envelope_bulk_insert": {
        "min": 0.01,
        "max": 0.06,
        "avg": 0.02,
        "median": 0.01,
        "p95": 0.03
      },
      "recovery_normalize_input": {
        "min": 0.0,
        "max": 0.01,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "recovery_policy_snapshot": {
        "min": 0.07,
        "max": 5.25,
        "avg": 0.84,
        "median": 0.12,
        "p95": 3.4
      },
      "recovery_total": {
        "min": 4.34,
        "max": 30.69,
        "avg": 12.47,
        "median": 12.01,
        "p95": 23.38
      },
      "service_device_lookup": {
        "min": 0.06,
        "max": 9.45,
        "avg": 1.43,
        "median": 0.08,
        "p95": 4.79
      },
      "service_existing_room_validation": {
        "min": 0.0,
        "max": 0.01,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.01
      },
      "service_key_envelope_bulk_insert": {
        "min": 0.72,
        "max": 10.6,
        "avg": 2.42,
        "median": 1.56,
        "p95": 6.47
      },
      "service_message_insert": {
        "min": 0.75,
        "max": 6.27,
        "avg": 1.74,
        "median": 1.06,
        "p95": 4.11
      },
      "service_policy_snapshot": {
        "min": 0.0,
        "max": 0.0,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "service_receipt_decision_insert": {
        "min": 0.0,
        "max": 0.0,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "service_reply_lookup": {
        "min": 0.0,
        "max": 0.0,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "service_room_update": {
        "min": 0.68,
        "max": 4.56,
        "avg": 1.52,
        "median": 1.29,
        "p95": 3.45
      },
      "service_room_validation": {
        "min": 0.0,
        "max": 0.0,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "service_total": {
        "min": 3.56,
        "max": 24.38,
        "avg": 9.07,
        "median": 8.7,
        "p95": 16.13
      },
      "service_validate_input": {
        "min": 0.07,
        "max": 0.15,
        "avg": 0.1,
        "median": 0.09,
        "p95": 0.14
      },
      "view_authenticated_user": {
        "min": 0.0,
        "max": 0.0,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "view_payload_prepare": {
        "min": 0.0,
        "max": 0.04,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.01
      },
      "view_realtime_outbox_enqueue": {
        "min": 1.02,
        "max": 6.03,
        "avg": 2.59,
        "median": 2.02,
        "p95": 5.51
      },
      "view_recipient_resolution": {
        "min": 8.14,
        "max": 27.19,
        "avg": 15.0,
        "median": 13.78,
        "p95": 23.57
      },
      "view_response_build": {
        "min": 0.01,
        "max": 0.04,
        "avg": 0.01,
        "median": 0.01,
        "p95": 0.04
      },
      "view_serializer_validation": {
        "min": 0.85,
        "max": 5.06,
        "avg": 1.28,
        "median": 1.12,
        "p95": 1.69
      },
      "view_service_call": {
        "min": 10.72,
        "max": 42.46,
        "avg": 18.79,
        "median": 17.63,
        "p95": 30.29
      },
      "view_total": {
        "min": 23.67,
        "max": 63.08,
        "avg": 37.71,
        "median": 35.62,
        "p95": 59.84
      }
    }
  },
  {
    "concurrency": 40,
    "server_timing_ms": {
      "recovery_base_send_total": {
        "min": 2.85,
        "max": 26.98,
        "avg": 10.33,
        "median": 8.96,
        "p95": 20.86
      },
      "recovery_bundle_check": {
        "min": 0.02,
        "max": 4.05,
        "avg": 0.63,
        "median": 0.03,
        "p95": 3.56
      },
      "recovery_envelope_bulk_insert": {
        "min": 0.01,
        "max": 0.07,
        "avg": 0.02,
        "median": 0.02,
        "p95": 0.04
      },
      "recovery_normalize_input": {
        "min": 0.0,
        "max": 0.02,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "recovery_policy_snapshot": {
        "min": 0.06,
        "max": 5.99,
        "avg": 0.65,
        "median": 0.09,
        "p95": 2.42
      },
      "recovery_total": {
        "min": 2.98,
        "max": 31.14,
        "avg": 11.65,
        "median": 9.31,
        "p95": 22.89
      },
      "service_device_lookup": {
        "min": 0.05,
        "max": 4.0,
        "avg": 0.7,
        "median": 0.07,
        "p95": 3.56
      },
      "service_existing_room_validation": {
        "min": 0.0,
        "max": 0.02,
        "avg": 0.01,
        "median": 0.01,
        "p95": 0.01
      },
      "service_key_envelope_bulk_insert": {
        "min": 0.63,
        "max": 11.38,
        "avg": 2.3,
        "median": 1.31,
        "p95": 7.54
      },
      "service_message_insert": {
        "min": 0.62,
        "max": 14.64,
        "avg": 2.46,
        "median": 1.25,
        "p95": 9.12
      },
      "service_policy_snapshot": {
        "min": 0.0,
        "max": 0.0,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "service_receipt_decision_insert": {
        "min": 0.0,
        "max": 0.0,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "service_reply_lookup": {
        "min": 0.0,
        "max": 0.0,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "service_room_update": {
        "min": 0.59,
        "max": 4.36,
        "avg": 1.47,
        "median": 1.3,
        "p95": 3.54
      },
      "service_room_validation": {
        "min": 0.0,
        "max": 0.0,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "service_total": {
        "min": 2.53,
        "max": 23.71,
        "avg": 8.91,
        "median": 7.53,
        "p95": 18.08
      },
      "service_validate_input": {
        "min": 0.07,
        "max": 0.18,
        "avg": 0.1,
        "median": 0.09,
        "p95": 0.16
      },
      "view_authenticated_user": {
        "min": 0.0,
        "max": 0.0,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "view_payload_prepare": {
        "min": 0.0,
        "max": 0.01,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.01
      },
      "view_realtime_outbox_enqueue": {
        "min": 0.97,
        "max": 7.94,
        "avg": 2.31,
        "median": 1.53,
        "p95": 6.54
      },
      "view_recipient_resolution": {
        "min": 8.02,
        "max": 28.49,
        "avg": 14.1,
        "median": 12.09,
        "p95": 25.84
      },
      "view_response_build": {
        "min": 0.01,
        "max": 0.04,
        "avg": 0.01,
        "median": 0.01,
        "p95": 0.02
      },
      "view_serializer_validation": {
        "min": 0.79,
        "max": 1.76,
        "avg": 1.1,
        "median": 1.04,
        "p95": 1.58
      },
      "view_service_call": {
        "min": 8.01,
        "max": 36.73,
        "avg": 17.45,
        "median": 14.91,
        "p95": 30.22
      },
      "view_total": {
        "min": 20.2,
        "max": 62.26,
        "avg": 35.01,
        "median": 30.03,
        "p95": 58.26
      }
    }
  },
  {
    "concurrency": 50,
    "server_timing_ms": {
      "recovery_base_send_total": {
        "min": 3.63,
        "max": 20.59,
        "avg": 8.83,
        "median": 8.06,
        "p95": 17.87
      },
      "recovery_bundle_check": {
        "min": 0.02,
        "max": 3.58,
        "avg": 0.75,
        "median": 0.04,
        "p95": 3.24
      },
      "recovery_envelope_bulk_insert": {
        "min": 0.01,
        "max": 0.05,
        "avg": 0.02,
        "median": 0.02,
        "p95": 0.03
      },
      "recovery_normalize_input": {
        "min": 0.0,
        "max": 0.0,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "recovery_policy_snapshot": {
        "min": 0.05,
        "max": 2.28,
        "avg": 0.48,
        "median": 0.11,
        "p95": 1.77
      },
      "recovery_total": {
        "min": 3.75,
        "max": 25.07,
        "avg": 10.09,
        "median": 8.41,
        "p95": 19.64
      },
      "service_device_lookup": {
        "min": 0.05,
        "max": 7.8,
        "avg": 1.07,
        "median": 0.07,
        "p95": 5.0
      },
      "service_existing_room_validation": {
        "min": 0.0,
        "max": 0.03,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.01
      },
      "service_key_envelope_bulk_insert": {
        "min": 0.61,
        "max": 8.44,
        "avg": 1.95,
        "median": 1.19,
        "p95": 5.72
      },
      "service_message_insert": {
        "min": 0.66,
        "max": 10.99,
        "avg": 1.87,
        "median": 1.19,
        "p95": 5.12
      },
      "service_policy_snapshot": {
        "min": 0.0,
        "max": 0.0,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "service_receipt_decision_insert": {
        "min": 0.0,
        "max": 0.0,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "service_reply_lookup": {
        "min": 0.0,
        "max": 0.0,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "service_room_update": {
        "min": 0.63,
        "max": 3.1,
        "avg": 1.28,
        "median": 1.11,
        "p95": 2.77
      },
      "service_room_validation": {
        "min": 0.0,
        "max": 0.0,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "service_total": {
        "min": 2.97,
        "max": 18.8,
        "avg": 7.74,
        "median": 7.52,
        "p95": 16.82
      },
      "service_validate_input": {
        "min": 0.06,
        "max": 0.15,
        "avg": 0.09,
        "median": 0.09,
        "p95": 0.13
      },
      "view_authenticated_user": {
        "min": 0.0,
        "max": 0.0,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "view_payload_prepare": {
        "min": 0.0,
        "max": 0.01,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "view_realtime_outbox_enqueue": {
        "min": 0.91,
        "max": 10.07,
        "avg": 2.15,
        "median": 1.39,
        "p95": 5.42
      },
      "view_recipient_resolution": {
        "min": 7.48,
        "max": 31.89,
        "avg": 12.88,
        "median": 11.02,
        "p95": 24.76
      },
      "view_response_build": {
        "min": 0.01,
        "max": 0.04,
        "avg": 0.01,
        "median": 0.01,
        "p95": 0.02
      },
      "view_serializer_validation": {
        "min": 0.83,
        "max": 1.54,
        "avg": 1.1,
        "median": 1.06,
        "p95": 1.39
      },
      "view_service_call": {
        "min": 8.94,
        "max": 30.82,
        "avg": 15.96,
        "median": 14.14,
        "p95": 27.76
      },
      "view_total": {
        "min": 19.4,
        "max": 63.17,
        "avg": 32.13,
        "median": 28.21,
        "p95": 54.68
      }
    }
  },
  {
    "concurrency": 60,
    "server_timing_ms": {
      "recovery_base_send_total": {
        "min": 3.53,
        "max": 23.91,
        "avg": 8.82,
        "median": 6.96,
        "p95": 21.25
      },
      "recovery_bundle_check": {
        "min": 0.02,
        "max": 4.65,
        "avg": 0.7,
        "median": 0.03,
        "p95": 3.93
      },
      "recovery_envelope_bulk_insert": {
        "min": 0.01,
        "max": 0.03,
        "avg": 0.02,
        "median": 0.02,
        "p95": 0.03
      },
      "recovery_normalize_input": {
        "min": 0.0,
        "max": 0.01,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "recovery_policy_snapshot": {
        "min": 0.07,
        "max": 3.16,
        "avg": 0.42,
        "median": 0.1,
        "p95": 1.76
      },
      "recovery_total": {
        "min": 3.67,
        "max": 29.02,
        "avg": 9.97,
        "median": 7.91,
        "p95": 22.85
      },
      "service_device_lookup": {
        "min": 0.05,
        "max": 8.2,
        "avg": 0.91,
        "median": 0.07,
        "p95": 5.63
      },
      "service_existing_room_validation": {
        "min": 0.0,
        "max": 0.02,
        "avg": 0.01,
        "median": 0.01,
        "p95": 0.01
      },
      "service_key_envelope_bulk_insert": {
        "min": 0.64,
        "max": 8.25,
        "avg": 1.78,
        "median": 1.1,
        "p95": 5.21
      },
      "service_message_insert": {
        "min": 0.66,
        "max": 9.04,
        "avg": 1.53,
        "median": 1.08,
        "p95": 3.74
      },
      "service_policy_snapshot": {
        "min": 0.0,
        "max": 0.0,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "service_receipt_decision_insert": {
        "min": 0.0,
        "max": 0.0,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "service_reply_lookup": {
        "min": 0.0,
        "max": 0.0,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "service_room_update": {
        "min": 0.56,
        "max": 4.79,
        "avg": 1.17,
        "median": 0.85,
        "p95": 2.71
      },
      "service_room_validation": {
        "min": 0.0,
        "max": 0.0,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "service_total": {
        "min": 3.0,
        "max": 20.94,
        "avg": 7.35,
        "median": 6.02,
        "p95": 16.14
      },
      "service_validate_input": {
        "min": 0.06,
        "max": 0.32,
        "avg": 0.11,
        "median": 0.09,
        "p95": 0.16
      },
      "view_authenticated_user": {
        "min": 0.0,
        "max": 0.02,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "view_payload_prepare": {
        "min": 0.0,
        "max": 0.01,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.01
      },
      "view_realtime_outbox_enqueue": {
        "min": 0.9,
        "max": 9.59,
        "avg": 2.07,
        "median": 1.63,
        "p95": 4.38
      },
      "view_recipient_resolution": {
        "min": 8.07,
        "max": 33.24,
        "avg": 13.24,
        "median": 11.72,
        "p95": 23.58
      },
      "view_response_build": {
        "min": 0.01,
        "max": 0.05,
        "avg": 0.01,
        "median": 0.01,
        "p95": 0.02
      },
      "view_serializer_validation": {
        "min": 0.8,
        "max": 1.79,
        "avg": 1.09,
        "median": 1.04,
        "p95": 1.47
      },
      "view_service_call": {
        "min": 7.56,
        "max": 36.39,
        "avg": 16.09,
        "median": 13.43,
        "p95": 29.62
      },
      "view_total": {
        "min": 19.43,
        "max": 71.9,
        "avg": 32.55,
        "median": 29.09,
        "p95": 57.58
      }
    }
  },
  {
    "concurrency": 70,
    "server_timing_ms": {
      "recovery_base_send_total": {
        "min": 3.63,
        "max": 45.23,
        "avg": 11.42,
        "median": 8.43,
        "p95": 26.37
      },
      "recovery_bundle_check": {
        "min": 0.02,
        "max": 8.76,
        "avg": 1.32,
        "median": 0.04,
        "p95": 5.44
      },
      "recovery_envelope_bulk_insert": {
        "min": 0.01,
        "max": 0.06,
        "avg": 0.02,
        "median": 0.01,
        "p95": 0.04
      },
      "recovery_normalize_input": {
        "min": 0.0,
        "max": 0.0,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "recovery_policy_snapshot": {
        "min": 0.05,
        "max": 3.72,
        "avg": 0.7,
        "median": 0.11,
        "p95": 2.43
      },
      "recovery_total": {
        "min": 3.78,
        "max": 45.38,
        "avg": 13.48,
        "median": 8.91,
        "p95": 29.64
      },
      "service_device_lookup": {
        "min": 0.05,
        "max": 11.31,
        "avg": 1.56,
        "median": 0.1,
        "p95": 5.76
      },
      "service_existing_room_validation": {
        "min": 0.0,
        "max": 0.01,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.01
      },
      "service_key_envelope_bulk_insert": {
        "min": 0.68,
        "max": 40.69,
        "avg": 2.95,
        "median": 1.06,
        "p95": 14.42
      },
      "service_message_insert": {
        "min": 0.63,
        "max": 8.47,
        "avg": 1.82,
        "median": 1.23,
        "p95": 5.86
      },
      "service_policy_snapshot": {
        "min": 0.0,
        "max": 0.0,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "service_receipt_decision_insert": {
        "min": 0.0,
        "max": 0.0,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "service_reply_lookup": {
        "min": 0.0,
        "max": 0.0,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "service_room_update": {
        "min": 0.58,
        "max": 6.77,
        "avg": 1.33,
        "median": 0.86,
        "p95": 3.88
      },
      "service_room_validation": {
        "min": 0.0,
        "max": 0.0,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "service_total": {
        "min": 3.03,
        "max": 44.13,
        "avg": 9.69,
        "median": 7.2,
        "p95": 23.06
      },
      "service_validate_input": {
        "min": 0.06,
        "max": 0.15,
        "avg": 0.09,
        "median": 0.09,
        "p95": 0.14
      },
      "view_authenticated_user": {
        "min": 0.0,
        "max": 0.03,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "view_payload_prepare": {
        "min": 0.0,
        "max": 0.0,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "view_realtime_outbox_enqueue": {
        "min": 1.0,
        "max": 10.77,
        "avg": 2.33,
        "median": 1.63,
        "p95": 6.13
      },
      "view_recipient_resolution": {
        "min": 7.58,
        "max": 36.06,
        "avg": 13.55,
        "median": 10.37,
        "p95": 27.42
      },
      "view_response_build": {
        "min": 0.01,
        "max": 0.06,
        "avg": 0.01,
        "median": 0.01,
        "p95": 0.03
      },
      "view_serializer_validation": {
        "min": 0.78,
        "max": 4.73,
        "avg": 1.18,
        "median": 1.03,
        "p95": 1.63
      },
      "view_service_call": {
        "min": 8.89,
        "max": 53.36,
        "avg": 19.88,
        "median": 15.31,
        "p95": 39.84
      },
      "view_total": {
        "min": 19.66,
        "max": 91.02,
        "avg": 36.98,
        "median": 28.94,
        "p95": 71.32
      }
    }
  },
  {
    "concurrency": 80,
    "server_timing_ms": {
      "recovery_base_send_total": {
        "min": 3.69,
        "max": 74.22,
        "avg": 12.44,
        "median": 9.77,
        "p95": 28.2
      },
      "recovery_bundle_check": {
        "min": 0.02,
        "max": 11.35,
        "avg": 2.09,
        "median": 1.8,
        "p95": 5.84
      },
      "recovery_envelope_bulk_insert": {
        "min": 0.01,
        "max": 0.08,
        "avg": 0.02,
        "median": 0.02,
        "p95": 0.05
      },
      "recovery_normalize_input": {
        "min": 0.0,
        "max": 0.01,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "recovery_policy_snapshot": {
        "min": 0.06,
        "max": 6.17,
        "avg": 1.17,
        "median": 1.05,
        "p95": 3.72
      },
      "recovery_total": {
        "min": 3.83,
        "max": 80.96,
        "avg": 15.73,
        "median": 13.34,
        "p95": 38.42
      },
      "service_device_lookup": {
        "min": 0.05,
        "max": 10.3,
        "avg": 2.24,
        "median": 2.23,
        "p95": 6.21
      },
      "service_existing_room_validation": {
        "min": 0.0,
        "max": 0.06,
        "avg": 0.01,
        "median": 0.01,
        "p95": 0.01
      },
      "service_key_envelope_bulk_insert": {
        "min": 0.75,
        "max": 7.93,
        "avg": 1.7,
        "median": 1.21,
        "p95": 5.19
      },
      "service_message_insert": {
        "min": 0.66,
        "max": 50.54,
        "avg": 3.39,
        "median": 1.36,
        "p95": 11.12
      },
      "service_policy_snapshot": {
        "min": 0.0,
        "max": 0.0,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "service_receipt_decision_insert": {
        "min": 0.0,
        "max": 0.0,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "service_reply_lookup": {
        "min": 0.0,
        "max": 0.01,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "service_room_update": {
        "min": 0.59,
        "max": 4.59,
        "avg": 1.32,
        "median": 0.97,
        "p95": 3.73
      },
      "service_room_validation": {
        "min": 0.0,
        "max": 0.0,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "service_total": {
        "min": 3.06,
        "max": 68.11,
        "avg": 10.89,
        "median": 8.71,
        "p95": 24.91
      },
      "service_validate_input": {
        "min": 0.06,
        "max": 0.26,
        "avg": 0.11,
        "median": 0.1,
        "p95": 0.18
      },
      "view_authenticated_user": {
        "min": 0.0,
        "max": 0.02,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "view_payload_prepare": {
        "min": 0.0,
        "max": 0.01,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.01
      },
      "view_realtime_outbox_enqueue": {
        "min": 0.97,
        "max": 15.97,
        "avg": 2.62,
        "median": 1.69,
        "p95": 6.54
      },
      "view_recipient_resolution": {
        "min": 7.3,
        "max": 36.81,
        "avg": 14.57,
        "median": 11.57,
        "p95": 27.31
      },
      "view_response_build": {
        "min": 0.01,
        "max": 0.08,
        "avg": 0.02,
        "median": 0.01,
        "p95": 0.05
      },
      "view_serializer_validation": {
        "min": 0.76,
        "max": 68.01,
        "avg": 2.14,
        "median": 1.12,
        "p95": 2.75
      },
      "view_service_call": {
        "min": 8.29,
        "max": 87.96,
        "avg": 22.15,
        "median": 19.94,
        "p95": 51.0
      },
      "view_total": {
        "min": 19.27,
        "max": 143.98,
        "avg": 41.52,
        "median": 36.67,
        "p95": 80.1
      }
    }
  },
  {
    "concurrency": 90,
    "server_timing_ms": {
      "recovery_base_send_total": {
        "min": 3.34,
        "max": 31.98,
        "avg": 10.1,
        "median": 8.57,
        "p95": 21.38
      },
      "recovery_bundle_check": {
        "min": 0.02,
        "max": 7.54,
        "avg": 1.92,
        "median": 1.96,
        "p95": 4.76
      },
      "recovery_envelope_bulk_insert": {
        "min": 0.01,
        "max": 0.06,
        "avg": 0.02,
        "median": 0.02,
        "p95": 0.04
      },
      "recovery_normalize_input": {
        "min": 0.0,
        "max": 0.02,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "recovery_policy_snapshot": {
        "min": 0.07,
        "max": 5.82,
        "avg": 1.14,
        "median": 1.13,
        "p95": 2.35
      },
      "recovery_total": {
        "min": 3.49,
        "max": 38.2,
        "avg": 13.2,
        "median": 12.07,
        "p95": 28.01
      },
      "service_device_lookup": {
        "min": 0.05,
        "max": 11.18,
        "avg": 2.28,
        "median": 2.26,
        "p95": 4.3
      },
      "service_existing_room_validation": {
        "min": 0.0,
        "max": 0.03,
        "avg": 0.01,
        "median": 0.01,
        "p95": 0.01
      },
      "service_key_envelope_bulk_insert": {
        "min": 0.64,
        "max": 6.35,
        "avg": 1.32,
        "median": 1.06,
        "p95": 2.64
      },
      "service_message_insert": {
        "min": 0.56,
        "max": 20.76,
        "avg": 1.73,
        "median": 1.0,
        "p95": 3.89
      },
      "service_policy_snapshot": {
        "min": 0.0,
        "max": 0.0,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "service_receipt_decision_insert": {
        "min": 0.0,
        "max": 0.0,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "service_reply_lookup": {
        "min": 0.0,
        "max": 0.0,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "service_room_update": {
        "min": 0.57,
        "max": 8.93,
        "avg": 1.41,
        "median": 1.13,
        "p95": 3.17
      },
      "service_room_validation": {
        "min": 0.0,
        "max": 0.0,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "service_total": {
        "min": 2.79,
        "max": 29.56,
        "avg": 8.69,
        "median": 7.33,
        "p95": 18.58
      },
      "service_validate_input": {
        "min": 0.06,
        "max": 0.36,
        "avg": 0.11,
        "median": 0.1,
        "p95": 0.16
      },
      "view_authenticated_user": {
        "min": 0.0,
        "max": 0.03,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "view_payload_prepare": {
        "min": 0.0,
        "max": 0.03,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.01
      },
      "view_realtime_outbox_enqueue": {
        "min": 0.97,
        "max": 16.16,
        "avg": 2.7,
        "median": 1.78,
        "p95": 6.99
      },
      "view_recipient_resolution": {
        "min": 7.52,
        "max": 32.47,
        "avg": 14.17,
        "median": 12.12,
        "p95": 27.27
      },
      "view_response_build": {
        "min": 0.01,
        "max": 0.07,
        "avg": 0.01,
        "median": 0.01,
        "p95": 0.03
      },
      "view_serializer_validation": {
        "min": 0.78,
        "max": 1.98,
        "avg": 1.13,
        "median": 1.06,
        "p95": 1.68
      },
      "view_service_call": {
        "min": 7.81,
        "max": 46.53,
        "avg": 19.55,
        "median": 18.57,
        "p95": 36.28
      },
      "view_total": {
        "min": 17.9,
        "max": 84.74,
        "avg": 37.59,
        "median": 34.14,
        "p95": 68.05
      }
    }
  },
  {
    "concurrency": 100,
    "server_timing_ms": {
      "recovery_base_send_total": {
        "min": 3.28,
        "max": 25.59,
        "avg": 10.07,
        "median": 8.72,
        "p95": 18.91
      },
      "recovery_bundle_check": {
        "min": 0.02,
        "max": 7.1,
        "avg": 2.28,
        "median": 2.05,
        "p95": 4.8
      },
      "recovery_envelope_bulk_insert": {
        "min": 0.01,
        "max": 0.09,
        "avg": 0.02,
        "median": 0.01,
        "p95": 0.03
      },
      "recovery_normalize_input": {
        "min": 0.0,
        "max": 0.06,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "recovery_policy_snapshot": {
        "min": 0.08,
        "max": 7.31,
        "avg": 1.37,
        "median": 1.19,
        "p95": 3.4
      },
      "recovery_total": {
        "min": 3.45,
        "max": 30.47,
        "avg": 13.75,
        "median": 12.45,
        "p95": 25.91
      },
      "service_device_lookup": {
        "min": 0.05,
        "max": 8.34,
        "avg": 2.69,
        "median": 2.41,
        "p95": 5.74
      },
      "service_existing_room_validation": {
        "min": 0.0,
        "max": 0.01,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.01
      },
      "service_key_envelope_bulk_insert": {
        "min": 0.6,
        "max": 5.24,
        "avg": 1.4,
        "median": 1.08,
        "p95": 2.92
      },
      "service_message_insert": {
        "min": 0.66,
        "max": 10.14,
        "avg": 1.34,
        "median": 1.02,
        "p95": 3.07
      },
      "service_policy_snapshot": {
        "min": 0.0,
        "max": 0.0,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "service_receipt_decision_insert": {
        "min": 0.0,
        "max": 0.0,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "service_reply_lookup": {
        "min": 0.0,
        "max": 0.0,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "service_room_update": {
        "min": 0.59,
        "max": 3.7,
        "avg": 1.19,
        "median": 0.94,
        "p95": 2.74
      },
      "service_room_validation": {
        "min": 0.0,
        "max": 0.0,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "service_total": {
        "min": 2.93,
        "max": 21.22,
        "avg": 8.44,
        "median": 7.58,
        "p95": 15.11
      },
      "service_validate_input": {
        "min": 0.06,
        "max": 0.22,
        "avg": 0.1,
        "median": 0.09,
        "p95": 0.15
      },
      "view_authenticated_user": {
        "min": 0.0,
        "max": 0.0,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.0
      },
      "view_payload_prepare": {
        "min": 0.0,
        "max": 0.01,
        "avg": 0.0,
        "median": 0.0,
        "p95": 0.01
      },
      "view_realtime_outbox_enqueue": {
        "min": 0.85,
        "max": 9.94,
        "avg": 2.82,
        "median": 2.02,
        "p95": 7.79
      },
      "view_recipient_resolution": {
        "min": 6.97,
        "max": 34.03,
        "avg": 13.44,
        "median": 11.47,
        "p95": 25.57
      },
      "view_response_build": {
        "min": 0.01,
        "max": 0.05,
        "avg": 0.01,
        "median": 0.01,
        "p95": 0.02
      },
      "view_serializer_validation": {
        "min": 0.78,
        "max": 6.49,
        "avg": 1.18,
        "median": 1.0,
        "p95": 1.54
      },
      "view_service_call": {
        "min": 7.05,
        "max": 44.46,
        "avg": 19.93,
        "median": 18.46,
        "p95": 33.76
      },
      "view_total": {
        "min": 16.91,
        "max": 76.85,
        "avg": 37.43,
        "median": 34.47,
        "p95": 66.65
      }
    }
  }
]
```

## Docker Resource Usage

### Setup And Warmup Docker Usage

| Phase | Concurrency | Container | Avg CPU % | Max CPU % | Avg RAM MB | Max RAM MB | Avg RAM % | Max RAM % | Max PIDs |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|



```json
{
  "enabled": false,
  "interval_seconds": 1.0,
  "container_names": [],
  "total_sample_rows": 0,
  "overall": {
    "sample_count": 0,
    "containers": {}
  },
  "by_phase": {},
  "errors": []
}
```

## Per-Level Docker Resource Usage

| Phase | Concurrency | Container | Avg CPU % | Max CPU % | Avg RAM MB | Max RAM MB | Avg RAM % | Max RAM % | Max PIDs |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|


```json
[
  {
    "concurrency": 1,
    "docker_stats": {
      "enabled": false,
      "interval_seconds": 1.0,
      "container_names": [],
      "total_sample_rows": 0,
      "overall": {
        "sample_count": 0,
        "containers": {}
      },
      "by_phase": {}
    }
  },
  {
    "concurrency": 5,
    "docker_stats": {
      "enabled": false,
      "interval_seconds": 1.0,
      "container_names": [],
      "total_sample_rows": 0,
      "overall": {
        "sample_count": 0,
        "containers": {}
      },
      "by_phase": {}
    }
  },
  {
    "concurrency": 10,
    "docker_stats": {
      "enabled": false,
      "interval_seconds": 1.0,
      "container_names": [],
      "total_sample_rows": 0,
      "overall": {
        "sample_count": 0,
        "containers": {}
      },
      "by_phase": {}
    }
  },
  {
    "concurrency": 20,
    "docker_stats": {
      "enabled": false,
      "interval_seconds": 1.0,
      "container_names": [],
      "total_sample_rows": 0,
      "overall": {
        "sample_count": 0,
        "containers": {}
      },
      "by_phase": {}
    }
  },
  {
    "concurrency": 30,
    "docker_stats": {
      "enabled": false,
      "interval_seconds": 1.0,
      "container_names": [],
      "total_sample_rows": 0,
      "overall": {
        "sample_count": 0,
        "containers": {}
      },
      "by_phase": {}
    }
  },
  {
    "concurrency": 40,
    "docker_stats": {
      "enabled": false,
      "interval_seconds": 1.0,
      "container_names": [],
      "total_sample_rows": 0,
      "overall": {
        "sample_count": 0,
        "containers": {}
      },
      "by_phase": {}
    }
  },
  {
    "concurrency": 50,
    "docker_stats": {
      "enabled": false,
      "interval_seconds": 1.0,
      "container_names": [],
      "total_sample_rows": 0,
      "overall": {
        "sample_count": 0,
        "containers": {}
      },
      "by_phase": {}
    }
  },
  {
    "concurrency": 60,
    "docker_stats": {
      "enabled": false,
      "interval_seconds": 1.0,
      "container_names": [],
      "total_sample_rows": 0,
      "overall": {
        "sample_count": 0,
        "containers": {}
      },
      "by_phase": {}
    }
  },
  {
    "concurrency": 70,
    "docker_stats": {
      "enabled": false,
      "interval_seconds": 1.0,
      "container_names": [],
      "total_sample_rows": 0,
      "overall": {
        "sample_count": 0,
        "containers": {}
      },
      "by_phase": {}
    }
  },
  {
    "concurrency": 80,
    "docker_stats": {
      "enabled": false,
      "interval_seconds": 1.0,
      "container_names": [],
      "total_sample_rows": 0,
      "overall": {
        "sample_count": 0,
        "containers": {}
      },
      "by_phase": {}
    }
  },
  {
    "concurrency": 90,
    "docker_stats": {
      "enabled": false,
      "interval_seconds": 1.0,
      "container_names": [],
      "total_sample_rows": 0,
      "overall": {
        "sample_count": 0,
        "containers": {}
      },
      "by_phase": {}
    }
  },
  {
    "concurrency": 100,
    "docker_stats": {
      "enabled": false,
      "interval_seconds": 1.0,
      "container_names": [],
      "total_sample_rows": 0,
      "overall": {
        "sample_count": 0,
        "containers": {}
      },
      "by_phase": {}
    }
  }
]
```

## API Timings

```json
{
  "GET /api/v1/health/": {
    "count": 2,
    "success_count": 2,
    "failure_count": 0,
    "status_counts": {
      "200": 2
    },
    "latency_ms": {
      "min": 19.45,
      "max": 27.76,
      "avg": 23.61,
      "median": 23.61,
      "p95": 27.34
    },
    "sample_errors": []
  },
  "identity_add_contact": {
    "count": 100,
    "success_count": 100,
    "failure_count": 0,
    "status_counts": {
      "201": 100
    },
    "latency_ms": {
      "min": 31.08,
      "max": 338.87,
      "avg": 41.0,
      "median": 36.09,
      "p95": 44.03
    },
    "sample_errors": []
  },
  "identity_delete_account": {
    "count": 200,
    "success_count": 200,
    "failure_count": 0,
    "status_counts": {
      "200": 200
    },
    "latency_ms": {
      "min": 109.44,
      "max": 171.66,
      "avg": 124.35,
      "median": 125.34,
      "p95": 136.32
    },
    "sample_errors": []
  },
  "identity_login": {
    "count": 200,
    "success_count": 200,
    "failure_count": 0,
    "status_counts": {
      "200": 200
    },
    "latency_ms": {
      "min": 104.2,
      "max": 143.1,
      "avg": 121.17,
      "median": 121.31,
      "p95": 130.06
    },
    "sample_errors": []
  },
  "identity_register": {
    "count": 200,
    "success_count": 200,
    "failure_count": 0,
    "status_counts": {
      "201": 200
    },
    "latency_ms": {
      "min": 105.23,
      "max": 278.95,
      "avg": 123.35,
      "median": 122.35,
      "p95": 132.27
    },
    "sample_errors": []
  },
  "messenger_device_register": {
    "count": 200,
    "success_count": 200,
    "failure_count": 0,
    "status_counts": {
      "201": 200
    },
    "latency_ms": {
      "min": 26.12,
      "max": 120.11,
      "avg": 33.32,
      "median": 32.27,
      "p95": 39.21
    },
    "sample_errors": []
  },
  "messenger_prekey_claim": {
    "count": 100,
    "success_count": 100,
    "failure_count": 0,
    "status_counts": {
      "200": 100
    },
    "latency_ms": {
      "min": 27.79,
      "max": 141.35,
      "avg": 38.53,
      "median": 33.9,
      "p95": 57.38
    },
    "sample_errors": []
  },
  "messenger_send_direct": {
    "count": 656,
    "success_count": 656,
    "failure_count": 0,
    "status_counts": {
      "201": 656
    },
    "latency_ms": {
      "min": 36.73,
      "max": 2175.61,
      "avg": 739.23,
      "median": 616.74,
      "p95": 1716.59
    },
    "sample_errors": []
  },
  "messenger_whoami": {
    "count": 200,
    "success_count": 200,
    "failure_count": 0,
    "status_counts": {
      "200": 200
    },
    "latency_ms": {
      "min": 8.37,
      "max": 15.44,
      "avg": 11.1,
      "median": 11.16,
      "p95": 12.6
    },
    "sample_errors": []
  }
}
```

## Cleanup

```json
{
  "messenger": {
    "enabled": false,
    "message": "Messenger Django cleanup disabled."
  },
  "identity": {
    "enabled": true,
    "success": true,
    "deleted_count": 200,
    "total_user_count": 200,
    "failed_samples": []
  }
}
```

## Failure Samples

```json
[]
```

## Host-Side Messenger Cleanup

``json
{
    "attempted":  true,
    "success":  true,
    "enabled":  true,
    "mode":  "host_side_docker_mysql_database_reset",
    "cleanup_type":  "host_side_messenger_cleanup",
    "cleanup_method":  "drop_recreate_messenger_benchmark_database_and_rerun_migrations",
    "stage":  "completed",
    "messenger_database":  "myna_messenger_benchmark",
    "mysql_container":  "mysql-benchmark-local",
    "messenger_container":  "messenger-service-local",
    "message_data_removed":  true,
    "all_messenger_benchmark_data_removed":  true,
    "messages_created_by_benchmark_removed":  true,
    "message":  "Messenger benchmark messages/data removed successfully by dropping and recreating the Messenger benchmark database, then rerunning migrations.",
    "completed_at":  "2026-07-03T22:55:30.1102814+05:30"
}
``

**Messenger messages cleaned:** `True`  
**Messages created by benchmark removed:** `True`  
**Final cleanup success:** `True`  


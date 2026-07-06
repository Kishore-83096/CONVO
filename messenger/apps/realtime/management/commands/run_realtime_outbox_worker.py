from __future__ import annotations

import os
import signal
import time

from django.core.management.base import BaseCommand
from django.db import close_old_connections

from apps.realtime.outbox import (
    DEFAULT_OUTBOX_BATCH_SIZE,
    DEFAULT_OUTBOX_MAX_ATTEMPTS,
    DEFAULT_OUTBOX_STALE_CLAIM_SECONDS,
    get_default_worker_id,
    retry_pending_realtime_outbox_events,
)


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name, "").strip()
    if not value:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name, "").strip()
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


class Command(BaseCommand):
    help = "Run the long-lived realtime transactional outbox worker."

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=_env_int(
                "REALTIME_OUTBOX_BATCH_SIZE",
                DEFAULT_OUTBOX_BATCH_SIZE,
            ),
        )
        parser.add_argument(
            "--poll-interval-seconds",
            type=float,
            default=_env_float(
                "REALTIME_OUTBOX_POLL_INTERVAL_SECONDS",
                1.0,
            ),
        )
        parser.add_argument(
            "--max-attempts",
            type=int,
            default=_env_int(
                "REALTIME_OUTBOX_MAX_ATTEMPTS",
                DEFAULT_OUTBOX_MAX_ATTEMPTS,
            ),
        )
        parser.add_argument(
            "--stale-claim-seconds",
            type=int,
            default=_env_int(
                "REALTIME_OUTBOX_STALE_CLAIM_SECONDS",
                DEFAULT_OUTBOX_STALE_CLAIM_SECONDS,
            ),
        )
        parser.add_argument(
            "--worker-id",
            default=os.getenv("REALTIME_OUTBOX_WORKER_ID", "").strip(),
        )
        parser.add_argument(
            "--stop-after-empty-polls",
            type=int,
            default=0,
            help=(
                "Testing helper: exit after this many empty polls. "
                "Zero runs forever."
            ),
        )

    def handle(self, *args, **options):
        should_stop = False

        def request_stop(signum, _frame):
            nonlocal should_stop
            should_stop = True
            self.stdout.write(
                f"Realtime outbox worker received signal {signum}; "
                "stopping after current batch."
            )

        signal.signal(signal.SIGTERM, request_stop)
        signal.signal(signal.SIGINT, request_stop)

        worker_id = (
            str(options["worker_id"]).strip()
            or get_default_worker_id()
        )
        batch_size = max(1, int(options["batch_size"]))
        poll_interval_seconds = max(
            0.1,
            float(options["poll_interval_seconds"]),
        )
        max_attempts = max(1, int(options["max_attempts"]))
        stale_claim_seconds = max(
            1,
            int(options["stale_claim_seconds"]),
        )
        stop_after_empty_polls = max(
            0,
            int(options["stop_after_empty_polls"]),
        )

        self.stdout.write(
            (
                "Starting realtime outbox worker "
                f"worker_id={worker_id} "
                f"batch_size={batch_size} "
                f"poll_interval_seconds={poll_interval_seconds} "
                f"max_attempts={max_attempts} "
                f"stale_claim_seconds={stale_claim_seconds}"
            )
        )

        empty_polls = 0
        totals = {
            "attempted": 0,
            "delivered": 0,
            "failed": 0,
            "dead": 0,
        }

        while not should_stop:
            close_old_connections()
            result = retry_pending_realtime_outbox_events(
                limit=batch_size,
                worker_id=worker_id,
                max_attempts=max_attempts,
                stale_claim_seconds=stale_claim_seconds,
            )
            close_old_connections()

            for key in totals:
                totals[key] += int(result.get(key) or 0)

            if result["attempted"]:
                empty_polls = 0
                self.stdout.write(
                    (
                        "Realtime outbox batch: "
                        f"attempted={result['attempted']} "
                        f"delivered={result['delivered']} "
                        f"failed={result['failed']} "
                        f"dead={result['dead']} "
                        f"totals={totals}"
                    )
                )
                continue

            empty_polls += 1
            if (
                stop_after_empty_polls
                and empty_polls >= stop_after_empty_polls
            ):
                break

            time.sleep(poll_interval_seconds)

        self.stdout.write(
            self.style.SUCCESS(
                (
                    "Realtime outbox worker stopped: "
                    f"attempted={totals['attempted']} "
                    f"delivered={totals['delivered']} "
                    f"failed={totals['failed']} "
                    f"dead={totals['dead']}"
                )
            )
        )

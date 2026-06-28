from django.core.management.base import BaseCommand

from apps.realtime.outbox import retry_pending_realtime_outbox_events


class Command(BaseCommand):
    help = "Retry pending realtime outbox events."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=100,
            help="Maximum number of pending realtime events to retry.",
        )

    def handle(self, *args, **options):
        result = retry_pending_realtime_outbox_events(
            limit=options["limit"],
        )

        self.stdout.write(
            self.style.SUCCESS(
                (
                    "Realtime outbox retry complete: "
                    f"attempted={result['attempted']} "
                    f"delivered={result['delivered']} "
                    f"failed={result['failed']}"
                )
            )
        )
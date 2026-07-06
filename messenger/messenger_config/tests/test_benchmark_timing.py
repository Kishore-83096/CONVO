from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.test import SimpleTestCase
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView

from apps.chat_messages.views import DirectSendPreViewTimingMixin
from messenger_config.benchmark_timing import (
    BenchmarkPreViewTimingMiddleware,
    BenchmarkRequestTiming,
    record_direct_send_view_entry,
    record_direct_send_view_exit,
    record_django_asgi_entry,
    record_drf_dispatch_entry,
    reset_benchmark_request_timing,
    set_benchmark_request_timing,
)


class InstrumentedAPIView(DirectSendPreViewTimingMixin, APIView):
    authentication_classes = []
    permission_classes = []
    throttle_classes = []

    def post(self, request):
        record_direct_send_view_entry()
        record_direct_send_view_exit()
        return Response({"ok": True})


class BenchmarkTimingContextTests(SimpleTestCase):
    def test_timing_context_is_request_local_across_threads(self):
        barrier = Barrier(2)

        def worker(server_entry_ns: int) -> BenchmarkRequestTiming:
            timing = BenchmarkRequestTiming(server_entry_ns=server_entry_ns)
            token = set_benchmark_request_timing(timing)
            try:
                barrier.wait(timeout=5)
                record_django_asgi_entry(server_entry_ns + 10)
                record_drf_dispatch_entry(server_entry_ns + 20)
                record_direct_send_view_entry(server_entry_ns + 30)
                return timing
            finally:
                reset_benchmark_request_timing(token)

        with ThreadPoolExecutor(max_workers=2) as executor:
            first, second = list(executor.map(worker, [1_000, 2_000]))

        self.assertEqual(first.django_asgi_entry_ns, 1_010)
        self.assertEqual(first.drf_dispatch_entry_ns, 1_020)
        self.assertEqual(first.view_entry_ns, 1_030)
        self.assertEqual(second.django_asgi_entry_ns, 2_010)
        self.assertEqual(second.drf_dispatch_entry_ns, 2_020)
        self.assertEqual(second.view_entry_ns, 2_030)

    def test_benchmark_middleware_records_first_django_middleware_entry(self):
        timing = BenchmarkRequestTiming(server_entry_ns=1_000)
        token = set_benchmark_request_timing(timing)
        try:
            middleware = BenchmarkPreViewTimingMiddleware(lambda request: "ok")

            self.assertEqual(middleware(object()), "ok")

            self.assertIsNotNone(timing.django_middleware_entry_ns)
        finally:
            reset_benchmark_request_timing(token)

    def test_drf_mixin_captures_supported_pre_view_boundaries(self):
        timing = BenchmarkRequestTiming(server_entry_ns=1_000)
        token = set_benchmark_request_timing(timing)
        try:
            view = InstrumentedAPIView.as_view()
            request = APIRequestFactory().post(
                "/api/v1/messages/direct/",
                data={},
                format="json",
            )

            response = view(request)

            self.assertEqual(response.status_code, 200)
            self.assertIsNotNone(timing.drf_dispatch_entry_ns)
            self.assertIsNotNone(timing.drf_initialize_request_entry_ns)
            self.assertIsNotNone(timing.drf_initialize_request_exit_ns)
            self.assertIsNotNone(timing.drf_initial_entry_ns)
            self.assertIsNotNone(timing.drf_initial_exit_ns)
            self.assertIsNotNone(timing.drf_content_negotiation_entry_ns)
            self.assertIsNotNone(timing.drf_content_negotiation_exit_ns)
            self.assertIsNotNone(timing.drf_authentication_entry_ns)
            self.assertIsNotNone(timing.drf_authentication_exit_ns)
            self.assertIsNotNone(timing.drf_permission_entry_ns)
            self.assertIsNotNone(timing.drf_permission_exit_ns)
            self.assertIsNotNone(timing.drf_throttle_entry_ns)
            self.assertIsNotNone(timing.drf_throttle_exit_ns)
            self.assertGreaterEqual(
                timing.drf_initialize_request_exit_ns,
                timing.drf_initialize_request_entry_ns,
            )
            self.assertGreaterEqual(
                timing.drf_initial_exit_ns,
                timing.drf_initial_entry_ns,
            )
            self.assertGreaterEqual(timing.view_entry_ns, timing.drf_initial_exit_ns)
        finally:
            reset_benchmark_request_timing(token)

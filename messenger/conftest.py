import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def clear_django_cache_between_tests():
    """
    Keep cache-backed hot-path optimizations isolated between tests.

    Django TestCase/TransactionTestCase isolate database state, but the
    configured cache can outlive a single test method. The messenger
    service now caches active-device IDs, delivery-policy snapshots, and
    recovery-active checks, so stale cache values must not leak between
    independent tests.
    """

    cache.clear()
    yield
    cache.clear()
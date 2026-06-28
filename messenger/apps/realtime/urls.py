from django.urls import path

from .views import (
    PresenceBatchView,
    RealtimeTicketCreateView,
)
app_name = "realtime"

urlpatterns = [
    path(
        "tickets/",
        RealtimeTicketCreateView.as_view(),
        name="ticket-create",
    ),
    path(
        "presence/batch/",
        PresenceBatchView.as_view(),
        name="presence-batch",
    ),
]
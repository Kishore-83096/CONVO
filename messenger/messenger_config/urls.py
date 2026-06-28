from django.contrib import admin
from django.urls import include, path

from apps.chat_messages.views import (
    EncryptedMessageHistoryView,
    RoomListView,
)
from messenger_config.views import CurrentIdentityView, HealthView
from apps.chat_messages.policy_views import ContactDeliveryPolicySyncView

urlpatterns = [
    path(
        "api/v1/internal/contact-policies/",
        ContactDeliveryPolicySyncView.as_view(),
        name="internal-contact-policy-sync",
    ),

    path(
        "api/v1/health/",
        HealthView.as_view(),
        name="health",
    ),
    path(
        "admin/",
        admin.site.urls,
    ),
    path(
        "api/v1/auth/whoami/",
        CurrentIdentityView.as_view(),
        name="current-identity",
    ),
    path(
        "api/v1/e2ee/",
        include("apps.e2ee_devices.urls"),
    ),
    path(
        "api/v1/messages/",
        include("apps.chat_messages.urls"),
    ),
    path(
        "api/v1/rooms/",
        RoomListView.as_view(),
        name="room-list",
    ),
    path(
        "api/v1/rooms/<uuid:room_id>/history/",
        EncryptedMessageHistoryView.as_view(),
        name="room-history",
    ),
    path(
        "api/v1/groups/",
        include(("apps.group_chat.urls", "group_chat"), namespace="group_chat"),
    ),
]

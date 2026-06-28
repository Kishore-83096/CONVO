"""
ASGI config for the Myna Messenger service.

Important import order:

Django apps must be loaded before importing modules that import models.
So get_asgi_application() must run before importing realtime middleware
that touches RealtimeTicket / Device / other Django models.
"""

import os

from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "messenger_config.settings",
)

django_asgi_app = get_asgi_application()

from apps.realtime.authentication import RealtimeTicketAuthMiddleware  # noqa: E402
from messenger_config.routing import websocket_urlpatterns  # noqa: E402


application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": RealtimeTicketAuthMiddleware(
            URLRouter(websocket_urlpatterns),
        ),
    }
)
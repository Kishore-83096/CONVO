"""
Root WebSocket routing for the Myna Messenger service.

This file collects websocket routes from realtime apps.

Phase 7:
    apps.realtime.routing exists but exposes no WebSocket endpoint yet.
"""

from apps.realtime.routing import websocket_urlpatterns as realtime_urlpatterns

websocket_urlpatterns = [
    *realtime_urlpatterns,
]
from django.apps import apps
from django.test import SimpleTestCase
from django.urls import reverse
from apps.realtime import events
from apps.realtime import policies
from messenger_config.routing import websocket_urlpatterns


class RealtimeAppStructureTests(SimpleTestCase):
    def test_realtime_app_is_installed(self):
        app_config = apps.get_app_config("realtime")

        self.assertEqual(app_config.name, "apps.realtime")
        self.assertEqual(app_config.verbose_name, "Realtime")
    
    def test_phase10_has_messenger_websocket_route(self):
        self.assertEqual(len(websocket_urlpatterns), 1)
        self.assertEqual(
            websocket_urlpatterns[0].pattern._route,
            "ws/messenger/",
        )
    def test_phase8_ticket_route_exists(self):
        self.assertEqual(
            reverse("realtime:ticket-create"),
            "/api/v1/realtime/tickets/",
        )
        
    def test_phase13_presence_batch_route_exists(self):
        self.assertEqual(
            reverse("realtime:presence-batch"),
            "/api/v1/realtime/presence/batch/",
        )

    def test_realtime_event_constants_exist(self):
        self.assertEqual(events.CONNECTION_ACCEPTED, "connection.accepted")
        self.assertEqual(events.HEARTBEAT_ACK, "heartbeat.ack")
        self.assertEqual(events.MESSAGE_STORED, "message.stored")
        self.assertEqual(events.GROUP_MESSAGE_STORED, "group.message.stored")
        self.assertEqual(events.MESSAGE_DELIVERED, "message.delivered")
        self.assertEqual(events.MESSAGE_READ, "message.read")
        self.assertEqual(events.PRESENCE_CHANGED, "presence.changed")
        self.assertEqual(events.PRESENCE_HIDDEN, "presence.hidden")
        self.assertEqual(
            events.RECONCILIATION_REQUIRED,
            "reconciliation.required",
        )

    def test_realtime_policies_reexport_directional_policy_helpers(self):
        self.assertTrue(callable(policies.can_view_presence))
        self.assertTrue(callable(policies.can_publish_receipt_to_sender))
        self.assertTrue(callable(policies.can_send_typing_to_viewer))
from django.apps import apps
from django.core.management import call_command
from django.test import SimpleTestCase
from django.urls import get_resolver, resolve, reverse

from apps.group_chat import constants


class GroupChatScaffoldTests(SimpleTestCase):
    def test_group_chat_app_loads(self):
        config = apps.get_app_config("group_chat")

        self.assertEqual(config.name, "apps.group_chat")
        self.assertEqual(config.verbose_name, "Myna Group Chat")

    def test_group_url_namespace_loads_without_public_routes(self):
        resolver = get_resolver()

        self.assertIn("group_chat", resolver.namespace_dict)

    def test_group_constants_are_centralized(self):
        self.assertEqual(constants.ROOM_TYPE_GROUP, "group")
        self.assertEqual(
            constants.GROUP_ROLES,
            ("owner", "admin", "member"),
        )
        self.assertGreaterEqual(constants.DEFAULT_GROUP_MEMBER_LIMIT, 2)
        self.assertIn(
            "security_incident",
            constants.EPOCH_ROTATION_REASONS,
        )

    def test_django_system_check_passes(self):
        call_command("check", verbosity=0)

    def test_existing_direct_routes_still_resolve(self):
        direct_path = reverse("chat_messages:send-direct-message")
        rooms_path = reverse("chat_messages:room-list")
        history_path = reverse(
            "chat_messages:encrypted-message-history",
            kwargs={
                "room_id": "11111111-1111-4111-8111-111111111111",
            },
        )

        self.assertEqual(direct_path, "/api/v1/messages/direct/")
        self.assertEqual(rooms_path, "/api/v1/messages/rooms/")
        self.assertEqual(
            history_path,
            "/api/v1/messages/rooms/"
            "11111111-1111-4111-8111-111111111111/history/",
        )

        self.assertEqual(
            resolve(direct_path).url_name,
            "send-direct-message",
        )
        self.assertEqual(resolve(rooms_path).url_name, "room-list")
        self.assertEqual(
            resolve(history_path).url_name,
            "encrypted-message-history",
        )
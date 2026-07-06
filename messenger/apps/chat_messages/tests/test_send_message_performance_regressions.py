import os
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.core.cache import cache
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.e2ee_devices.models import Device
from apps.e2ee_devices.services import get_active_device_ids_for_user
from apps.realtime.models import RealtimeOutboxEvent
from apps.rooms.models import Room, RoomMember

from ..models import (
    DirectMessageReceiptDecision,
    Message,
    MessageKeyEnvelope,
)
from ..services import (
    DirectMessageValidationError,
    DirectRoomUnavailableError,
    build_direct_pair_key,
    resolve_existing_direct_room_recipient,
)
from ..recovery_send_services import send_direct_message_with_recovery
from .. import services as message_services


class SendMessagePerformanceRegressionTests(TestCase):
    sender_device_id = uuid.UUID(
        "11111111-1111-4111-8111-111111111111"
    )
    recipient_device_id = uuid.UUID(
        "22222222-2222-4222-8222-222222222222"
    )

    def setUp(self):
        cache.clear()

        self.sender_device = Device.objects.create(
            id=self.sender_device_id,
            user_id="1",
            device_name="Sender browser",
            platform=Device.Platform.WEB,
            registration_id=10001,
            identity_key_public="SENDER_IDENTITY_PUBLIC",
            signed_prekey_id=1,
            signed_prekey_public="SENDER_SIGNED_PREKEY",
            signed_prekey_signature="SENDER_SIGNATURE",
            key_algorithm="curve25519",
            key_bundle_version=1,
        )

        self.recipient_device = Device.objects.create(
            id=self.recipient_device_id,
            user_id="2",
            device_name="Recipient browser",
            platform=Device.Platform.WEB,
            registration_id=20001,
            identity_key_public="RECIPIENT_IDENTITY_PUBLIC",
            signed_prekey_id=1,
            signed_prekey_public="RECIPIENT_SIGNED_PREKEY",
            signed_prekey_signature="RECIPIENT_SIGNATURE",
            key_algorithm="curve25519",
            key_bundle_version=1,
        )

    def valid_envelopes(self):
        return [
            {
                "recipient_device_id": str(self.sender_device_id),
                "protocol": MessageKeyEnvelope.Protocol.DEVICE_SYNC,
                "session_reference": "sender-sync-session",
                "wrapped_message_key": "WRAPPED_KEY_FOR_SENDER",
                "key_wrap_metadata": {
                    "algorithm": "device-sync-v1",
                },
                "envelope_version": 1,
            },
            {
                "recipient_device_id": str(self.recipient_device_id),
                "protocol": MessageKeyEnvelope.Protocol.DOUBLE_RATCHET,
                "session_reference": "recipient-ratchet-session",
                "wrapped_message_key": "WRAPPED_KEY_FOR_RECIPIENT",
                "key_wrap_metadata": {
                    "algorithm": "double-ratchet",
                    "message_number": 1,
                },
                "envelope_version": 1,
            },
        ]

    def send_message(
        self,
        *,
        client_message_id=None,
        encrypted_payload="PERFORMANCE_REGRESSION_CIPHERTEXT",
        envelopes=None,
        existing_room=None,
    ):
        return send_direct_message_with_recovery(
            sender_user_id="1",
            recipient_user_id="2",
            sender_device_id=self.sender_device_id,
            client_message_id=(
                client_message_id
                or uuid.UUID(
                    "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
                )
            ),
            message_type=Message.MessageType.TEXT,
            encrypted_payload=encrypted_payload,
            encryption_metadata={
                "algorithm": "xchacha20poly1305",
                "nonce": f"NONCE_{client_message_id or 'default'}",
            },
            encryption_version=1,
            envelopes=envelopes or self.valid_envelopes(),
            recovery_envelopes=[],
            sender_contact_validated_by_identity=existing_room is None,
            identity_contact_id="101" if existing_room is None else None,
            existing_room=existing_room,
            require_saved_contact=False,
        )

    def test_profiled_normal_send_keeps_receipt_decision_insert_at_zero(self):
        with patch.dict(
            os.environ,
            {
                "MYNA_PROFILE_DIRECT_SEND": "true",
            },
        ):
            result = self.send_message()

        self.assertTrue(result.message_created)
        self.assertEqual(Message.objects.count(), 1)
        self.assertEqual(MessageKeyEnvelope.objects.count(), 2)

        self.assertEqual(
            DirectMessageReceiptDecision.objects.count(),
            0,
        )

        self.assertIsInstance(result.profile_timings_ms, dict)
        self.assertEqual(
            result.profile_timings_ms[
                "service_receipt_decision_insert"
            ],
            0.0,
        )

        for timing_key in (
            "service_policy_snapshot",
            "service_device_lookup",
            "service_message_insert",
            "service_key_envelope_bulk_insert",
            "service_realtime_outbox_persist",
            "service_room_update",
            "service_total",
            "recovery_bundle_check",
            "recovery_total",
        ):
            self.assertIn(
                timing_key,
                result.profile_timings_ms,
            )
            self.assertGreaterEqual(
                result.profile_timings_ms[timing_key],
                0.0,
            )

    def test_outbox_persistence_rolls_back_with_message_transaction(self):
        original_profile_checkpoint = message_services.profile_checkpoint

        def fail_after_outbox_persist(timings, name, started_at):
            original_profile_checkpoint(timings, name, started_at)
            if name == "service_realtime_outbox_persist":
                raise RuntimeError("force rollback after outbox persist")

        with patch(
            "apps.chat_messages.services.profile_checkpoint",
            side_effect=fail_after_outbox_persist,
        ):
            with self.assertRaises(RuntimeError):
                self.send_message(
                    client_message_id=uuid.UUID(
                        "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee"
                    ),
                    encrypted_payload=(
                        "ROLLBACK_AFTER_OUTBOX_CIPHERTEXT"
                    ),
                )

        self.assertEqual(Message.objects.count(), 0)
        self.assertEqual(MessageKeyEnvelope.objects.count(), 0)
        self.assertEqual(RealtimeOutboxEvent.objects.count(), 0)

    def test_cached_active_devices_still_reject_missing_recipient_envelope(self):
        get_active_device_ids_for_user("1")
        get_active_device_ids_for_user("2")

        with self.assertRaises(DirectMessageValidationError) as context:
            self.send_message(
                client_message_id=uuid.UUID(
                    "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
                ),
                encrypted_payload=(
                    "MISSING_RECIPIENT_ENVELOPE_CIPHERTEXT"
                ),
                envelopes=[
                    self.valid_envelopes()[0],
                ],
            )

        self.assertIn(
            str(self.recipient_device_id),
            str(context.exception),
        )
        self.assertEqual(Message.objects.count(), 0)
        self.assertEqual(MessageKeyEnvelope.objects.count(), 0)

    def test_existing_room_recipient_resolution_uses_one_joined_query(self):
        room = Room.objects.create(
            room_type=Room.RoomType.DIRECT,
            direct_pair_key=build_direct_pair_key("1", "2"),
            is_active=True,
        )
        RoomMember.objects.create(
            room=room,
            user_id="1",
            role=RoomMember.Role.MEMBER,
            added_by_user_id="1",
            is_active=True,
        )
        RoomMember.objects.create(
            room=room,
            user_id="2",
            role=RoomMember.Role.MEMBER,
            added_by_user_id="1",
            is_active=True,
        )

        with CaptureQueriesContext(connection) as captured:
            resolved_room, recipient_user_id = (
                resolve_existing_direct_room_recipient(
                    authenticated_user_id="1",
                    room_id=room.id,
                )
            )

        resolver_selects = [
            query["sql"]
            for query in captured.captured_queries
            if query["sql"].lstrip().upper().startswith("SELECT")
            and "messenger_room_members" in query["sql"]
        ]

        self.assertEqual(len(resolver_selects), 1)
        self.assertEqual(resolved_room.id, room.id)
        self.assertEqual(recipient_user_id, "2")
        self.assertEqual(
            {member.user_id for member in resolved_room.active_members},
            {"1", "2"},
        )

    def test_existing_room_recipient_resolution_rejects_extra_active_member(self):
        room = Room.objects.create(
            room_type=Room.RoomType.DIRECT,
            direct_pair_key=build_direct_pair_key("1", "2"),
            is_active=True,
        )
        for user_id in ("1", "2", "3"):
            RoomMember.objects.create(
                room=room,
                user_id=user_id,
                role=RoomMember.Role.MEMBER,
                added_by_user_id="1",
                is_active=True,
            )

        with self.assertRaises(DirectRoomUnavailableError):
            resolve_existing_direct_room_recipient(
                authenticated_user_id="1",
                room_id=room.id,
            )

    def test_profiled_existing_room_send_uses_existing_room_validation_checkpoint(self):
        room = Room.objects.create(
            room_type=Room.RoomType.DIRECT,
            direct_pair_key=build_direct_pair_key("1", "2"),
        )
        RoomMember.objects.create(
            room=room,
            user_id="1",
            role=RoomMember.Role.MEMBER,
        )
        RoomMember.objects.create(
            room=room,
            user_id="2",
            role=RoomMember.Role.MEMBER,
        )

        old_updated_at = timezone.now() - timedelta(days=1)
        Room.objects.filter(id=room.id).update(
            updated_at=old_updated_at,
        )
        room.refresh_from_db()

        with patch.dict(
            os.environ,
            {
                "MYNA_PROFILE_DIRECT_SEND": "true",
            },
        ):
            result = self.send_message(
                client_message_id=uuid.UUID(
                    "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
                ),
                encrypted_payload=(
                    "EXISTING_ROOM_PERFORMANCE_CIPHERTEXT"
                ),
                existing_room=room,
            )

        self.assertTrue(result.message_created)
        self.assertFalse(result.room_created)
        self.assertEqual(result.room.id, room.id)

        self.assertIn(
            "service_existing_room_validation",
            result.profile_timings_ms,
        )
        self.assertIn(
            "service_room_update",
            result.profile_timings_ms,
        )

        room.refresh_from_db()
        self.assertGreater(
            room.updated_at,
            old_updated_at,
        )

    def test_profiled_existing_room_send_failure_does_not_update_room_timestamp(self):
        room = Room.objects.create(
            room_type=Room.RoomType.DIRECT,
            direct_pair_key=build_direct_pair_key("1", "2"),
        )
        RoomMember.objects.create(
            room=room,
            user_id="1",
            role=RoomMember.Role.MEMBER,
        )
        RoomMember.objects.create(
            room=room,
            user_id="2",
            role=RoomMember.Role.MEMBER,
        )

        old_updated_at = timezone.now() - timedelta(days=1)
        Room.objects.filter(id=room.id).update(
            updated_at=old_updated_at,
        )
        room.refresh_from_db()

        with patch.dict(
            os.environ,
            {
                "MYNA_PROFILE_DIRECT_SEND": "true",
            },
        ):
            with self.assertRaises(DirectMessageValidationError):
                self.send_message(
                    client_message_id=uuid.UUID(
                        "dddddddd-dddd-4ddd-8ddd-dddddddddddd"
                    ),
                    encrypted_payload=(
                        "FAILED_EXISTING_ROOM_PERFORMANCE"
                    ),
                    envelopes=[
                        self.valid_envelopes()[0],
                    ],
                    existing_room=room,
                )

        room.refresh_from_db()
        self.assertEqual(
            room.updated_at,
            old_updated_at,
        )
        self.assertEqual(Message.objects.count(), 0)
        self.assertEqual(MessageKeyEnvelope.objects.count(), 0)

import uuid
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

import jwt
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from messenger_config.identity_client import (
    IdentityClientError,
    SavedContactForbiddenError,
)
from apps.e2ee_devices.models import Device
from apps.rooms.models import Room, RoomMember

from ..models import ContactDeliveryPolicy, Message, MessageKeyEnvelope
from ..services import build_direct_pair_key

class DirectMessageSendingAPITests(APITestCase):
    sender_device_id = uuid.UUID(
        "11111111-1111-4111-8111-111111111111"
    )
    recipient_device_id = uuid.UUID(
        "22222222-2222-4222-8222-222222222222"
    )
    second_sender_device_id = uuid.UUID(
        "33333333-3333-4333-8333-333333333333"
    )
    recipient_contact_id = 101

    def setUp(self):
        self.sender_device = Device.objects.create(
            id=self.sender_device_id,
            user_id="1",
            device_name="Sender browser",
            platform="web",
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
            platform="web",
            registration_id=20001,
            identity_key_public="RECIPIENT_IDENTITY_PUBLIC",
            signed_prekey_id=1,
            signed_prekey_public="RECIPIENT_SIGNED_PREKEY",
            signed_prekey_signature="RECIPIENT_SIGNATURE",
            key_algorithm="curve25519",
            key_bundle_version=1,
        )

        self.url = reverse("chat_messages:send-direct-message")

        self.resolve_contact_patcher = patch(
            "apps.chat_messages.views.resolve_saved_contact_recipient"
        )
        self.mock_resolve_contact = self.resolve_contact_patcher.start()
        self.addCleanup(self.resolve_contact_patcher.stop)

        self.mock_resolve_contact.return_value = SimpleNamespace(
            contact_id=str(self.recipient_contact_id),
            contact_user_id="2",
            saved_name="Recipient",
            contact_number="9999999999",
        )

    def authenticate_as(self, user_id: str):
        now = timezone.now()
        token = jwt.encode(
            {
                "sub": user_id,
                "type": "access",
                "jti": str(uuid.uuid4()),
                "iat": now,
                "nbf": now,
                "exp": now + timedelta(minutes=5),
            },
            settings.JWT_VERIFYING_KEY,
            algorithm=settings.JWT_ALGORITHM,
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def valid_payload(
        self,
        *,
        client_message_id: uuid.UUID | None = None,
        encrypted_payload: str = "AUTOMATED_DIRECT_CIPHERTEXT",
    ) -> dict:
        client_message_id = client_message_id or uuid.UUID(
            "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
        )

        return {
            "recipient_contact_id": self.recipient_contact_id,
            "sender_device_id": str(self.sender_device_id),
            "client_message_id": str(client_message_id),
            "message_type": "text",
            "encrypted_payload": encrypted_payload,
            "encryption_metadata": {
                "algorithm": "xchacha20poly1305",
                "nonce": "AUTOMATED_DIRECT_NONCE",
            },
            "encryption_version": 1,
            "envelopes": [
                {
                    "recipient_device_id": str(self.sender_device_id),
                    "protocol": "device_sync",
                    "session_reference": "sender-sync-session",
                    "wrapped_message_key": "WRAPPED_KEY_FOR_SENDER",
                    "key_wrap_metadata": {
                        "algorithm": "device-sync-v1",
                    },
                    "envelope_version": 1,
                },
                {
                    "recipient_device_id": str(self.recipient_device_id),
                    "protocol": "double_ratchet",
                    "session_reference": "recipient-ratchet-session",
                    "wrapped_message_key": "WRAPPED_KEY_FOR_RECIPIENT",
                    "key_wrap_metadata": {
                        "algorithm": "double-ratchet",
                        "message_number": 1,
                    },
                    "envelope_version": 1,
                },
            ],
        }

    def assert_nothing_stored(self):
        self.assertEqual(Message.objects.count(), 0)
        self.assertEqual(MessageKeyEnvelope.objects.count(), 0)
        self.assertEqual(Room.objects.count(), 0)
        self.assertEqual(RoomMember.objects.count(), 0)

    def test_authentication_is_required(self):
        response = self.client.post(
            self.url,
            self.valid_payload(),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assert_nothing_stored()

    def test_valid_direct_message_is_stored_atomically(self):
        self.authenticate_as("1")
        payload = self.valid_payload()

        response = self.client.post(
            self.url,
            payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        body = response.json()
        data = body["data"]

        self.assertTrue(body["success"])
        self.assertTrue(data["room_created"])
        self.assertTrue(data["message_created"])
        self.assertEqual(data["envelope_count"], 2)

        self.assertEqual(Room.objects.count(), 1)
        self.assertEqual(RoomMember.objects.count(), 2)
        self.assertEqual(Message.objects.count(), 1)
        self.assertEqual(MessageKeyEnvelope.objects.count(), 2)

        message = Message.objects.get(
            client_message_id=payload["client_message_id"],
            sender_user_id="1",
        )

        self.assertEqual(str(message.id), data["message_id"])
        self.assertEqual(str(message.room_id), data["room_id"])
        self.assertEqual(
            message.encrypted_payload,
            payload["encrypted_payload"],
        )

        member_ids = set(
            RoomMember.objects.filter(
                room=message.room,
                is_active=True,
            ).values_list("user_id", flat=True)
        )
        self.assertEqual(member_ids, {"1", "2"})

        envelope_devices = set(
            MessageKeyEnvelope.objects.filter(
                message=message,
            ).values_list("recipient_device_id", flat=True)
        )
        self.assertEqual(
            envelope_devices,
            {
                self.sender_device_id,
                self.recipient_device_id,
            },
        )

    def test_exact_retry_is_idempotent(self):
        self.authenticate_as("1")
        payload = self.valid_payload()

        first_response = self.client.post(
            self.url,
            payload,
            format="json",
        )
        second_response = self.client.post(
            self.url,
            payload,
            format="json",
        )

        self.assertEqual(
            first_response.status_code,
            status.HTTP_201_CREATED,
        )
        self.assertEqual(
            second_response.status_code,
            status.HTTP_200_OK,
        )

        first_data = first_response.json()["data"]
        second_data = second_response.json()["data"]

        self.assertEqual(
            first_data["room_id"],
            second_data["room_id"],
        )
        self.assertEqual(
            first_data["message_id"],
            second_data["message_id"],
        )
        self.assertFalse(second_data["room_created"])
        self.assertFalse(second_data["message_created"])
        self.assertEqual(second_data["envelope_count"], 2)

        self.assertEqual(Room.objects.count(), 1)
        self.assertEqual(RoomMember.objects.count(), 2)
        self.assertEqual(Message.objects.count(), 1)
        self.assertEqual(MessageKeyEnvelope.objects.count(), 2)

    def test_reused_client_message_id_with_changed_data_conflicts(self):
        self.authenticate_as("1")
        original_payload = self.valid_payload()

        first_response = self.client.post(
            self.url,
            original_payload,
            format="json",
        )
        self.assertEqual(
            first_response.status_code,
            status.HTTP_201_CREATED,
        )

        conflicting_payload = self.valid_payload(
            encrypted_payload="CHANGED_CIPHERTEXT",
        )

        conflict_response = self.client.post(
            self.url,
            conflicting_payload,
            format="json",
        )

        self.assertEqual(
            conflict_response.status_code,
            status.HTTP_409_CONFLICT,
        )
        self.assertEqual(
            conflict_response.json(),
            {
                "success": False,
                "message": (
                    "This client_message_id was already used with "
                    "different message or envelope data."
                ),
            },
        )

        self.assertEqual(Room.objects.count(), 1)
        self.assertEqual(RoomMember.objects.count(), 2)
        self.assertEqual(Message.objects.count(), 1)
        self.assertEqual(MessageKeyEnvelope.objects.count(), 2)

    def test_sender_device_must_belong_to_authenticated_user(self):
        self.authenticate_as("1")
        payload = self.valid_payload()
        payload["sender_device_id"] = str(self.recipient_device_id)

        response = self.client.post(
            self.url,
            payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            response.json(),
            {
                "success": False,
                "message": (
                    "The sender device does not belong to the "
                    "authenticated sender."
                ),
            },
        )
        self.assert_nothing_stored()

    def test_missing_recipient_device_envelope_is_rejected(self):
        self.authenticate_as("1")
        payload = self.valid_payload()
        payload["envelopes"] = [payload["envelopes"][0]]

        response = self.client.post(
            self.url,
            payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertIn(
            str(self.recipient_device_id),
            response.json()["message"],
        )
        self.assert_nothing_stored()

    def test_recipient_device_must_use_double_ratchet(self):
        self.authenticate_as("1")
        payload = self.valid_payload()
        payload["envelopes"][1]["protocol"] = "device_sync"

        response = self.client.post(
            self.url,
            payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertIn(
            "must use the double_ratchet envelope protocol",
            response.json()["message"],
        )
        self.assert_nothing_stored()

    def test_sender_device_must_use_device_sync(self):
        self.authenticate_as("1")
        payload = self.valid_payload()
        payload["envelopes"][0]["protocol"] = "double_ratchet"

        response = self.client.post(
            self.url,
            payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertIn(
            "must use the device_sync envelope protocol",
            response.json()["message"],
        )
        self.assert_nothing_stored()

    def test_every_active_sender_device_requires_an_envelope(self):
        Device.objects.create(
            id=self.second_sender_device_id,
            user_id="1",
            device_name="Sender mobile",
            platform="android",
            registration_id=10002,
            identity_key_public="SECOND_SENDER_IDENTITY_PUBLIC",
            signed_prekey_id=2,
            signed_prekey_public="SECOND_SENDER_SIGNED_PREKEY",
            signed_prekey_signature="SECOND_SENDER_SIGNATURE",
            key_algorithm="curve25519",
            key_bundle_version=1,
        )

        self.authenticate_as("1")
        payload = self.valid_payload()

        response = self.client.post(
            self.url,
            payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertIn(
            str(self.second_sender_device_id),
            response.json()["message"],
        )
        self.assert_nothing_stored()

    def test_duplicate_device_envelopes_are_rejected(self):
        self.authenticate_as("1")
        payload = self.valid_payload()
        payload["envelopes"].append(dict(payload["envelopes"][0]))

        response = self.client.post(
            self.url,
            payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertFalse(response.json()["success"])
        self.assert_nothing_stored()

    def test_new_message_reuses_existing_direct_room(self):
        self.authenticate_as("1")

        first_payload = self.valid_payload()
        first_response = self.client.post(
            self.url,
            first_payload,
            format="json",
        )
        self.assertEqual(
            first_response.status_code,
            status.HTTP_201_CREATED,
        )

        second_payload = self.valid_payload(
            client_message_id=uuid.UUID(
                "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
            ),
            encrypted_payload="SECOND_DIRECT_CIPHERTEXT",
        )
        second_payload["encryption_metadata"]["nonce"] = (
            "SECOND_DIRECT_NONCE"
        )
        second_payload["envelopes"][0][
            "session_reference"
        ] = "second-sender-sync-session"
        second_payload["envelopes"][1][
            "session_reference"
        ] = "second-recipient-ratchet-session"
        second_payload["envelopes"][1][
            "key_wrap_metadata"
        ]["message_number"] = 2

        second_response = self.client.post(
            self.url,
            second_payload,
            format="json",
        )

        self.assertEqual(
            second_response.status_code,
            status.HTTP_201_CREATED,
        )

        first_data = first_response.json()["data"]
        second_data = second_response.json()["data"]

        self.assertEqual(
            first_data["room_id"],
            second_data["room_id"],
        )
        self.assertFalse(second_data["room_created"])
        self.assertTrue(second_data["message_created"])

        self.assertEqual(Room.objects.count(), 1)
        self.assertEqual(RoomMember.objects.count(), 2)
        self.assertEqual(Message.objects.count(), 2)
        self.assertEqual(MessageKeyEnvelope.objects.count(), 4)

    def test_raw_recipient_user_id_is_rejected(self):
        self.authenticate_as("1")

        payload = self.valid_payload()
        payload.pop("recipient_contact_id")
        payload["recipient_user_id"] = "2"

        response = self.client.post(
            self.url,
            payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            response.json()["success"],
            False,
        )
        self.assertIn(
            "recipient",
            response.json()["errors"],
        )

    def test_unsaved_contact_is_blocked(self):
        self.authenticate_as("1")

        self.mock_resolve_contact.side_effect = SavedContactForbiddenError(
            "You must save this contact before messaging."
        )

        response = self.client.post(
            self.url,
            self.valid_payload(),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(
            response.json(),
            {
                "success": False,
                "message": (
                    "You must save this contact before messaging."
                ),
            },
        )

    def test_identity_contact_resolve_failure_returns_503(self):
        self.authenticate_as("1")

        self.mock_resolve_contact.side_effect = IdentityClientError(
            "Identity service is unavailable for saved-contact resolution."
        )

        response = self.client.post(
            self.url,
            self.valid_payload(),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_503_SERVICE_UNAVAILABLE,
        )
        self.assertEqual(
            response.json()["success"],
            False,
        )

    def test_saved_contact_is_resolved_before_sending(self):
        self.authenticate_as("1")

        response = self.client.post(
            self.url,
            self.valid_payload(),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.mock_resolve_contact.assert_called_once()
        call_kwargs = self.mock_resolve_contact.call_args.kwargs

        self.assertEqual(
            call_kwargs["contact_id"],
            self.recipient_contact_id,
        )
        self.assertTrue(
            call_kwargs["authorization_header"].startswith("Bearer ")
        )

    def test_existing_room_allows_send_by_room_id_without_contact(self):
        self.authenticate_as("1")

        first_response = self.client.post(
            self.url,
            self.valid_payload(),
            format="json",
        )

        self.assertEqual(
            first_response.status_code,
            status.HTTP_201_CREATED,
        )

        room_id = first_response.json()["data"]["room_id"]

        self.mock_resolve_contact.side_effect = SavedContactForbiddenError(
            "You must save this contact before messaging."
        )

        second_payload = self.valid_payload(
            client_message_id=uuid.UUID(
                "99999999-9999-4999-8999-999999999999"
            ),
            encrypted_payload="SECOND_MESSAGE_AFTER_CONTACT_DELETE",
        )

        second_payload.pop("recipient_contact_id")
        second_payload["room_id"] = room_id
        second_payload["encryption_metadata"]["nonce"] = (
            "SECOND_MESSAGE_NONCE"
        )
        second_payload["envelopes"][0][
            "session_reference"
        ] = "second-sender-sync-session"
        second_payload["envelopes"][1][
            "session_reference"
        ] = "second-recipient-ratchet-session"
        second_payload["envelopes"][1][
            "key_wrap_metadata"
        ]["message_number"] = 2

        second_response = self.client.post(
            self.url,
            second_payload,
            format="json",
        )

        self.assertEqual(
            second_response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertEqual(
            Message.objects.filter(room_id=room_id).count(),
            2,
        )

        self.assertEqual(
            self.mock_resolve_contact.call_count,
            1,
        )

    def test_deleted_contact_id_cannot_start_or_resolve_message(self):
        self.authenticate_as("1")

        self.mock_resolve_contact.side_effect = SavedContactForbiddenError(
            "You must save this contact before messaging."
        )

        response = self.client.post(
            self.url,
            self.valid_payload(),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(
            response.json(),
            {
                "success": False,
                "message": "You must save this contact before messaging.",
            },
        )

        self.assert_nothing_stored()
    
    def test_blocked_sender_message_is_stored_sender_only(self):
        """
        Directional block rule:

        If user 2 blocks user 1, user 1 must not be able to deliver
        encrypted message envelopes to user 2.

        The sender should not learn the exact reason.
        Backend stores only sender-side device_sync envelopes so sender
        can still see their own sent message, but recipient devices do
        not receive decryptable envelopes.
        """

        ContactDeliveryPolicy.objects.create(
            owner_user_id="2",
            target_user_id="1",
            is_blocked=True,
            policy_version=1,
        )

        self.authenticate_as("1")

        response = self.client.post(
            self.url,
            self.valid_payload(),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
            response.json(),
        )

        data = response.json()["data"]

        self.assertTrue(data["recipient_delivery_blocked"])
        self.assertEqual(data["envelope_count"], 1)

        self.assertEqual(Message.objects.count(), 1)
        self.assertEqual(MessageKeyEnvelope.objects.count(), 1)

        message = Message.objects.get()
        envelope = MessageKeyEnvelope.objects.get()

        self.assertEqual(message.sender_user_id, "1")
        self.assertEqual(envelope.message_id, message.id)
        self.assertEqual(envelope.recipient_device_id, self.sender_device_id)
        self.assertEqual(
            envelope.protocol,
            MessageKeyEnvelope.Protocol.DEVICE_SYNC,
        )

    def test_blocker_can_still_send_to_blocked_contact(self):
        """
        Directional block rule:

        If user 2 blocks user 1, user 2 can still send messages to user 1.
        Blocking hides/protects user 2 from inbound delivery by user 1,
        but it does not prevent user 2 from sending outbound messages.
        """

        ContactDeliveryPolicy.objects.create(
            owner_user_id="2",
            target_user_id="1",
            is_blocked=True,
            policy_version=1,
        )

        self.mock_resolve_contact.return_value = SimpleNamespace(
            contact_id=str(self.recipient_contact_id),
            contact_user_id="1",
            saved_name="Blocked contact",
            contact_number="8888888888",
        )

        self.authenticate_as("2")

        payload = {
            "recipient_contact_id": self.recipient_contact_id,
            "sender_device_id": str(self.recipient_device_id),
            "client_message_id": str(
                uuid.UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
            ),
            "message_type": "text",
            "encrypted_payload": "BLOCKER_OUTBOUND_CIPHERTEXT",
            "encryption_metadata": {
                "algorithm": "xchacha20poly1305",
                "nonce": "BLOCKER_OUTBOUND_NONCE",
            },
            "encryption_version": 1,
            "envelopes": [
                {
                    "recipient_device_id": str(self.recipient_device_id),
                    "protocol": "device_sync",
                    "session_reference": "blocker-sender-sync-session",
                    "wrapped_message_key": "WRAPPED_KEY_FOR_BLOCKER",
                    "key_wrap_metadata": {
                        "algorithm": "device-sync-v1",
                    },
                    "envelope_version": 1,
                },
                {
                    "recipient_device_id": str(self.sender_device_id),
                    "protocol": "double_ratchet",
                    "session_reference": "blocked-contact-ratchet-session",
                    "wrapped_message_key": "WRAPPED_KEY_FOR_BLOCKED_CONTACT",
                    "key_wrap_metadata": {
                        "algorithm": "double-ratchet",
                        "message_number": 1,
                    },
                    "envelope_version": 1,
                },
            ],
        }

        response = self.client.post(
            self.url,
            payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
            response.json(),
        )

        data = response.json()["data"]

        self.assertFalse(data["recipient_delivery_blocked"])
        self.assertEqual(data["envelope_count"], 2)

        self.assertEqual(Message.objects.count(), 1)
        self.assertEqual(MessageKeyEnvelope.objects.count(), 2)

        message = Message.objects.get()

        self.assertEqual(message.sender_user_id, "2")

        envelope_devices = set(
            MessageKeyEnvelope.objects.filter(
                message=message,
            ).values_list("recipient_device_id", flat=True)
        )

        self.assertEqual(
            envelope_devices,
            {
                self.sender_device_id,
                self.recipient_device_id,
            },
        )

    def test_room_id_send_requires_active_membership(self):
        self.authenticate_as("3")

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

        payload = self.valid_payload()
        payload.pop("recipient_contact_id")
        payload["room_id"] = str(room.id)

        response = self.client.post(
            self.url,
            payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_409_CONFLICT,
        )
        self.assertEqual(
            response.json(),
            {
                "success": False,
                "message": "Direct room is unavailable.",
            },
        )

        self.assertEqual(Room.objects.count(), 1)
        self.assertEqual(RoomMember.objects.count(), 2)
        self.assertEqual(Message.objects.count(), 0)
        self.assertEqual(MessageKeyEnvelope.objects.count(), 0)

    def test_room_id_send_rejects_group_room(self):
        self.authenticate_as("1")

        room = Room.objects.create(
            room_type=Room.RoomType.GROUP,
            name="Not direct",
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

        payload = self.valid_payload()
        payload.pop("recipient_contact_id")
        payload["room_id"] = str(room.id)

        response = self.client.post(
            self.url,
            payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_409_CONFLICT,
        )
        self.assertEqual(
            response.json()["success"],
            False,
        )

    def test_cannot_send_with_both_contact_id_and_room_id(self):
        self.authenticate_as("1")

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

        payload = self.valid_payload()
        payload["room_id"] = str(room.id)

        response = self.client.post(
            self.url,
            payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            response.json()["success"],
            False,
        )
        self.assertIn(
            "recipient",
            response.json()["errors"],
        )

    def test_cannot_send_without_contact_id_or_room_id(self):
        self.authenticate_as("1")

        payload = self.valid_payload()
        payload.pop("recipient_contact_id")

        response = self.client.post(
            self.url,
            payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            response.json()["success"],
            False,
        )
        self.assertIn(
            "recipient",
            response.json()["errors"],
        )

import uuid

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.chat_messages.models import (
    GroupMessageEncryption,
    Message,
    MessageRecoveryEnvelope,
)
from apps.e2ee_devices.models import Device, RecoveryBundle
from apps.group_chat.models import (
    GroupEncryptionEpoch,
    GroupSenderKey,
    GroupSenderKeyDistribution,
)
from apps.group_chat.tests.factories import (
    GROUP_MEMBER_USER_ID,
    GROUP_NEW_MEMBER_USER_ID,
    GROUP_OWNER_USER_ID,
    authenticate_client,
    create_group_room,
)
from apps.rooms.models import RoomMember


def create_device(
    *,
    user_id: str,
    is_active: bool = True,
) -> Device:
    return Device.objects.create(
        user_id=user_id,
        device_name="Web",
        platform=Device.Platform.WEB,
        registration_id=12345,
        identity_key_public=f"identity-public-{uuid.uuid4()}",
        signed_prekey_id=1,
        signed_prekey_public=f"signed-prekey-public-{uuid.uuid4()}",
        signed_prekey_signature=f"signature-{uuid.uuid4()}",
        key_algorithm="curve25519",
        key_bundle_version=1,
        is_active=is_active,
    )


def create_recovery_bundle(
    *,
    user_id: str,
    recovery_version: int = 1,
    is_active: bool = True,
) -> RecoveryBundle:
    return RecoveryBundle.objects.create(
        user_id=user_id,
        recovery_public_key=f"recovery-public-{user_id}",
        encrypted_recovery_private_key=f"encrypted-private-{user_id}",
        encryption_metadata={
            "algorithm": "recovery-box-v1",
        },
        recovery_version=recovery_version,
        is_active=is_active,
    )


def create_sender_key(
    *,
    profile,
    sender_user_id: str,
    sender_device: Device,
) -> GroupSenderKey:
    epoch = GroupEncryptionEpoch.objects.get(
        group_room=profile.room,
        status=GroupEncryptionEpoch.Status.ACTIVE,
    )

    return GroupSenderKey.objects.create(
        group_room=profile.room,
        epoch=epoch,
        sender_user_id=sender_user_id,
        sender_device=sender_device,
        sender_key_id=uuid.uuid4(),
        signing_public_key=f"signing-public-{uuid.uuid4()}",
        key_algorithm="group-sender-key-v1",
        signing_algorithm="ed25519",
        key_version=1,
        highest_accepted_iteration=0,
        is_active=True,
    )


def distribute_sender_key_to_device(
    *,
    sender_key: GroupSenderKey,
    recipient_device: Device,
):
    return GroupSenderKeyDistribution.objects.create(
        sender_key=sender_key,
        recipient_user_id=recipient_device.user_id,
        recipient_device=recipient_device,
        encrypted_sender_key=f"encrypted-sender-key-{uuid.uuid4()}",
        distribution_metadata={
            "algorithm": "double-ratchet",
            "session_reference": f"session-{recipient_device.id}",
            "message_number": 1,
            "nonce": "base64-nonce",
        },
        distribution_version=1,
        status="stored",
    )


def recovery_envelope(
    *,
    user_id: str,
    version: int = 1,
    wrapped: str | None = None,
):
    return {
        "recovery_owner_user_id": user_id,
        "recovery_key_version": version,
        "wrapped_message_key": wrapped or f"wrapped-key-{user_id}",
        "key_wrap_metadata": {
            "algorithm": "recovery-box-v1",
            "nonce": f"nonce-{user_id}",
        },
        "envelope_version": 1,
    }


class GroupRecoveryAPITests(APITestCase):
    def send_url(self):
        return reverse("chat_messages:group-message-send")

    def _ready_group(self):
        profile = create_group_room(
            member_user_ids=[
                GROUP_MEMBER_USER_ID,
                GROUP_NEW_MEMBER_USER_ID,
            ],
        )

        owner_device = create_device(user_id=GROUP_OWNER_USER_ID)
        member_device = create_device(user_id=GROUP_MEMBER_USER_ID)
        new_member_device = create_device(user_id=GROUP_NEW_MEMBER_USER_ID)

        sender_key = create_sender_key(
            profile=profile,
            sender_user_id=GROUP_MEMBER_USER_ID,
            sender_device=member_device,
        )

        for device in [
            owner_device,
            new_member_device,
        ]:
            distribute_sender_key_to_device(
                sender_key=sender_key,
                recipient_device=device,
            )

        create_recovery_bundle(
            user_id=GROUP_OWNER_USER_ID,
            recovery_version=2,
        )
        create_recovery_bundle(
            user_id=GROUP_MEMBER_USER_ID,
            recovery_version=1,
        )

        return profile, member_device, sender_key

    def payload(
        self,
        *,
        profile,
        sender_device,
        sender_key,
        client_message_id=None,
        chain_iteration=1,
        recovery_envelopes=None,
    ):
        return {
            "group_id": str(profile.room.id),
            "sender_device_id": str(sender_device.id),
            "client_message_id": str(client_message_id or uuid.uuid4()),
            "epoch_number": sender_key.epoch.epoch_number,
            "sender_key_id": str(sender_key.sender_key_id),
            "chain_iteration": chain_iteration,
            "message_type": "text",
            "encrypted_payload": "base64-group-ciphertext",
            "encryption_metadata": {
                "algorithm": "group-sender-key-v1",
                "nonce": "group-nonce",
                "content_encoding": "myna-message-v1",
            },
            "signature": "base64-signature",
            "reply_to_message_id": None,
            "client_sent_at": "2026-06-27T00:00:00Z",
            "recovery_envelopes": recovery_envelopes
            if recovery_envelopes is not None
            else [
                recovery_envelope(
                    user_id=GROUP_OWNER_USER_ID,
                    version=2,
                ),
                recovery_envelope(
                    user_id=GROUP_MEMBER_USER_ID,
                    version=1,
                ),
            ],
        }

    def test_group_send_creates_recovery_envelopes_atomically(self):
        profile, sender_device, sender_key = self._ready_group()
        authenticate_client(self.client, GROUP_MEMBER_USER_ID)

        response = self.client.post(
            self.send_url(),
            self.payload(
                profile=profile,
                sender_device=sender_device,
                sender_key=sender_key,
            ),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Message.objects.count(), 1)
        self.assertEqual(GroupMessageEncryption.objects.count(), 1)
        self.assertEqual(MessageRecoveryEnvelope.objects.count(), 2)

        owners = set(
            MessageRecoveryEnvelope.objects.values_list(
                "recovery_owner_user_id",
                flat=True,
            )
        )

        self.assertEqual(
            owners,
            {
                GROUP_OWNER_USER_ID,
                GROUP_MEMBER_USER_ID,
            },
        )

    def test_missing_recovery_envelope_is_rejected(self):
        profile, sender_device, sender_key = self._ready_group()
        authenticate_client(self.client, GROUP_MEMBER_USER_ID)

        response = self.client.post(
            self.send_url(),
            self.payload(
                profile=profile,
                sender_device=sender_device,
                sender_key=sender_key,
                recovery_envelopes=[
                    recovery_envelope(
                        user_id=GROUP_OWNER_USER_ID,
                        version=2,
                    ),
                ],
            ),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Message.objects.count(), 0)
        self.assertEqual(MessageRecoveryEnvelope.objects.count(), 0)

    def test_unexpected_nonmember_recovery_envelope_is_rejected(self):
        profile, sender_device, sender_key = self._ready_group()
        authenticate_client(self.client, GROUP_MEMBER_USER_ID)

        response = self.client.post(
            self.send_url(),
            self.payload(
                profile=profile,
                sender_device=sender_device,
                sender_key=sender_key,
                recovery_envelopes=[
                    recovery_envelope(
                        user_id=GROUP_OWNER_USER_ID,
                        version=2,
                    ),
                    recovery_envelope(
                        user_id=GROUP_MEMBER_USER_ID,
                        version=1,
                    ),
                    recovery_envelope(
                        user_id="999",
                        version=1,
                    ),
                ],
            ),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Message.objects.count(), 0)
        self.assertEqual(MessageRecoveryEnvelope.objects.count(), 0)

    def test_stale_recovery_version_is_rejected(self):
        profile, sender_device, sender_key = self._ready_group()
        authenticate_client(self.client, GROUP_MEMBER_USER_ID)

        response = self.client.post(
            self.send_url(),
            self.payload(
                profile=profile,
                sender_device=sender_device,
                sender_key=sender_key,
                recovery_envelopes=[
                    recovery_envelope(
                        user_id=GROUP_OWNER_USER_ID,
                        version=1,
                    ),
                    recovery_envelope(
                        user_id=GROUP_MEMBER_USER_ID,
                        version=1,
                    ),
                ],
            ),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(Message.objects.count(), 0)
        self.assertEqual(MessageRecoveryEnvelope.objects.count(), 0)

    def test_removed_member_recovery_envelope_is_rejected(self):
        profile, sender_device, sender_key = self._ready_group()

        removed_member = RoomMember.objects.get(
            room=profile.room,
            user_id=GROUP_NEW_MEMBER_USER_ID,
        )
        removed_member.is_active = False
        removed_member.removed_by_user_id = GROUP_OWNER_USER_ID
        removed_member.save(
            update_fields=[
                "is_active",
                "removed_by_user_id",
            ]
        )

        create_recovery_bundle(
            user_id=GROUP_NEW_MEMBER_USER_ID,
            recovery_version=1,
        )

        authenticate_client(self.client, GROUP_MEMBER_USER_ID)

        response = self.client.post(
            self.send_url(),
            self.payload(
                profile=profile,
                sender_device=sender_device,
                sender_key=sender_key,
                recovery_envelopes=[
                    recovery_envelope(
                        user_id=GROUP_OWNER_USER_ID,
                        version=2,
                    ),
                    recovery_envelope(
                        user_id=GROUP_MEMBER_USER_ID,
                        version=1,
                    ),
                    recovery_envelope(
                        user_id=GROUP_NEW_MEMBER_USER_ID,
                        version=1,
                    ),
                ],
            ),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_exact_retry_includes_recovery_envelope_equality(self):
        profile, sender_device, sender_key = self._ready_group()
        client_message_id = uuid.uuid4()

        payload = self.payload(
            profile=profile,
            sender_device=sender_device,
            sender_key=sender_key,
            client_message_id=client_message_id,
        )

        authenticate_client(self.client, GROUP_MEMBER_USER_ID)

        first_response = self.client.post(
            self.send_url(),
            payload,
            format="json",
        )
        second_response = self.client.post(
            self.send_url(),
            payload,
            format="json",
        )

        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second_response.status_code, status.HTTP_200_OK)
        self.assertEqual(Message.objects.count(), 1)
        self.assertEqual(MessageRecoveryEnvelope.objects.count(), 2)

    def test_changed_recovery_envelope_retry_conflicts(self):
        profile, sender_device, sender_key = self._ready_group()
        client_message_id = uuid.uuid4()

        payload = self.payload(
            profile=profile,
            sender_device=sender_device,
            sender_key=sender_key,
            client_message_id=client_message_id,
        )

        changed_payload = self.payload(
            profile=profile,
            sender_device=sender_device,
            sender_key=sender_key,
            client_message_id=client_message_id,
            recovery_envelopes=[
                recovery_envelope(
                    user_id=GROUP_OWNER_USER_ID,
                    version=2,
                    wrapped="changed-wrapped-key",
                ),
                recovery_envelope(
                    user_id=GROUP_MEMBER_USER_ID,
                    version=1,
                ),
            ],
        )

        authenticate_client(self.client, GROUP_MEMBER_USER_ID)

        first_response = self.client.post(
            self.send_url(),
            payload,
            format="json",
        )
        changed_response = self.client.post(
            self.send_url(),
            changed_payload,
            format="json",
        )

        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(changed_response.status_code, status.HTTP_409_CONFLICT)

    def test_group_message_recovery_envelopes_do_not_store_plaintext(self):
        profile, sender_device, sender_key = self._ready_group()
        authenticate_client(self.client, GROUP_MEMBER_USER_ID)

        response = self.client.post(
            self.send_url(),
            self.payload(
                profile=profile,
                sender_device=sender_device,
                sender_key=sender_key,
            ),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        envelope = MessageRecoveryEnvelope.objects.first()
        self.assertIsNotNone(envelope)
        self.assertNotIn(
            "plaintext",
            envelope.key_wrap_metadata,
        )
        self.assertNotIn(
            "private_key",
            envelope.key_wrap_metadata,
        )
import uuid

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.e2ee_devices.models import Device
from apps.group_chat.constants import (
    GROUP_AUDIT_SENDER_KEY_DISTRIBUTED,
    GROUP_AUDIT_SENDER_KEY_DISTRIBUTION_ACKED,
)
from apps.group_chat.models import (
    GroupAuditEvent,
    GroupEncryptionEpoch,
    GroupSenderKey,
    GroupSenderKeyDistribution,
)
from apps.rooms.models import Room, RoomMember

from .factories import (
    GROUP_ADMIN_USER_ID,
    GROUP_MEMBER_USER_ID,
    GROUP_NEW_MEMBER_USER_ID,
    GROUP_OUTSIDER_USER_ID,
    GROUP_OWNER_USER_ID,
    authenticate_client,
    create_group_room,
)


def create_device(
    *,
    user_id: str,
    is_active: bool = True,
    device_name: str = "Web",
) -> Device:
    return Device.objects.create(
        user_id=user_id,
        device_name=device_name,
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


def sender_key_payload(
    *,
    device: Device,
    epoch_number: int = 1,
    sender_key_id=None,
    signing_public_key: str = "sender-signing-public-key",
):
    return {
        "sender_device_id": str(device.id),
        "epoch_number": epoch_number,
        "sender_key_id": str(sender_key_id or uuid.uuid4()),
        "signing_public_key": signing_public_key,
        "key_algorithm": "group-sender-key-v1",
        "signing_algorithm": "ed25519",
        "key_version": 1,
    }


def distribution_item(
    *,
    recipient_device: Device,
    encrypted_sender_key: str = "encrypted-sender-key",
):
    return {
        "recipient_user_id": recipient_device.user_id,
        "recipient_device_id": str(recipient_device.id),
        "encrypted_sender_key": encrypted_sender_key,
        "distribution_metadata": {
            "algorithm": "double-ratchet",
            "session_reference": f"session-{recipient_device.id}",
            "message_number": 1,
            "nonce": "base64-nonce",
        },
        "distribution_version": 1,
    }


class GroupSenderKeyDistributionAPITests(APITestCase):
    def roster_url(self, group_id):
        return reverse(
            "group_chat:group-device-roster",
            kwargs={"group_id": group_id},
        )

    def register_url(self, group_id):
        return reverse(
            "group_chat:group-sender-key-register",
            kwargs={"group_id": group_id},
        )

    def distributions_url(self, group_id, sender_key_id):
        return reverse(
            "group_chat:group-sender-key-distributions",
            kwargs={
                "group_id": group_id,
                "sender_key_id": sender_key_id,
            },
        )

    def pending_url(self, group_id, sender_key_id):
        return reverse(
            "group_chat:group-sender-key-pending",
            kwargs={
                "group_id": group_id,
                "sender_key_id": sender_key_id,
            },
        )

    def inbox_url(self, group_id):
        return reverse(
            "group_chat:group-sender-key-distribution-inbox",
            kwargs={"group_id": group_id},
        )

    def acknowledge_url(self, group_id):
        return reverse(
            "group_chat:group-sender-key-distribution-acknowledge",
            kwargs={"group_id": group_id},
        )

    def _register_sender_key(
        self,
        *,
        profile,
        sender_user_id=GROUP_MEMBER_USER_ID,
        sender_device=None,
    ):
        sender_device = sender_device or create_device(
            user_id=sender_user_id,
        )

        authenticate_client(self.client, sender_user_id)

        response = self.client.post(
            self.register_url(profile.room.id),
            sender_key_payload(device=sender_device),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        return response.json()["data"], sender_device

    def test_roster_returns_only_active_member_devices(self):
        profile = create_group_room(
            member_user_ids=[
                GROUP_MEMBER_USER_ID,
                GROUP_NEW_MEMBER_USER_ID,
            ],
        )
        owner_device = create_device(user_id=GROUP_OWNER_USER_ID)
        member_device = create_device(user_id=GROUP_MEMBER_USER_ID)
        create_device(user_id=GROUP_OUTSIDER_USER_ID)
        create_device(
            user_id=GROUP_NEW_MEMBER_USER_ID,
            is_active=False,
        )

        authenticate_client(self.client, GROUP_OWNER_USER_ID)

        response = self.client.get(
            self.roster_url(profile.room.id),
            {
                "epoch_number": 1,
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        device_ids = {
            item["device_id"]
            for item in response.json()["data"]
        }

        self.assertEqual(
            device_ids,
            {
                str(owner_device.id),
                str(member_device.id),
            },
        )

        first = response.json()["data"][0]
        self.assertIn("identity_key_public", first)
        self.assertIn("signed_prekey_public", first)
        self.assertNotIn("encrypted_recovery_private_key", first)

    def test_non_member_cannot_fetch_roster(self):
        profile = create_group_room()
        authenticate_client(self.client, GROUP_OUTSIDER_USER_ID)

        response = self.client.get(
            self.roster_url(profile.room.id),
            {
                "epoch_number": 1,
            },
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_sender_can_store_distribution_to_required_device(self):
        profile = create_group_room()
        sender_data, sender_device = self._register_sender_key(
            profile=profile,
        )
        recipient_device = create_device(user_id=GROUP_OWNER_USER_ID)

        authenticate_client(self.client, GROUP_MEMBER_USER_ID)

        response = self.client.post(
            self.distributions_url(
                profile.room.id,
                sender_data["sender_key_id"],
            ),
            {
                "epoch_number": 1,
                "distributions": [
                    distribution_item(
                        recipient_device=recipient_device,
                    ),
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.json()["data"]["created_count"], 1)
        self.assertEqual(GroupSenderKeyDistribution.objects.count(), 1)

    def test_sender_device_can_be_omitted_from_required_distribution(self):
        profile = create_group_room()
        sender_data, sender_device = self._register_sender_key(
            profile=profile,
        )
        owner_device = create_device(user_id=GROUP_OWNER_USER_ID)

        authenticate_client(self.client, GROUP_MEMBER_USER_ID)

        response = self.client.post(
            self.distributions_url(
                profile.room.id,
                sender_data["sender_key_id"],
            ),
            {
                "epoch_number": 1,
                "distributions": [
                    distribution_item(
                        recipient_device=owner_device,
                    ),
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            response.json()["data"]["missing_required_device_ids"],
            [],
        )
        self.assertTrue(response.json()["data"]["is_send_ready"])

    def test_missing_required_device_is_reported_not_failed(self):
        profile = create_group_room()
        sender_data, sender_device = self._register_sender_key(
            profile=profile,
        )
        owner_device = create_device(user_id=GROUP_OWNER_USER_ID)
        admin_device = create_device(user_id=GROUP_ADMIN_USER_ID)

        RoomMember.objects.create(
            room=profile.room,
            user_id=GROUP_ADMIN_USER_ID,
            role=RoomMember.Role.ADMIN,
            added_by_user_id=GROUP_OWNER_USER_ID,
            is_active=True,
        )

        authenticate_client(self.client, GROUP_MEMBER_USER_ID)

        response = self.client.post(
            self.distributions_url(
                profile.room.id,
                sender_data["sender_key_id"],
            ),
            {
                "epoch_number": 1,
                "distributions": [
                    distribution_item(
                        recipient_device=owner_device,
                    ),
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn(
            str(admin_device.id),
            response.json()["data"]["missing_required_device_ids"],
        )
        self.assertFalse(response.json()["data"]["is_send_ready"])

    def test_unexpected_recipient_is_rejected(self):
        profile = create_group_room()
        sender_data, sender_device = self._register_sender_key(
            profile=profile,
        )
        outsider_device = create_device(user_id=GROUP_OUTSIDER_USER_ID)

        authenticate_client(self.client, GROUP_MEMBER_USER_ID)

        response = self.client.post(
            self.distributions_url(
                profile.room.id,
                sender_data["sender_key_id"],
            ),
            {
                "epoch_number": 1,
                "distributions": [
                    distribution_item(
                        recipient_device=outsider_device,
                    ),
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(GroupSenderKeyDistribution.objects.count(), 0)

    def test_non_owner_of_sender_key_cannot_store_distributions(self):
        profile = create_group_room()
        sender_data, sender_device = self._register_sender_key(
            profile=profile,
        )
        owner_device = create_device(user_id=GROUP_OWNER_USER_ID)

        authenticate_client(self.client, GROUP_OWNER_USER_ID)

        response = self.client.post(
            self.distributions_url(
                profile.room.id,
                sender_data["sender_key_id"],
            ),
            {
                "epoch_number": 1,
                "distributions": [
                    distribution_item(
                        recipient_device=owner_device,
                    ),
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_exact_distribution_retry_is_idempotent(self):
        profile = create_group_room()
        sender_data, sender_device = self._register_sender_key(
            profile=profile,
        )
        owner_device = create_device(user_id=GROUP_OWNER_USER_ID)
        payload = {
            "epoch_number": 1,
            "distributions": [
                distribution_item(
                    recipient_device=owner_device,
                ),
            ],
        }

        authenticate_client(self.client, GROUP_MEMBER_USER_ID)

        first_response = self.client.post(
            self.distributions_url(
                profile.room.id,
                sender_data["sender_key_id"],
            ),
            payload,
            format="json",
        )
        second_response = self.client.post(
            self.distributions_url(
                profile.room.id,
                sender_data["sender_key_id"],
            ),
            payload,
            format="json",
        )

        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second_response.json()["data"]["existing_count"], 1)
        self.assertEqual(GroupSenderKeyDistribution.objects.count(), 1)

    def test_changed_distribution_retry_returns_conflict(self):
        profile = create_group_room()
        sender_data, sender_device = self._register_sender_key(
            profile=profile,
        )
        owner_device = create_device(user_id=GROUP_OWNER_USER_ID)

        authenticate_client(self.client, GROUP_MEMBER_USER_ID)

        first_response = self.client.post(
            self.distributions_url(
                profile.room.id,
                sender_data["sender_key_id"],
            ),
            {
                "epoch_number": 1,
                "distributions": [
                    distribution_item(
                        recipient_device=owner_device,
                        encrypted_sender_key="ciphertext-one",
                    ),
                ],
            },
            format="json",
        )
        changed_response = self.client.post(
            self.distributions_url(
                profile.room.id,
                sender_data["sender_key_id"],
            ),
            {
                "epoch_number": 1,
                "distributions": [
                    distribution_item(
                        recipient_device=owner_device,
                        encrypted_sender_key="ciphertext-two",
                    ),
                ],
            },
            format="json",
        )

        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            changed_response.status_code,
            status.HTTP_409_CONFLICT,
        )

    def test_stale_epoch_is_rejected(self):
        profile = create_group_room()
        sender_data, sender_device = self._register_sender_key(
            profile=profile,
            sender_user_id=GROUP_OWNER_USER_ID,
        )
        recipient_device = create_device(user_id=GROUP_MEMBER_USER_ID)

        authenticate_client(self.client, GROUP_OWNER_USER_ID)
        rotate_response = self.client.post(
            reverse(
                "group_chat:group-epoch-rotate",
                kwargs={"group_id": profile.room.id},
            ),
            {
                "reason": "manual",
            },
            format="json",
        )
        self.assertEqual(rotate_response.status_code, status.HTTP_200_OK)

        response = self.client.post(
            self.distributions_url(
                profile.room.id,
                sender_data["sender_key_id"],
            ),
            {
                "epoch_number": 1,
                "distributions": [
                    distribution_item(
                        recipient_device=recipient_device,
                    ),
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_pending_reports_coverage(self):
        profile = create_group_room()
        sender_data, sender_device = self._register_sender_key(
            profile=profile,
        )
        owner_device = create_device(user_id=GROUP_OWNER_USER_ID)

        authenticate_client(self.client, GROUP_MEMBER_USER_ID)

        before_response = self.client.get(
            self.pending_url(
                profile.room.id,
                sender_data["sender_key_id"],
            )
        )
        self.assertEqual(before_response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            before_response.json()["data"]["pending_device_count"],
            1,
        )
        self.assertFalse(before_response.json()["data"]["is_send_ready"])

        store_response = self.client.post(
            self.distributions_url(
                profile.room.id,
                sender_data["sender_key_id"],
            ),
            {
                "epoch_number": 1,
                "distributions": [
                    distribution_item(
                        recipient_device=owner_device,
                    ),
                ],
            },
            format="json",
        )
        self.assertEqual(store_response.status_code, status.HTTP_201_CREATED)

        after_response = self.client.get(
            self.pending_url(
                profile.room.id,
                sender_data["sender_key_id"],
            )
        )
        self.assertEqual(after_response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            after_response.json()["data"]["pending_device_count"],
            0,
        )
        self.assertTrue(after_response.json()["data"]["is_send_ready"])

    def test_device_specific_inbox_returns_only_that_device(self):
        profile = create_group_room()
        sender_data, sender_device = self._register_sender_key(
            profile=profile,
        )
        owner_device = create_device(user_id=GROUP_OWNER_USER_ID)

        authenticate_client(self.client, GROUP_MEMBER_USER_ID)
        store_response = self.client.post(
            self.distributions_url(
                profile.room.id,
                sender_data["sender_key_id"],
            ),
            {
                "epoch_number": 1,
                "distributions": [
                    distribution_item(
                        recipient_device=owner_device,
                    ),
                ],
            },
            format="json",
        )
        self.assertEqual(store_response.status_code, status.HTTP_201_CREATED)

        authenticate_client(self.client, GROUP_OWNER_USER_ID)

        response = self.client.get(
            self.inbox_url(profile.room.id),
            {
                "device_id": str(owner_device.id),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()["data"]), 1)
        self.assertEqual(
            response.json()["data"][0]["recipient_device_id"],
            str(owner_device.id),
        )

    def test_user_cannot_read_another_devices_inbox(self):
        profile = create_group_room()
        owner_device = create_device(user_id=GROUP_OWNER_USER_ID)

        authenticate_client(self.client, GROUP_MEMBER_USER_ID)

        response = self.client.get(
            self.inbox_url(profile.room.id),
            {
                "device_id": str(owner_device.id),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_acknowledge_marks_distributions_acknowledged(self):
        profile = create_group_room()
        sender_data, sender_device = self._register_sender_key(
            profile=profile,
        )
        owner_device = create_device(user_id=GROUP_OWNER_USER_ID)

        authenticate_client(self.client, GROUP_MEMBER_USER_ID)
        store_response = self.client.post(
            self.distributions_url(
                profile.room.id,
                sender_data["sender_key_id"],
            ),
            {
                "epoch_number": 1,
                "distributions": [
                    distribution_item(
                        recipient_device=owner_device,
                    ),
                ],
            },
            format="json",
        )
        distribution_id = store_response.json()["data"]["distributions"][0]["id"]

        authenticate_client(self.client, GROUP_OWNER_USER_ID)

        response = self.client.post(
            self.acknowledge_url(profile.room.id),
            {
                "device_id": str(owner_device.id),
                "distribution_ids": [distribution_id],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        distribution = GroupSenderKeyDistribution.objects.get(
            id=distribution_id,
        )
        self.assertEqual(distribution.status, "acknowledged")
        self.assertIsNotNone(distribution.acknowledged_at)

    def test_acknowledge_is_idempotent(self):
        profile = create_group_room()
        sender_data, sender_device = self._register_sender_key(
            profile=profile,
        )
        owner_device = create_device(user_id=GROUP_OWNER_USER_ID)

        authenticate_client(self.client, GROUP_MEMBER_USER_ID)
        store_response = self.client.post(
            self.distributions_url(
                profile.room.id,
                sender_data["sender_key_id"],
            ),
            {
                "epoch_number": 1,
                "distributions": [
                    distribution_item(
                        recipient_device=owner_device,
                    ),
                ],
            },
            format="json",
        )
        distribution_id = store_response.json()["data"]["distributions"][0]["id"]

        authenticate_client(self.client, GROUP_OWNER_USER_ID)

        first_response = self.client.post(
            self.acknowledge_url(profile.room.id),
            {
                "device_id": str(owner_device.id),
                "distribution_ids": [distribution_id],
            },
            format="json",
        )
        second_response = self.client.post(
            self.acknowledge_url(profile.room.id),
            {
                "device_id": str(owner_device.id),
                "distribution_ids": [distribution_id],
            },
            format="json",
        )

        self.assertEqual(first_response.status_code, status.HTTP_200_OK)
        self.assertEqual(second_response.status_code, status.HTTP_200_OK)

    def test_distribution_upload_writes_audit_event(self):
        profile = create_group_room()
        sender_data, sender_device = self._register_sender_key(
            profile=profile,
        )
        owner_device = create_device(user_id=GROUP_OWNER_USER_ID)

        authenticate_client(self.client, GROUP_MEMBER_USER_ID)

        response = self.client.post(
            self.distributions_url(
                profile.room.id,
                sender_data["sender_key_id"],
            ),
            {
                "epoch_number": 1,
                "distributions": [
                    distribution_item(
                        recipient_device=owner_device,
                    ),
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        event = GroupAuditEvent.objects.get(
            event_type=GROUP_AUDIT_SENDER_KEY_DISTRIBUTED,
        )
        self.assertEqual(event.actor_user_id, GROUP_MEMBER_USER_ID)
        self.assertEqual(event.metadata["created_count"], 1)

    def test_acknowledge_writes_audit_event(self):
        profile = create_group_room()
        sender_data, sender_device = self._register_sender_key(
            profile=profile,
        )
        owner_device = create_device(user_id=GROUP_OWNER_USER_ID)

        authenticate_client(self.client, GROUP_MEMBER_USER_ID)
        store_response = self.client.post(
            self.distributions_url(
                profile.room.id,
                sender_data["sender_key_id"],
            ),
            {
                "epoch_number": 1,
                "distributions": [
                    distribution_item(
                        recipient_device=owner_device,
                    ),
                ],
            },
            format="json",
        )
        distribution_id = store_response.json()["data"]["distributions"][0]["id"]

        authenticate_client(self.client, GROUP_OWNER_USER_ID)
        response = self.client.post(
            self.acknowledge_url(profile.room.id),
            {
                "device_id": str(owner_device.id),
                "distribution_ids": [distribution_id],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        event = GroupAuditEvent.objects.get(
            event_type=GROUP_AUDIT_SENDER_KEY_DISTRIBUTION_ACKED,
        )
        self.assertEqual(event.actor_user_id, GROUP_OWNER_USER_ID)
        self.assertEqual(event.metadata["changed_count"], 1)

    def test_direct_room_cannot_have_distribution(self):
        profile = create_group_room()
        sender_device = create_device(user_id=GROUP_OWNER_USER_ID)
        recipient_device = create_device(user_id=GROUP_MEMBER_USER_ID)
        epoch = GroupEncryptionEpoch.objects.get(
            group_room=profile.room,
            status=GroupEncryptionEpoch.Status.ACTIVE,
        )
        sender_key = GroupSenderKey.objects.create(
            group_room=profile.room,
            epoch=epoch,
            sender_user_id=GROUP_OWNER_USER_ID,
            sender_device=sender_device,
            sender_key_id=uuid.uuid4(),
            signing_public_key="public-key",
            key_algorithm="group-sender-key-v1",
            signing_algorithm="ed25519",
            key_version=1,
        )

        distribution = GroupSenderKeyDistribution(
            sender_key=sender_key,
            recipient_user_id=GROUP_MEMBER_USER_ID,
            recipient_device=sender_key.sender_device,
            encrypted_sender_key="ciphertext",
            distribution_metadata={
                "algorithm": "double-ratchet",
            },
            distribution_version=1,
        )

        with self.assertRaises(ValidationError):
            distribution.full_clean()

    def test_database_unique_sender_key_recipient_device_constraint(self):
        profile = create_group_room()
        sender_device = create_device(user_id=GROUP_OWNER_USER_ID)
        recipient_device = create_device(user_id=GROUP_MEMBER_USER_ID)
        epoch = GroupEncryptionEpoch.objects.get(
            group_room=profile.room,
            status=GroupEncryptionEpoch.Status.ACTIVE,
        )
        sender_key = GroupSenderKey.objects.create(
            group_room=profile.room,
            epoch=epoch,
            sender_user_id=GROUP_OWNER_USER_ID,
            sender_device=sender_device,
            sender_key_id=uuid.uuid4(),
            signing_public_key="public-key",
            key_algorithm="group-sender-key-v1",
            signing_algorithm="ed25519",
            key_version=1,
        )

        GroupSenderKeyDistribution.objects.create(
            sender_key=sender_key,
            recipient_user_id=GROUP_MEMBER_USER_ID,
            recipient_device=recipient_device,
            encrypted_sender_key="ciphertext-one",
            distribution_metadata={
                "algorithm": "double-ratchet",
            },
            distribution_version=1,
        )

        with self.assertRaises(IntegrityError):
            GroupSenderKeyDistribution.objects.create(
                sender_key=sender_key,
                recipient_user_id=GROUP_MEMBER_USER_ID,
                recipient_device=recipient_device,
                encrypted_sender_key="ciphertext-two",
                distribution_metadata={
                    "algorithm": "double-ratchet",
                },
                distribution_version=1,
            )

    def test_model_has_no_secret_distribution_fields(self):
        field_names = {
            field.name
            for field in GroupSenderKeyDistribution._meta.fields
        }

        forbidden = {
            "sender_chain_secret",
            "signing_private_key",
            "private_key",
            "message_key",
            "plaintext",
            "ratchet_state",
            "recovery_key",
        }

        self.assertTrue(field_names.isdisjoint(forbidden))
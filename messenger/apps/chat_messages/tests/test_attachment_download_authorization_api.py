import uuid
from datetime import timedelta

from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.chat_messages.models import (
    EncryptedAttachment,
    Message,
    MessageKeyEnvelope,
)
from apps.chat_messages.tests.test_message_attachment_linking_api import (
    create_completed_attachment,
    create_device,
)
from apps.group_chat.tests.factories import (
    GROUP_MEMBER_USER_ID,
    GROUP_NEW_MEMBER_USER_ID,
    GROUP_OUTSIDER_USER_ID,
    GROUP_OWNER_USER_ID,
    authenticate_client,
    create_group_room,
)
from apps.rooms.models import Room, RoomMember


@override_settings(
    CLOUDINARY_URL="cloudinary://public-api-key:private-api-secret@test-cloud",
    CLOUDINARY_FOLDER="myna/test/attachments",
    ATTACHMENT_CLOUDINARY_RESOURCE_TYPE="raw",
    ATTACHMENT_DOWNLOAD_URL_TTL_SECONDS=300,
    ATTACHMENT_DOWNLOAD_URL_MAX_TTL_SECONDS=900,
)
class AttachmentDownloadAuthorizationAPITests(APITestCase):
    def download_url(self, attachment_id):
        return reverse(
            "chat_messages:encrypted-attachment-download",
            kwargs={
                "attachment_id": attachment_id,
            },
        )

    def create_direct_room(
        self,
        *,
        sender_user_id: str,
        recipient_user_id: str,
    ):
        room = Room.objects.create(
            room_type=Room.RoomType.DIRECT,
            created_by_user_id=sender_user_id,
            direct_pair_key=Room.build_direct_pair_key(
                sender_user_id,
                recipient_user_id,
            ),
            is_active=True,
        )

        RoomMember.objects.create(
            room=room,
            user_id=sender_user_id,
            role=RoomMember.Role.MEMBER,
            added_by_user_id=sender_user_id,
            is_active=True,
        )
        RoomMember.objects.create(
            room=room,
            user_id=recipient_user_id,
            role=RoomMember.Role.MEMBER,
            added_by_user_id=sender_user_id,
            is_active=True,
        )

        return room

    def create_message(
        self,
        *,
        room,
        sender_user_id,
        sender_device,
        message_type="file",
    ):
        return Message.objects.create(
            room=room,
            sender_user_id=sender_user_id,
            sender_device_id=str(sender_device.id),
            client_message_id=uuid.uuid4(),
            message_type=message_type,
            encrypted_payload="ENCRYPTED_PAYLOAD",
            encryption_metadata={
                "algorithm": "xchacha20poly1305",
                "nonce": "base64-nonce",
            },
            encryption_version=1,
        )

    def attach_to_message(
        self,
        *,
        attachment,
        room,
        message,
    ):
        attachment.attached_room = room
        attachment.attached_message = message
        attachment.attached_at = timezone.now()
        attachment.upload_status = EncryptedAttachment.UploadStatus.ATTACHED
        attachment.save(
            update_fields=[
                "attached_room",
                "attached_message",
                "attached_at",
                "upload_status",
            ]
        )
        return attachment

    def create_direct_attached_attachment(
        self,
        *,
        sender_user_id=GROUP_OWNER_USER_ID,
        recipient_user_id=GROUP_MEMBER_USER_ID,
        include_recipient_envelope=True,
    ):
        sender_device = create_device(
            user_id=sender_user_id,
        )
        recipient_device = create_device(
            user_id=recipient_user_id,
        )

        room = self.create_direct_room(
            sender_user_id=sender_user_id,
            recipient_user_id=recipient_user_id,
        )

        message = self.create_message(
            room=room,
            sender_user_id=sender_user_id,
            sender_device=sender_device,
        )

        if include_recipient_envelope:
            MessageKeyEnvelope.objects.create(
                message=message,
                recipient_user_id=recipient_user_id,
                recipient_device=recipient_device,
                protocol=MessageKeyEnvelope.Protocol.DOUBLE_RATCHET,
                session_reference="recipient-session",
                wrapped_message_key="WRAPPED_KEY_FOR_RECIPIENT",
                key_wrap_metadata={
                    "algorithm": "double-ratchet",
                    "message_number": 1,
                },
                envelope_version=1,
            )

        attachment = create_completed_attachment(
            user_id=sender_user_id,
            device=sender_device,
        )

        self.attach_to_message(
            attachment=attachment,
            room=room,
            message=message,
        )

        return {
            "room": room,
            "message": message,
            "attachment": attachment,
            "sender_device": sender_device,
            "recipient_device": recipient_device,
        }

    def test_uploader_can_download_own_completed_attachment(self):
        device = create_device(
            user_id=GROUP_OWNER_USER_ID,
        )
        attachment = create_completed_attachment(
            user_id=GROUP_OWNER_USER_ID,
            device=device,
        )

        authenticate_client(
            self.client,
            GROUP_OWNER_USER_ID,
        )

        response = self.client.get(
            self.download_url(attachment.id),
            {
                "device_id": str(device.id),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()["data"]

        self.assertEqual(
            data["attachment"]["id"],
            str(attachment.id),
        )
        self.assertEqual(
            data["attachment"]["ciphertext_sha256"],
            "a" * 64,
        )
        self.assertEqual(
            data["attachment"]["ciphertext_size"],
            4096,
        )
        self.assertIn("download_url", data)
        self.assertIn("expires_at", data)
        self.assertNotIn("api_secret", data)
        self.assertNotIn("private-api-secret", str(data))

    def test_direct_recipient_can_download_when_message_has_device_envelope(self):
        setup = self.create_direct_attached_attachment(
            include_recipient_envelope=True,
        )

        authenticate_client(
            self.client,
            GROUP_MEMBER_USER_ID,
        )

        response = self.client.get(
            self.download_url(setup["attachment"].id),
            {
                "device_id": str(setup["recipient_device"].id),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_direct_recipient_cannot_download_sender_only_blocked_attachment(self):
        setup = self.create_direct_attached_attachment(
            include_recipient_envelope=False,
        )

        authenticate_client(
            self.client,
            GROUP_MEMBER_USER_ID,
        )

        response = self.client.get(
            self.download_url(setup["attachment"].id),
            {
                "device_id": str(setup["recipient_device"].id),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_non_room_user_cannot_download_direct_attachment(self):
        setup = self.create_direct_attached_attachment(
            include_recipient_envelope=True,
        )

        outsider_device = create_device(
            user_id=GROUP_OUTSIDER_USER_ID,
        )

        authenticate_client(
            self.client,
            GROUP_OUTSIDER_USER_ID,
        )

        response = self.client.get(
            self.download_url(setup["attachment"].id),
            {
                "device_id": str(outsider_device.id),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_group_active_member_can_download_group_attachment(self):
        profile = create_group_room(
            member_user_ids=[
                GROUP_MEMBER_USER_ID,
                GROUP_NEW_MEMBER_USER_ID,
            ],
        )

        sender_device = create_device(
            user_id=GROUP_MEMBER_USER_ID,
        )
        owner_device = create_device(
            user_id=GROUP_OWNER_USER_ID,
        )

        message = self.create_message(
            room=profile.room,
            sender_user_id=GROUP_MEMBER_USER_ID,
            sender_device=sender_device,
        )

        attachment = create_completed_attachment(
            user_id=GROUP_MEMBER_USER_ID,
            device=sender_device,
        )

        self.attach_to_message(
            attachment=attachment,
            room=profile.room,
            message=message,
        )

        authenticate_client(
            self.client,
            GROUP_OWNER_USER_ID,
        )

        response = self.client.get(
            self.download_url(attachment.id),
            {
                "device_id": str(owner_device.id),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_inactive_group_member_cannot_download_group_attachment(self):
        profile = create_group_room(
            member_user_ids=[
                GROUP_MEMBER_USER_ID,
                GROUP_NEW_MEMBER_USER_ID,
            ],
        )

        sender_device = create_device(
            user_id=GROUP_MEMBER_USER_ID,
        )
        owner_device = create_device(
            user_id=GROUP_OWNER_USER_ID,
        )

        RoomMember.objects.filter(
            room=profile.room,
            user_id=GROUP_OWNER_USER_ID,
        ).update(
            is_active=False,
            left_at=timezone.now(),
        )

        message = self.create_message(
            room=profile.room,
            sender_user_id=GROUP_MEMBER_USER_ID,
            sender_device=sender_device,
        )

        attachment = create_completed_attachment(
            user_id=GROUP_MEMBER_USER_ID,
            device=sender_device,
        )

        self.attach_to_message(
            attachment=attachment,
            room=profile.room,
            message=message,
        )

        authenticate_client(
            self.client,
            GROUP_OWNER_USER_ID,
        )

        response = self.client.get(
            self.download_url(attachment.id),
            {
                "device_id": str(owner_device.id),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_deleted_attachment_cannot_be_downloaded(self):
        device = create_device(
            user_id=GROUP_OWNER_USER_ID,
        )
        attachment = create_completed_attachment(
            user_id=GROUP_OWNER_USER_ID,
            device=device,
        )
        attachment.upload_status = EncryptedAttachment.UploadStatus.DELETED
        attachment.deleted_at = timezone.now()
        attachment.save(
            update_fields=[
                "upload_status",
                "deleted_at",
            ]
        )

        authenticate_client(
            self.client,
            GROUP_OWNER_USER_ID,
        )

        response = self.client.get(
            self.download_url(attachment.id),
            {
                "device_id": str(device.id),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_expired_attachment_cannot_be_downloaded(self):
        device = create_device(
            user_id=GROUP_OWNER_USER_ID,
        )
        attachment = create_completed_attachment(
            user_id=GROUP_OWNER_USER_ID,
            device=device,
        )
        attachment.expires_at = timezone.now() - timedelta(seconds=1)
        attachment.save(
            update_fields=[
                "expires_at",
            ]
        )

        authenticate_client(
            self.client,
            GROUP_OWNER_USER_ID,
        )

        response = self.client.get(
            self.download_url(attachment.id),
            {
                "device_id": str(device.id),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

        attachment.refresh_from_db()

        self.assertEqual(
            attachment.upload_status,
            EncryptedAttachment.UploadStatus.EXPIRED,
        )
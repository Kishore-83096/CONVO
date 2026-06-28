from uuid import UUID

from .models import Message


EVENT_MESSAGE_TYPES = {
    Message.MessageType.EDIT,
    Message.MessageType.DELETE,
    Message.MessageType.REACTION,
    Message.MessageType.SYSTEM,
}

TARGET_REQUIRED_EVENT_TYPES = {
    Message.MessageType.EDIT,
    Message.MessageType.DELETE,
    Message.MessageType.REACTION,
}


class EncryptedMessageEventValidationError(Exception):
    """Raised when encrypted event-message metadata is invalid."""


def validate_encrypted_message_event(
    *,
    room,
    actor_user_id: str,
    message_type: str,
    encryption_metadata: dict,
) -> None:
    if message_type not in EVENT_MESSAGE_TYPES:
        return

    if not isinstance(encryption_metadata, dict):
        raise EncryptedMessageEventValidationError(
            "Event metadata must be a JSON object."
        )

    event_type = str(
        encryption_metadata.get("event_type", "")
    ).strip()

    if not event_type:
        raise EncryptedMessageEventValidationError(
            "Encrypted event messages require encryption_metadata.event_type."
        )

    target_message_id = encryption_metadata.get("target_message_id")

    if message_type in TARGET_REQUIRED_EVENT_TYPES:
        if not target_message_id:
            raise EncryptedMessageEventValidationError(
                "Encrypted edit/delete/reaction events require "
                "encryption_metadata.target_message_id."
            )

        try:
            target_uuid = UUID(str(target_message_id))
        except (TypeError, ValueError, AttributeError) as error:
            raise EncryptedMessageEventValidationError(
                "target_message_id must be a valid UUID."
            ) from error

        target_message = Message.objects.filter(
            id=target_uuid,
            room=room,
        ).first()

        if target_message is None:
            raise EncryptedMessageEventValidationError(
                "Event target message must exist in the same room."
            )

        if (
            message_type in {
                Message.MessageType.EDIT,
                Message.MessageType.DELETE,
            }
            and target_message.sender_user_id != actor_user_id
        ):
            raise EncryptedMessageEventValidationError(
                "Only the original sender can create encrypted edit/delete "
                "events for a message."
            )
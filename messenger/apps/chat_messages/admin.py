from django.contrib import admin

from .models import Message
from .models import Message, MessageKeyEnvelope
from .models import (
    DirectContactState,
    Message,
    MessageKeyEnvelope,
)
@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "room",
        "sender_user_id",
        "sender_device_id",
        "message_type",
        "encryption_version",
        "created_at",
    )

    list_filter = (
        "message_type",
        "encryption_version",
        "created_at",
    )

    search_fields = (
        "id",
        "room__id",
        "sender_user_id",
        "sender_device_id",
        "client_message_id",
    )

    readonly_fields = (
        "id",
        "created_at",
    )

    raw_id_fields = (
        "room",
        "reply_to",
    )

    fieldsets = (
        (
            "Message",
            {
                "fields": (
                    "id",
                    "room",
                    "sender_user_id",
                    "sender_device_id",
                    "client_message_id",
                    "message_type",
                    "reply_to",
                    "client_sent_at",
                    "created_at",
                ),
            },
        ),
        (
            "Encrypted content",
            {
                "fields": (
                    "encrypted_payload",
                    "encryption_metadata",
                    "encryption_version",
                ),
                "classes": (
                    "collapse",
                ),
            },
        ),
    )



@admin.register(MessageKeyEnvelope)
class MessageKeyEnvelopeAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "message",
        "recipient_user_id",
        "recipient_device",
        "protocol",
        "envelope_version",
        "created_at",
    )

    list_filter = (
        "protocol",
        "envelope_version",
        "created_at",
    )

    search_fields = (
        "id",
        "message__id",
        "recipient_user_id",
        "recipient_device__id",
        "session_reference",
    )

    readonly_fields = (
        "id",
        "created_at",
    )

    raw_id_fields = (
        "message",
        "recipient_device",
    )


@admin.register(DirectContactState)
class DirectContactStateAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "room",
        "owner_user_id",
        "contact_user_id",
        "identity_contact_id",
        "is_saved",
        "synced_at",
        "created_at",
    )

    list_filter = (
        "is_saved",
        "created_at",
        "updated_at",
        "synced_at",
    )

    search_fields = (
        "id",
        "room__id",
        "owner_user_id",
        "contact_user_id",
        "identity_contact_id",
    )

    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
        "synced_at",
    )

    raw_id_fields = (
        "room",
    )
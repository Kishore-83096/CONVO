from django.contrib import admin

from .models import Message
from .models import Message, MessageKeyEnvelope

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
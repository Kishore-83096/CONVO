from django.contrib import admin

from .models import Device, OneTimePreKey


class OneTimePreKeyInline(admin.TabularInline):
    model = OneTimePreKey
    extra = 0
    fields = (
        "key_id",
        "is_claimed",
        "claimed_at",
        "created_at",
    )
    readonly_fields = (
        "created_at",
    )


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user_id",
        "device_name",
        "platform",
        "registration_id",
        "key_bundle_version",
        "is_active",
        "created_at",
        "last_seen_at",
    )

    list_filter = (
        "platform",
        "is_active",
        "key_bundle_version",
        "created_at",
    )

    search_fields = (
        "id",
        "user_id",
        "device_name",
    )

    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
    )

    inlines = [
        OneTimePreKeyInline,
    ]


@admin.register(OneTimePreKey)
class OneTimePreKeyAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "device",
        "key_id",
        "is_claimed",
        "claimed_at",
        "created_at",
    )

    list_filter = (
        "is_claimed",
        "created_at",
    )

    search_fields = (
        "id",
        "device__id",
        "device__user_id",
    )

    readonly_fields = (
        "id",
        "created_at",
    )

    raw_id_fields = (
        "device",
    )
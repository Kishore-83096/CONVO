from django.contrib import admin

from .models import Room, RoomMember


class RoomMemberInline(admin.TabularInline):
    model = RoomMember
    extra = 0
    fields = (
        "user_id",
        "role",
        "is_active",
        "joined_at",
        "left_at",
    )
    readonly_fields = (
        "joined_at",
    )


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "room_type",
        "name",
        "created_by_user_id",
        "is_active",
        "created_at",
        "updated_at",
    )

    list_filter = (
        "room_type",
        "is_active",
        "created_at",
    )

    search_fields = (
        "id",
        "name",
        "created_by_user_id",
        "direct_pair_key",
    )

    readonly_fields = (
        "id",
        "direct_pair_key",
        "created_at",
        "updated_at",
    )

    inlines = [
        RoomMemberInline,
    ]


@admin.register(RoomMember)
class RoomMemberAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "room",
        "user_id",
        "role",
        "is_active",
        "joined_at",
        "left_at",
    )

    list_filter = (
        "role",
        "is_active",
        "joined_at",
    )

    search_fields = (
        "id",
        "room__id",
        "user_id",
        "added_by_user_id",
    )

    readonly_fields = (
        "id",
        "joined_at",
        "updated_at",
    )
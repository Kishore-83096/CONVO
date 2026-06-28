# Generated for Myna Messenger Phase 4 group audit events

import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("group_chat", "0001_group_profile"),
    ]

    operations = [
        migrations.CreateModel(
            name="GroupAuditEvent",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "actor_user_id",
                    models.CharField(
                        max_length=128,
                    ),
                ),
                (
                    "event_type",
                    models.CharField(
                        max_length=64,
                    ),
                ),
                (
                    "target_user_id",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=128,
                    ),
                ),
                (
                    "metadata",
                    models.JSONField(
                        blank=True,
                        default=dict,
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True,
                    ),
                ),
                (
                    "group_room",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="group_audit_events",
                        to="rooms.room",
                    ),
                ),
            ],
            options={
                "db_table": "messenger_group_audit_events",
                "ordering": ["-created_at", "-id"],
                "indexes": [
                    models.Index(
                        fields=["group_room", "-created_at"],
                        name="group_audit_room_time_idx",
                    ),
                    models.Index(
                        fields=["actor_user_id", "-created_at"],
                        name="group_audit_actor_time_idx",
                    ),
                    models.Index(
                        fields=["event_type", "-created_at"],
                        name="group_audit_type_time_idx",
                    ),
                ],
            },
        ),
    ]
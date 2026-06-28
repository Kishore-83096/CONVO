# Generated for Myna Messenger Phase 10 group security transitions

import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("e2ee_devices", "0002_recoverybundle"),
        ("group_chat", "0006_group_sender_key_distribution"),
    ]

    operations = [
        migrations.CreateModel(
            name="GroupSecurityTransition",
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
                    "reason",
                    models.CharField(
                        max_length=64,
                    ),
                ),
                (
                    "actor_user_id",
                    models.CharField(
                        max_length=128,
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
                    "status",
                    models.CharField(
                        default="pending",
                        max_length=16,
                    ),
                ),
                (
                    "attempt_count",
                    models.PositiveSmallIntegerField(
                        default=0,
                    ),
                ),
                (
                    "last_error_code",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=120,
                    ),
                ),
                (
                    "old_epoch_number",
                    models.PositiveIntegerField(
                        blank=True,
                        null=True,
                    ),
                ),
                (
                    "new_epoch_number",
                    models.PositiveIntegerField(
                        blank=True,
                        null=True,
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True,
                    ),
                ),
                (
                    "applied_at",
                    models.DateTimeField(
                        blank=True,
                        null=True,
                    ),
                ),
                (
                    "group_room",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="group_security_transitions",
                        to="rooms.room",
                    ),
                ),
                (
                    "target_device",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="group_security_transitions",
                        to="e2ee_devices.device",
                    ),
                ),
            ],
            options={
                "db_table": "messenger_group_security_transitions",
                "ordering": ["-created_at", "-id"],
                "indexes": [
                    models.Index(
                        fields=[
                            "group_room",
                            "status",
                            "-created_at",
                        ],
                        name="gst_room_status_idx",
                    ),
                    models.Index(
                        fields=[
                            "target_user_id",
                            "status",
                            "-created_at",
                        ],
                        name="gst_target_status_idx",
                    ),
                    models.Index(
                        fields=[
                            "target_device",
                            "status",
                            "-created_at",
                        ],
                        name="gst_device_status_idx",
                    ),
                ],
            },
        ),
    ]
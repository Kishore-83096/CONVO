# Generated for Myna Messenger Phase 7 sender-key distribution

import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("e2ee_devices", "0002_recoverybundle"),
        ("group_chat", "0004_group_sender_key"),
    ]

    operations = [
        migrations.CreateModel(
            name="GroupSenderKeyDistribution",
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
                    "recipient_user_id",
                    models.CharField(
                        max_length=128,
                    ),
                ),
                (
                    "encrypted_sender_key",
                    models.TextField(),
                ),
                (
                    "distribution_metadata",
                    models.JSONField(
                        default=dict,
                    ),
                ),
                (
                    "distribution_version",
                    models.PositiveSmallIntegerField(
                        default=1,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("stored", "Stored"),
                            ("acknowledged", "Acknowledged"),
                        ],
                        default="stored",
                        max_length=16,
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True,
                    ),
                ),
                (
                    "acknowledged_at",
                    models.DateTimeField(
                        blank=True,
                        null=True,
                    ),
                ),
                (
                    "recipient_device",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="group_sender_key_distributions",
                        to="e2ee_devices.device",
                    ),
                ),
                (
                    "sender_key",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="distributions",
                        to="group_chat.groupsenderkey",
                    ),
                ),
            ],
            options={
                "db_table": "messenger_group_sender_key_distributions",
                "ordering": ["-created_at", "-id"],
                "indexes": [
                    models.Index(
                        fields=[
                            "recipient_device",
                            "status",
                            "-created_at",
                        ],
                        name="group_sender_dist_device_idx",
                    ),
                    models.Index(
                        fields=[
                            "recipient_user_id",
                            "status",
                            "-created_at",
                        ],
                        name="group_sender_dist_user_idx",
                    ),
                    models.Index(
                        fields=[
                            "sender_key",
                            "status",
                        ],
                        name="group_sender_dist_key_status_idx",
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=[
                            "sender_key",
                            "recipient_device",
                        ],
                        name="unique_sender_key_recipient_device",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            ("distribution_version__gte", 1)
                        ),
                        name="group_sender_distribution_version_gte_1",
                    ),
                ],
            },
        ),
    ]
# Generated for Myna Messenger Phase 6 sender-key registration

import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("e2ee_devices", "0002_recoverybundle"),
        ("group_chat", "0003_group_encryption_epoch"),
    ]

    operations = [
        migrations.CreateModel(
            name="GroupSenderKey",
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
                    "sender_user_id",
                    models.CharField(
                        max_length=128,
                    ),
                ),
                (
                    "sender_key_id",
                    models.UUIDField(
                        unique=True,
                    ),
                ),
                (
                    "signing_public_key",
                    models.TextField(),
                ),
                (
                    "key_algorithm",
                    models.CharField(
                        default="group-sender-key-v1",
                        max_length=50,
                    ),
                ),
                (
                    "signing_algorithm",
                    models.CharField(
                        default="ed25519",
                        max_length=50,
                    ),
                ),
                (
                    "key_version",
                    models.PositiveSmallIntegerField(
                        default=1,
                    ),
                ),
                (
                    "highest_accepted_iteration",
                    models.PositiveIntegerField(
                        default=0,
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(
                        default=True,
                    ),
                ),
                (
                    "active_sender_device_epoch_key",
                    models.CharField(
                        blank=True,
                        editable=False,
                        max_length=128,
                        null=True,
                        unique=True,
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True,
                    ),
                ),
                (
                    "revoked_at",
                    models.DateTimeField(
                        blank=True,
                        null=True,
                    ),
                ),
                (
                    "epoch",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sender_keys",
                        to="group_chat.groupencryptionepoch",
                    ),
                ),
                (
                    "group_room",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="group_sender_keys",
                        to="rooms.room",
                    ),
                ),
                (
                    "sender_device",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="group_sender_keys",
                        to="e2ee_devices.device",
                    ),
                ),
            ],
            options={
                "db_table": "messenger_group_sender_keys",
                "ordering": ["-created_at", "-id"],
                "indexes": [
                    models.Index(
                        fields=[
                            "group_room",
                            "sender_user_id",
                            "is_active",
                        ],
                        name="group_sender_user_active_idx",
                    ),
                    models.Index(
                        fields=[
                            "epoch",
                            "sender_device",
                            "is_active",
                        ],
                        name="group_sender_epoch_device_idx",
                    ),
                    models.Index(
                        fields=[
                            "sender_device",
                            "-created_at",
                        ],
                        name="group_sender_device_time_idx",
                    ),
                ],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(("key_version__gte", 1)),
                        name="group_sender_key_version_gte_1",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            ("highest_accepted_iteration__gte", 0)
                        ),
                        name="group_sender_key_iteration_gte_0",
                    ),
                ],
            },
        ),
    ]
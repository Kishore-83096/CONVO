# Generated for Myna Messenger Phase 8 group encrypted messages

import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chat_messages", "0003_messagerecoveryenvelope"),
        ("group_chat", "0005_group_sender_key_distribution"),
        ("rooms", "0002_roommember_group_lifecycle"),
    ]

    operations = [
        migrations.CreateModel(
            name="GroupMessageEncryption",
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
                    "chain_iteration",
                    models.PositiveIntegerField(),
                ),
                (
                    "signature",
                    models.TextField(),
                ),
                (
                    "encryption_metadata",
                    models.JSONField(
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
                    "epoch",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="group_message_encryptions",
                        to="group_chat.groupencryptionepoch",
                    ),
                ),
                (
                    "group_room",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="group_message_encryptions",
                        to="rooms.room",
                    ),
                ),
                (
                    "message",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="group_encryption",
                        to="chat_messages.message",
                    ),
                ),
                (
                    "sender_key",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="group_message_encryptions",
                        to="group_chat.groupsenderkey",
                    ),
                ),
            ],
            options={
                "db_table": "messenger_group_message_encryptions",
                "ordering": ["-created_at", "-id"],
                "indexes": [
                    models.Index(
                        fields=[
                            "group_room",
                            "epoch",
                            "-created_at",
                        ],
                        name="gmenc_room_epoch_idx",
                    ),
                    models.Index(
                        fields=[
                            "sender_key",
                            "chain_iteration",
                        ],
                        name="gmenc_sender_iter_idx",
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=[
                            "sender_key",
                            "chain_iteration",
                        ],
                        name="uniq_group_sender_iter",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("chain_iteration__gte", 0)),
                        name="group_msg_iter_gte_0",
                    ),
                ],
            },
        ),
    ]
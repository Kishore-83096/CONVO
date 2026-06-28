import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chat_messages", "0006_contact_delivery_policy"),
    ]

    operations = [
        migrations.AddField(
            model_name="contactdeliverypolicy",
            name="ghost_until",
            field=models.DateTimeField(
                blank=True,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="contactdeliverypolicy",
            name="ghost_permanent",
            field=models.BooleanField(
                default=False,
            ),
        ),
        migrations.AddField(
            model_name="contactdeliverypolicy",
            name="ghost_duration_option",
            field=models.CharField(
                blank=True,
                default="",
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name="DirectMessageReceiptDecision",
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
                    models.CharField(max_length=128),
                ),
                (
                    "recipient_user_id",
                    models.CharField(max_length=128),
                ),
                (
                    "suppress_delivered_receipt",
                    models.BooleanField(default=False),
                ),
                (
                    "suppress_read_receipt",
                    models.BooleanField(default=False),
                ),
                (
                    "policy_reason",
                    models.CharField(
                        choices=[
                            ("normal", "Normal"),
                            ("blocked", "Blocked"),
                            ("ghost", "Ghost"),
                        ],
                        default="normal",
                        max_length=20,
                    ),
                ),
                (
                    "policy_version",
                    models.PositiveIntegerField(
                        blank=True,
                        null=True,
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "message",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="receipt_decision",
                        to="chat_messages.message",
                    ),
                ),
            ],
            options={
                "db_table": "messenger_direct_message_receipt_decisions",
            },
        ),
        migrations.AddIndex(
            model_name="directmessagereceiptdecision",
            index=models.Index(
                fields=[
                    "message",
                    "recipient_user_id",
                ],
                name="dm_rec_dec_msg_user_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="directmessagereceiptdecision",
            index=models.Index(
                fields=[
                    "recipient_user_id",
                    "sender_user_id",
                    "policy_reason",
                ],
                name="dm_receipt_decision_pair_idx",
            ),
        ),
    ]
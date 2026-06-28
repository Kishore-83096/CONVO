import uuid

from django.db import migrations, models
from django.db.models import F, Q


class Migration(migrations.Migration):

    dependencies = [
        ("chat_messages", "0005_message_receipt_encrypted_attachment"),
    ]

    operations = [
        migrations.CreateModel(
            name="ContactDeliveryPolicy",
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
                    "owner_user_id",
                    models.CharField(max_length=128),
                ),
                (
                    "target_user_id",
                    models.CharField(max_length=128),
                ),
                (
                    "is_blocked",
                    models.BooleanField(default=False),
                ),
                (
                    "policy_version",
                    models.PositiveIntegerField(default=1),
                ),
                (
                    "source_updated_at",
                    models.DateTimeField(blank=True, null=True),
                ),
                (
                    "synced_at",
                    models.DateTimeField(auto_now=True),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True),
                ),
            ],
            options={
                "db_table": "messenger_contact_delivery_policies",
            },
        ),
        migrations.AddConstraint(
            model_name="contactdeliverypolicy",
            constraint=models.UniqueConstraint(
                fields=("owner_user_id", "target_user_id"),
                name="uniq_contact_policy_owner_target",
            ),
        ),
        migrations.AddConstraint(
            model_name="contactdeliverypolicy",
            constraint=models.CheckConstraint(
                condition=~Q(owner_user_id=F("target_user_id")),
                name="ck_contact_policy_not_self",
            ),
        ),
        migrations.AddIndex(
            model_name="contactdeliverypolicy",
            index=models.Index(
                fields=[
                    "owner_user_id",
                    "target_user_id",
                    "is_blocked",
                ],
                name="contact_policy_lookup_idx",
            ),
        ),
    ]
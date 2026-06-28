# Generated for Myna Phase 12 backend.

import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("e2ee_devices", "0002_recoverybundle"),
        ("chat_messages", "0004_group_message_encryption"),
    ]

    operations = [
        migrations.AlterField(
            model_name="message",
            name="message_type",
            field=models.CharField(
                choices=[
                    ("text", "Text"),
                    ("image", "Image"),
                    ("video", "Video"),
                    ("audio", "Audio"),
                    ("file", "File"),
                    ("location", "Location"),
                    ("contact", "Contact"),
                    ("edit", "Edit"),
                    ("delete", "Delete"),
                    ("reaction", "Reaction"),
                    ("system", "System"),
                ],
                default="text",
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name="EncryptedAttachment",
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
                ("uploader_user_id", models.CharField(max_length=128)),
                (
                    "storage_provider",
                    models.CharField(
                        choices=[
                            ("cloudinary", "Cloudinary"),
                            ("s3", "S3"),
                            ("local", "Local"),
                        ],
                        default="cloudinary",
                        max_length=40,
                    ),
                ),
                (
                    "storage_key",
                    models.CharField(
                        max_length=512,
                        unique=True,
                    ),
                ),
                (
                    "ciphertext_sha256",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=64,
                    ),
                ),
                (
                    "ciphertext_size",
                    models.PositiveBigIntegerField(default=0),
                ),
                (
                    "media_category",
                    models.CharField(
                        choices=[
                            ("image", "Image"),
                            ("video", "Video"),
                            ("audio", "Audio"),
                            ("file", "File"),
                        ],
                        default="file",
                        max_length=20,
                    ),
                ),
                (
                    "upload_status",
                    models.CharField(
                        choices=[
                            ("initiated", "Initiated"),
                            ("completed", "Completed"),
                            ("deleted", "Deleted"),
                            ("expired", "Expired"),
                        ],
                        default="initiated",
                        max_length=20,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "completed_at",
                    models.DateTimeField(
                        blank=True,
                        null=True,
                    ),
                ),
                (
                    "expires_at",
                    models.DateTimeField(
                        blank=True,
                        null=True,
                    ),
                ),
                (
                    "uploader_device",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="encrypted_attachments",
                        to="e2ee_devices.device",
                    ),
                ),
            ],
            options={
                "db_table": "messenger_encrypted_attachments",
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.CreateModel(
            name="MessageReceipt",
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
                ("recipient_user_id", models.CharField(max_length=128)),
                (
                    "delivered_at",
                    models.DateTimeField(
                        blank=True,
                        null=True,
                    ),
                ),
                (
                    "read_at",
                    models.DateTimeField(
                        blank=True,
                        null=True,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "message",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="receipts",
                        to="chat_messages.message",
                    ),
                ),
                (
                    "recipient_device",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="message_receipts",
                        to="e2ee_devices.device",
                    ),
                ),
            ],
            options={
                "db_table": "messenger_message_receipts",
                "ordering": [
                    "message",
                    "recipient_user_id",
                    "recipient_device",
                ],
            },
        ),
        migrations.AddConstraint(
            model_name="encryptedattachment",
            constraint=models.CheckConstraint(
                condition=models.Q(("ciphertext_size__gte", 0)),
                name="attachment_ciphertext_size_gte_0",
            ),
        ),
        migrations.AddIndex(
            model_name="encryptedattachment",
            index=models.Index(
                fields=[
                    "uploader_user_id",
                    "-created_at",
                ],
                name="attach_uploader_time_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="encryptedattachment",
            index=models.Index(
                fields=[
                    "uploader_device",
                    "-created_at",
                ],
                name="attach_device_time_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="encryptedattachment",
            index=models.Index(
                fields=[
                    "upload_status",
                    "-created_at",
                ],
                name="attach_status_time_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="messagereceipt",
            constraint=models.UniqueConstraint(
                fields=[
                    "message",
                    "recipient_user_id",
                    "recipient_device",
                ],
                name="uniq_msg_receipt_device",
            ),
        ),
        migrations.AddIndex(
            model_name="messagereceipt",
            index=models.Index(
                fields=[
                    "message",
                    "recipient_user_id",
                ],
                name="receipt_msg_user_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="messagereceipt",
            index=models.Index(
                fields=[
                    "recipient_user_id",
                    "updated_at",
                ],
                name="receipt_user_updated_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="messagereceipt",
            index=models.Index(
                fields=[
                    "recipient_device",
                    "updated_at",
                ],
                name="receipt_device_updated_idx",
            ),
        ),
    ]
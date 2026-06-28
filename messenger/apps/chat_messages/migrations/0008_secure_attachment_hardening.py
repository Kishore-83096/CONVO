# Generated for secure Cloudinary attachment hardening.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chat_messages", "0007_contact_policy_ghost_and_receipt_decision"),
        ("e2ee_devices", "0002_recoverybundle"),
        ("rooms", "0002_roommember_group_lifecycle"),
    ]

    operations = [
        migrations.AddField(
            model_name="encryptedattachment",
            name="attached_at",
            field=models.DateTimeField(
                blank=True,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="encryptedattachment",
            name="attached_message",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="encrypted_attachments",
                to="chat_messages.message",
            ),
        ),
        migrations.AddField(
            model_name="encryptedattachment",
            name="attached_room",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="encrypted_attachments",
                to="rooms.room",
            ),
        ),
        migrations.AddField(
            model_name="encryptedattachment",
            name="ciphertext_size_hint",
            field=models.PositiveBigIntegerField(
                default=0,
            ),
        ),
        migrations.AddField(
            model_name="encryptedattachment",
            name="cloudinary_asset_id",
            field=models.CharField(
                blank=True,
                default="",
                max_length=128,
            ),
        ),
        migrations.AddField(
            model_name="encryptedattachment",
            name="cloudinary_version",
            field=models.CharField(
                blank=True,
                default="",
                max_length=64,
            ),
        ),
        migrations.AddField(
            model_name="encryptedattachment",
            name="deleted_at",
            field=models.DateTimeField(
                blank=True,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="encryptedattachment",
            name="last_cloudinary_error",
            field=models.TextField(
                blank=True,
                default="",
            ),
        ),
        migrations.AddField(
            model_name="encryptedattachment",
            name="resource_type",
            field=models.CharField(
                default="raw",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="encryptedattachment",
            name="upload_completed_verified_at",
            field=models.DateTimeField(
                blank=True,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="encryptedattachment",
            name="upload_signature_expires_at",
            field=models.DateTimeField(
                blank=True,
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="encryptedattachment",
            name="upload_status",
            field=models.CharField(
                choices=[
                    ("initiated", "Initiated"),
                    ("completed", "Completed"),
                    ("attached", "Attached"),
                    ("deleted", "Deleted"),
                    ("expired", "Expired"),
                ],
                default="initiated",
                max_length=20,
            ),
        ),
        migrations.AddIndex(
            model_name="encryptedattachment",
            index=models.Index(
                fields=[
                    "uploader_user_id",
                    "upload_status",
                    "created_at",
                ],
                name="attach_user_status_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="encryptedattachment",
            index=models.Index(
                fields=[
                    "upload_status",
                    "upload_signature_expires_at",
                ],
                name="attach_status_exp_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="encryptedattachment",
            index=models.Index(
                fields=[
                    "attached_room",
                    "attached_message",
                ],
                name="attach_room_msg_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="encryptedattachment",
            index=models.Index(
                fields=[
                    "storage_provider",
                    "storage_key",
                ],
                name="attach_provider_key_idx",
            ),
        ),
    ]
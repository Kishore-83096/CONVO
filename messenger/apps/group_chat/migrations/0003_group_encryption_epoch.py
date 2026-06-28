# Generated for Myna Messenger Phase 5 group encryption epochs

import hashlib
import json
import uuid

import django.db.models.deletion
from django.db import migrations, models


def _membership_snapshot_hash(member_rows):
    canonical = [
        {
            "user_id": str(user_id),
            "membership_version": int(membership_version or 1),
        }
        for user_id, membership_version in member_rows
    ]
    canonical.sort(key=lambda item: item["user_id"])

    payload = json.dumps(
        canonical,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")

    return hashlib.sha256(payload).hexdigest()


def create_initial_epochs(apps, schema_editor):
    GroupProfile = apps.get_model("group_chat", "GroupProfile")
    GroupEncryptionEpoch = apps.get_model(
        "group_chat",
        "GroupEncryptionEpoch",
    )
    RoomMember = apps.get_model("rooms", "RoomMember")

    profiles = GroupProfile.objects.filter(
        room__room_type="group",
        room__is_active=True,
    )

    for profile in profiles.iterator():
        has_epoch = GroupEncryptionEpoch.objects.filter(
            group_room_id=profile.room_id,
        ).exists()

        if has_epoch:
            continue

        member_rows = list(
            RoomMember.objects.filter(
                room_id=profile.room_id,
                is_active=True,
            )
            .order_by("user_id")
            .values_list("user_id", "membership_version")
        )

        GroupEncryptionEpoch.objects.create(
            group_room_id=profile.room_id,
            epoch_number=1,
            status="active",
            rotation_reason="initial",
            created_by_user_id=profile.created_by_user_id,
            membership_snapshot_hash=_membership_snapshot_hash(member_rows),
            active_epoch_key=str(profile.room_id),
        )


def noop_reverse(apps, schema_editor):
    # Do not delete epoch history on reverse migration automatically.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("group_chat", "0002_group_audit_event"),
        ("rooms", "0002_roommember_group_lifecycle"),
    ]

    operations = [
        migrations.CreateModel(
            name="GroupEncryptionEpoch",
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
                    "epoch_number",
                    models.PositiveIntegerField(),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("active", "Active"),
                            ("closed", "Closed"),
                        ],
                        default="active",
                        max_length=16,
                    ),
                ),
                (
                    "rotation_reason",
                    models.CharField(
                        max_length=64,
                    ),
                ),
                (
                    "created_by_user_id",
                    models.CharField(
                        max_length=128,
                    ),
                ),
                (
                    "membership_snapshot_hash",
                    models.CharField(
                        max_length=64,
                    ),
                ),
                (
                    "active_epoch_key",
                    models.CharField(
                        blank=True,
                        editable=False,
                        max_length=64,
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
                    "closed_at",
                    models.DateTimeField(
                        blank=True,
                        null=True,
                    ),
                ),
                (
                    "group_room",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="group_encryption_epochs",
                        to="rooms.room",
                    ),
                ),
            ],
            options={
                "db_table": "messenger_group_encryption_epochs",
                "ordering": ["-epoch_number", "-created_at"],
                "indexes": [
                    models.Index(
                        fields=[
                            "group_room",
                            "status",
                            "-epoch_number",
                        ],
                        name="group_epoch_room_status_idx",
                    ),
                    models.Index(
                        fields=[
                            "created_by_user_id",
                            "-created_at",
                        ],
                        name="group_epoch_creator_idx",
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=[
                            "group_room",
                            "epoch_number",
                        ],
                        name="unique_group_epoch_number",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("epoch_number__gte", 1)),
                        name="group_epoch_number_gte_1",
                    ),
                ],
            },
        ),
        migrations.RunPython(
            create_initial_epochs,
            noop_reverse,
        ),
    ]
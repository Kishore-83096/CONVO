import uuid

from django.core.exceptions import ValidationError
from django.db import models

from apps.e2ee_devices.models import Device
from apps.rooms.models import EXTERNAL_USER_ID_MAX_LENGTH, Room

from .constants import (
    GROUP_SECURITY_TRANSITION_REASONS,
    GROUP_SECURITY_TRANSITION_STATUSES,
    GROUP_SECURITY_TRANSITION_STATUS_APPLIED,
    GROUP_SECURITY_TRANSITION_STATUS_FAILED,
    GROUP_SECURITY_TRANSITION_STATUS_PENDING,
    DEFAULT_GROUP_MEMBER_LIMIT,
    EPOCH_ROTATION_REASONS,
    GROUP_AUDIT_EVENT_TYPES,
    GROUP_SENDER_KEY_ALGORITHM,
    GROUP_SENDER_KEY_DISTRIBUTION_STATUSES,
    GROUP_SENDER_KEY_DISTRIBUTION_STATUS_ACKNOWLEDGED,
    GROUP_SENDER_KEY_DISTRIBUTION_STATUS_STORED,
    GROUP_SENDER_KEY_SIGNING_ALGORITHM,
    MAX_GROUP_MEMBER_LIMIT,
    ROOM_TYPE_GROUP,
)


class GroupProfile(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    room = models.OneToOneField(
        Room,
        on_delete=models.CASCADE,
        related_name="group_profile",
    )

    description = models.TextField(
        blank=True,
        default="",
    )

    avatar_storage_key = models.CharField(
        max_length=512,
        blank=True,
        default="",
    )

    created_by_user_id = models.CharField(
        max_length=EXTERNAL_USER_ID_MAX_LENGTH,
    )

    max_members = models.PositiveSmallIntegerField(
        default=DEFAULT_GROUP_MEMBER_LIMIT,
    )

    join_history_visible = models.BooleanField(
        default=False,
    )

    only_admins_can_send = models.BooleanField(
        default=False,
    )

    only_admins_can_edit_info = models.BooleanField(
        default=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        db_table = "messenger_group_profiles"
        ordering = [
            "-updated_at",
        ]
        indexes = [
            models.Index(
                fields=[
                    "created_by_user_id",
                    "-created_at",
                ],
                name="group_profile_creator_idx",
            ),
        ]

    def __str__(self) -> str:
        return self.room.name or f"Group {self.room_id}"

    def clean(self) -> None:
        super().clean()

        self.description = self.description.strip()
        self.avatar_storage_key = self.avatar_storage_key.strip()
        self.created_by_user_id = self.created_by_user_id.strip()

        errors = {}

        if not self.created_by_user_id:
            errors["created_by_user_id"] = (
                "The group creator user ID is required."
            )

        if self.max_members < 2:
            errors["max_members"] = (
                "A group must allow at least 2 members including the owner."
            )

        if self.max_members > MAX_GROUP_MEMBER_LIMIT:
            errors["max_members"] = (
                f"A group cannot allow more than {MAX_GROUP_MEMBER_LIMIT} "
                "members."
            )

        if self.room_id and self.room.room_type != ROOM_TYPE_GROUP:
            errors["room"] = (
                "GroupProfile can only be attached to a group room."
            )

        if errors:
            raise ValidationError(errors)


class GroupAuditEvent(models.Model):
    """Audit trail for group security and membership mutations.

    Never store plaintext messages, encrypted payloads, private keys,
    sender-key secrets, ratchet state, recovery secrets or message keys here.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    group_room = models.ForeignKey(
        Room,
        on_delete=models.CASCADE,
        related_name="group_audit_events",
    )

    actor_user_id = models.CharField(
        max_length=EXTERNAL_USER_ID_MAX_LENGTH,
    )

    event_type = models.CharField(
        max_length=64,
    )

    target_user_id = models.CharField(
        max_length=EXTERNAL_USER_ID_MAX_LENGTH,
        blank=True,
        default="",
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        db_table = "messenger_group_audit_events"
        ordering = [
            "-created_at",
            "-id",
        ]
        indexes = [
            models.Index(
                fields=[
                    "group_room",
                    "-created_at",
                ],
                name="group_audit_room_time_idx",
            ),
            models.Index(
                fields=[
                    "actor_user_id",
                    "-created_at",
                ],
                name="group_audit_actor_time_idx",
            ),
            models.Index(
                fields=[
                    "event_type",
                    "-created_at",
                ],
                name="group_audit_type_time_idx",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"{self.event_type} by {self.actor_user_id} "
            f"in {self.group_room_id}"
        )

    def clean(self) -> None:
        super().clean()

        self.actor_user_id = self.actor_user_id.strip()
        self.target_user_id = self.target_user_id.strip()
        self.event_type = self.event_type.strip()

        errors = {}

        if not self.actor_user_id:
            errors["actor_user_id"] = "Actor user ID is required."

        if self.event_type not in GROUP_AUDIT_EVENT_TYPES:
            errors["event_type"] = "Invalid group audit event type."

        if self.group_room_id and self.group_room.room_type != ROOM_TYPE_GROUP:
            errors["group_room"] = (
                "Group audit events can only be attached to group rooms."
            )

        if not isinstance(self.metadata, dict):
            errors["metadata"] = "Audit metadata must be a JSON object."

        forbidden_words = (
            "plaintext",
            "private_key",
            "secret",
            "message_key",
            "ratchet",
            "sender_chain",
            "recovery_key",
        )

        for key in self.metadata.keys():
            normalized_key = str(key).lower()
            if any(word in normalized_key for word in forbidden_words):
                errors["metadata"] = (
                    "Audit metadata must not contain plaintext or secret "
                    "cryptographic material."
                )
                break

        if errors:
            raise ValidationError(errors)


class GroupEncryptionEpoch(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        CLOSED = "closed", "Closed"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    group_room = models.ForeignKey(
        Room,
        on_delete=models.CASCADE,
        related_name="group_encryption_epochs",
    )

    epoch_number = models.PositiveIntegerField()

    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.ACTIVE,
    )

    rotation_reason = models.CharField(
        max_length=64,
    )

    created_by_user_id = models.CharField(
        max_length=EXTERNAL_USER_ID_MAX_LENGTH,
    )

    membership_snapshot_hash = models.CharField(
        max_length=64,
    )

    active_epoch_key = models.CharField(
        max_length=64,
        unique=True,
        null=True,
        blank=True,
        editable=False,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    closed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "messenger_group_encryption_epochs"
        ordering = [
            "-epoch_number",
            "-created_at",
        ]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "group_room",
                    "epoch_number",
                ],
                name="unique_group_epoch_number",
            ),
            models.CheckConstraint(
                check=models.Q(epoch_number__gte=1),
                name="group_epoch_number_gte_1",
            ),
        ]
        indexes = [
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
        ]

    def __str__(self) -> str:
        return (
            f"Group {self.group_room_id} epoch {self.epoch_number} "
            f"({self.status})"
        )

    def clean(self) -> None:
        super().clean()

        self.created_by_user_id = self.created_by_user_id.strip()
        self.rotation_reason = self.rotation_reason.strip()
        self.membership_snapshot_hash = self.membership_snapshot_hash.strip()

        errors = {}

        if self.group_room_id and self.group_room.room_type != ROOM_TYPE_GROUP:
            errors["group_room"] = (
                "Group encryption epochs cannot be created for direct rooms."
            )

        if self.epoch_number < 1:
            errors["epoch_number"] = "Epoch number must be at least 1."

        if self.status not in {
            self.Status.ACTIVE,
            self.Status.CLOSED,
        }:
            errors["status"] = "Invalid epoch status."

        if self.rotation_reason not in EPOCH_ROTATION_REASONS:
            errors["rotation_reason"] = "Invalid epoch rotation reason."

        if not self.created_by_user_id:
            errors["created_by_user_id"] = (
                "Epoch creator user ID is required."
            )

        if len(self.membership_snapshot_hash) != 64:
            errors["membership_snapshot_hash"] = (
                "Membership snapshot hash must be a SHA-256 hex digest."
            )

        if self.status == self.Status.ACTIVE and self.closed_at is not None:
            errors["closed_at"] = "An active epoch cannot have closed_at."

        if self.status == self.Status.CLOSED and self.closed_at is None:
            errors["closed_at"] = "A closed epoch must have closed_at."

        if self.pk:
            existing = (
                GroupEncryptionEpoch.objects.filter(pk=self.pk)
                .only("status")
                .first()
            )
            if (
                existing is not None
                and existing.status == self.Status.CLOSED
                and self.status == self.Status.ACTIVE
            ):
                errors["status"] = "A closed epoch cannot be reactivated."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.status == self.Status.ACTIVE and self.group_room_id:
            self.active_epoch_key = str(self.group_room_id)
        else:
            self.active_epoch_key = None

        super().save(*args, **kwargs)


class GroupSenderKey(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    group_room = models.ForeignKey(
        Room,
        on_delete=models.CASCADE,
        related_name="group_sender_keys",
    )

    epoch = models.ForeignKey(
        GroupEncryptionEpoch,
        on_delete=models.CASCADE,
        related_name="sender_keys",
    )

    sender_user_id = models.CharField(
        max_length=EXTERNAL_USER_ID_MAX_LENGTH,
    )

    sender_device = models.ForeignKey(
        Device,
        on_delete=models.CASCADE,
        related_name="group_sender_keys",
    )

    sender_key_id = models.UUIDField(
        unique=True,
    )

    signing_public_key = models.TextField()

    key_algorithm = models.CharField(
        max_length=50,
        default=GROUP_SENDER_KEY_ALGORITHM,
    )

    signing_algorithm = models.CharField(
        max_length=50,
        default=GROUP_SENDER_KEY_SIGNING_ALGORITHM,
    )

    key_version = models.PositiveSmallIntegerField(
        default=1,
    )

    highest_accepted_iteration = models.PositiveIntegerField(
        default=0,
    )

    is_active = models.BooleanField(
        default=True,
    )

    active_sender_device_epoch_key = models.CharField(
        max_length=128,
        unique=True,
        null=True,
        blank=True,
        editable=False,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    revoked_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "messenger_group_sender_keys"
        ordering = [
            "-created_at",
            "-id",
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(key_version__gte=1),
                name="group_sender_key_version_gte_1",
            ),
            models.CheckConstraint(
                check=models.Q(highest_accepted_iteration__gte=0),
                name="group_sender_key_iteration_gte_0",
            ),
        ]
        indexes = [
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
        ]

    def __str__(self) -> str:
        return (
            f"Sender key {self.sender_key_id} for "
            f"{self.sender_user_id}/{self.sender_device_id}"
        )

    def clean(self) -> None:
        super().clean()

        self.sender_user_id = self.sender_user_id.strip()
        self.signing_public_key = self.signing_public_key.strip()
        self.key_algorithm = self.key_algorithm.strip().lower()
        self.signing_algorithm = self.signing_algorithm.strip().lower()

        errors = {}

        if self.group_room_id and self.group_room.room_type != ROOM_TYPE_GROUP:
            errors["group_room"] = (
                "Sender keys can only be registered for group rooms."
            )

        if self.epoch_id and self.group_room_id:
            if self.epoch.group_room_id != self.group_room_id:
                errors["epoch"] = "Epoch does not belong to this group."

        if self.epoch_id and self.is_active:
            if self.epoch.status != GroupEncryptionEpoch.Status.ACTIVE:
                errors["epoch"] = (
                    "Active sender keys can only target the active epoch."
                )

        if self.sender_device_id:
            if self.sender_device.user_id != self.sender_user_id:
                errors["sender_device"] = (
                    "Sender device does not belong to sender user."
                )

            if self.is_active and not self.sender_device.is_active:
                errors["sender_device"] = (
                    "Sender device must be active."
                )

        if not self.sender_user_id:
            errors["sender_user_id"] = "Sender user ID is required."

        if not self.signing_public_key:
            errors["signing_public_key"] = (
                "Signing public key is required."
            )

        if self.key_algorithm != GROUP_SENDER_KEY_ALGORITHM:
            errors["key_algorithm"] = (
                f"key_algorithm must be {GROUP_SENDER_KEY_ALGORITHM}."
            )

        if self.signing_algorithm != GROUP_SENDER_KEY_SIGNING_ALGORITHM:
            errors["signing_algorithm"] = (
                "signing_algorithm must be "
                f"{GROUP_SENDER_KEY_SIGNING_ALGORITHM}."
            )

        if self.key_version < 1:
            errors["key_version"] = (
                "Sender-key version must be at least 1."
            )

        if self.is_active and self.revoked_at is not None:
            errors["revoked_at"] = (
                "An active sender key cannot have revoked_at."
            )

        if not self.is_active and self.revoked_at is None:
            errors["revoked_at"] = (
                "A revoked sender key must have revoked_at."
            )

        if self.pk:
            existing = (
                GroupSenderKey.objects.filter(pk=self.pk)
                .only("is_active")
                .first()
            )

            if (
                existing is not None
                and not existing.is_active
                and self.is_active
            ):
                errors["is_active"] = (
                    "A revoked sender key cannot be reactivated."
                )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.is_active and self.epoch_id and self.sender_device_id:
            self.active_sender_device_epoch_key = (
                f"{self.epoch_id}:{self.sender_device_id}"
            )
        else:
            self.active_sender_device_epoch_key = None

        super().save(*args, **kwargs)


class GroupSenderKeyDistribution(models.Model):
    """Encrypted delivery of one group sender key to one recipient device.

    encrypted_sender_key must already be encrypted by the client through the
    recipient device's pairwise E2EE session. The server stores opaque
    ciphertext only.
    """

    class Status(models.TextChoices):
        STORED = (
            GROUP_SENDER_KEY_DISTRIBUTION_STATUS_STORED,
            "Stored",
        )
        ACKNOWLEDGED = (
            GROUP_SENDER_KEY_DISTRIBUTION_STATUS_ACKNOWLEDGED,
            "Acknowledged",
        )

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    sender_key = models.ForeignKey(
        GroupSenderKey,
        on_delete=models.CASCADE,
        related_name="distributions",
    )

    recipient_user_id = models.CharField(
        max_length=EXTERNAL_USER_ID_MAX_LENGTH,
    )

    recipient_device = models.ForeignKey(
        Device,
        on_delete=models.CASCADE,
        related_name="group_sender_key_distributions",
    )

    encrypted_sender_key = models.TextField()

    distribution_metadata = models.JSONField(
        default=dict,
    )

    distribution_version = models.PositiveSmallIntegerField(
        default=1,
    )

    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.STORED,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    acknowledged_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "messenger_group_sender_key_distributions"
        ordering = [
            "-created_at",
            "-id",
        ]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "sender_key",
                    "recipient_device",
                ],
                name="uniq_gskd_key_device",
            ),
            models.CheckConstraint(
                check=models.Q(distribution_version__gte=1),
                name="gskd_version_gte_1",
            ),
        ]
        indexes = [
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
                name="gskd_key_status_idx",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"Distribution {self.id} for sender key "
            f"{self.sender_key_id} to {self.recipient_device_id}"
        )

    def clean(self) -> None:
        super().clean()

        self.recipient_user_id = self.recipient_user_id.strip()
        self.encrypted_sender_key = self.encrypted_sender_key.strip()

        errors = {}

        if not self.recipient_user_id:
            errors["recipient_user_id"] = (
                "Recipient user ID is required."
            )

        if self.recipient_device_id:
            if self.recipient_device.user_id != self.recipient_user_id:
                errors["recipient_device"] = (
                    "Recipient device does not belong to recipient user."
                )

            if not self.recipient_device.is_active:
                errors["recipient_device"] = (
                    "Recipient device must be active."
                )

        if not self.encrypted_sender_key:
            errors["encrypted_sender_key"] = (
                "Encrypted sender key is required."
            )

        if not isinstance(self.distribution_metadata, dict):
            errors["distribution_metadata"] = (
                "Distribution metadata must be a JSON object."
            )

        if self.distribution_version < 1:
            errors["distribution_version"] = (
                "Distribution version must be at least 1."
            )

        if self.status not in GROUP_SENDER_KEY_DISTRIBUTION_STATUSES:
            errors["status"] = "Invalid distribution status."

        if self.status == self.Status.STORED and self.acknowledged_at is not None:
            errors["acknowledged_at"] = (
                "Stored distributions cannot have acknowledged_at."
            )

        if (
            self.status == self.Status.ACKNOWLEDGED
            and self.acknowledged_at is None
        ):
            errors["acknowledged_at"] = (
                "Acknowledged distributions must have acknowledged_at."
            )

        if self.sender_key_id and self.recipient_device_id:
            if (
                self.sender_key.sender_device_id
                == self.recipient_device_id
            ):
                errors["recipient_device"] = (
                    "Sender device does not need a sender-key distribution."
                )

        forbidden_words = (
            "plaintext",
            "private_key",
            "secret",
            "sender_chain_secret",
            "message_key",
            "ratchet",
            "recovery_key",
        )

        for key in self.distribution_metadata.keys():
            normalized_key = str(key).lower()
            if any(word in normalized_key for word in forbidden_words):
                errors["distribution_metadata"] = (
                    "Distribution metadata must not contain plaintext "
                    "or secret cryptographic material."
                )
                break

        if errors:
            raise ValidationError(errors)





class GroupSecurityTransition(models.Model):
    """Durable record for group security invalidation work.

    This is intentionally explicit instead of using implicit Django signals.
    Services create and apply transitions when membership/device changes must
    rotate the group epoch.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    group_room = models.ForeignKey(
        Room,
        on_delete=models.CASCADE,
        related_name="group_security_transitions",
    )

    reason = models.CharField(
        max_length=64,
    )

    actor_user_id = models.CharField(
        max_length=EXTERNAL_USER_ID_MAX_LENGTH,
    )

    target_user_id = models.CharField(
        max_length=EXTERNAL_USER_ID_MAX_LENGTH,
        blank=True,
        default="",
    )

    target_device = models.ForeignKey(
        Device,
        on_delete=models.SET_NULL,
        related_name="group_security_transitions",
        null=True,
        blank=True,
    )

    status = models.CharField(
        max_length=16,
        default=GROUP_SECURITY_TRANSITION_STATUS_PENDING,
    )

    attempt_count = models.PositiveSmallIntegerField(
        default=0,
    )

    last_error_code = models.CharField(
        max_length=120,
        blank=True,
        default="",
    )

    old_epoch_number = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    new_epoch_number = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    applied_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "messenger_group_security_transitions"
        ordering = [
            "-created_at",
            "-id",
        ]
        indexes = [
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
        ]

    def __str__(self) -> str:
        return (
            f"Security transition {self.reason} "
            f"for group {self.group_room_id} ({self.status})"
        )

    def clean(self) -> None:
        super().clean()

        self.reason = self.reason.strip()
        self.actor_user_id = self.actor_user_id.strip()
        self.target_user_id = self.target_user_id.strip()
        self.last_error_code = self.last_error_code.strip()

        errors = {}

        if self.group_room_id and self.group_room.room_type != ROOM_TYPE_GROUP:
            errors["group_room"] = (
                "Group security transitions can only attach to group rooms."
            )

        if self.reason not in GROUP_SECURITY_TRANSITION_REASONS:
            errors["reason"] = "Invalid group security transition reason."

        if self.status not in GROUP_SECURITY_TRANSITION_STATUSES:
            errors["status"] = "Invalid group security transition status."

        if not self.actor_user_id:
            errors["actor_user_id"] = "Actor user ID is required."

        if self.attempt_count < 0:
            errors["attempt_count"] = "attempt_count cannot be negative."

        if (
            self.status == GROUP_SECURITY_TRANSITION_STATUS_PENDING
            and self.applied_at is not None
        ):
            errors["applied_at"] = (
                "Pending transitions cannot have applied_at."
            )

        if (
            self.status == GROUP_SECURITY_TRANSITION_STATUS_APPLIED
            and self.applied_at is None
        ):
            errors["applied_at"] = (
                "Applied transitions must have applied_at."
            )

        if (
            self.status == GROUP_SECURITY_TRANSITION_STATUS_FAILED
            and not self.last_error_code
        ):
            errors["last_error_code"] = (
                "Failed transitions must include last_error_code."
            )

        if self.old_epoch_number is not None and self.old_epoch_number < 1:
            errors["old_epoch_number"] = (
                "old_epoch_number must be positive."
            )

        if self.new_epoch_number is not None and self.new_epoch_number < 1:
            errors["new_epoch_number"] = (
                "new_epoch_number must be positive."
            )

        if errors:
            raise ValidationError(errors)
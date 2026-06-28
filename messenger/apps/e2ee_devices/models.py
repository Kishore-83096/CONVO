import uuid

from django.core.exceptions import ValidationError
from django.db import models

from apps.rooms.models import EXTERNAL_USER_ID_MAX_LENGTH

from django.db.models import Q

class Device(models.Model):
    """
    A cryptographic device belonging to a user from the Identity service.

    Only public key material is stored here. Identity private keys,
    signed-prekey private keys and session keys must remain on the device.
    """

    class Platform(models.TextChoices):
        ANDROID = "android", "Android"
        IOS = "ios", "iOS"
        WEB = "web", "Web"
        DESKTOP = "desktop", "Desktop"
        OTHER = "other", "Other"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    user_id = models.CharField(
        max_length=EXTERNAL_USER_ID_MAX_LENGTH,
    )

    device_name = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    platform = models.CharField(
        max_length=20,
        choices=Platform.choices,
        default=Platform.OTHER,
    )

    # Signal-style registration identifier generated on the client.
    registration_id = models.PositiveIntegerField()

    # Base64-encoded public identity key.
    identity_key_public = models.TextField()

    # Version/identifier selected by the client for the current signed prekey.
    signed_prekey_id = models.PositiveIntegerField()

    # Base64-encoded signed-prekey public key.
    signed_prekey_public = models.TextField()

    # Signature over signed_prekey_public, produced by the device's
    # identity private key.
    signed_prekey_signature = models.TextField()

    key_algorithm = models.CharField(
        max_length=50,
        default="curve25519",
    )

    key_bundle_version = models.PositiveSmallIntegerField(
        default=1,
    )

    is_active = models.BooleanField(
        default=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    last_seen_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "messenger_devices"

        ordering = [
            "created_at",
        ]

        indexes = [
            models.Index(
                fields=[
                    "user_id",
                    "is_active",
                ],
                name="device_user_active_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} — {self.id}"

    def clean(self) -> None:
        super().clean()

        self.user_id = self.user_id.strip()
        self.device_name = self.device_name.strip()
        self.identity_key_public = self.identity_key_public.strip()
        self.signed_prekey_public = self.signed_prekey_public.strip()
        self.signed_prekey_signature = (
            self.signed_prekey_signature.strip()
        )
        self.key_algorithm = self.key_algorithm.strip().lower()

        errors = {}

        if not self.user_id:
            errors["user_id"] = "The external user ID is required."

        if not self.identity_key_public:
            errors["identity_key_public"] = (
                "The public identity key is required."
            )

        if not self.signed_prekey_public:
            errors["signed_prekey_public"] = (
                "The signed-prekey public key is required."
            )

        if not self.signed_prekey_signature:
            errors["signed_prekey_signature"] = (
                "The signed-prekey signature is required."
            )

        if not self.key_algorithm:
            errors["key_algorithm"] = (
                "The key algorithm is required."
            )

        if self.key_bundle_version < 1:
            errors["key_bundle_version"] = (
                "The key-bundle version must be at least 1."
            )

        if errors:
            raise ValidationError(errors)


class OneTimePreKey(models.Model):
    """
    A public one-time prekey uploaded by a registered device.

    A prekey is claimed at most once when another device begins a new
    encrypted session. The matching private key remains on its owner device.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    device = models.ForeignKey(
        Device,
        on_delete=models.CASCADE,
        related_name="one_time_prekeys",
    )

    # Client-assigned identifier used to locate the corresponding private
    # prekey on the recipient device.
    key_id = models.PositiveIntegerField()

    # Base64-encoded public one-time prekey.
    public_key = models.TextField()

    is_claimed = models.BooleanField(
        default=False,
    )

    claimed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        db_table = "messenger_one_time_prekeys"

        ordering = [
            "key_id",
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "device",
                    "key_id",
                ],
                name="unique_device_prekey_id",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        is_claimed=False,
                        claimed_at__isnull=True,
                    )
                    | models.Q(
                        is_claimed=True,
                        claimed_at__isnull=False,
                    )
                ),
                name="prekey_claim_state_valid",
            ),
        ]

        indexes = [
            models.Index(
                fields=[
                    "device",
                    "is_claimed",
                    "key_id",
                ],
                name="prekey_available_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"Prekey {self.key_id} for {self.device_id}"

    def clean(self) -> None:
        super().clean()

        self.public_key = self.public_key.strip()

        errors = {}

        if not self.public_key:
            errors["public_key"] = (
                "The public one-time prekey is required."
            )

        if self.is_claimed and self.claimed_at is None:
            errors["claimed_at"] = (
                "A claimed prekey must have a claimed-at time."
            )

        if not self.is_claimed and self.claimed_at is not None:
            errors["claimed_at"] = (
                "An available prekey cannot have a claimed-at time."
            )

        if errors:
            raise ValidationError(errors)


class RecoveryBundle(models.Model):
    """
    Stores only client-encrypted account recovery material.

    The server must never receive:
    - the plaintext recovery private key
    - the recovery secret
    - passkey PRF output
    - plaintext message keys
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    # External Identity-service user ID.
    user_id = models.CharField(
        max_length=128,
        unique=True,
    )

    # Public key used by clients to create recovery envelopes.
    recovery_public_key = models.TextField()

    # Recovery private key encrypted by the client using either:
    # - a recovery-key-derived wrapping key
    # - a passkey PRF-derived wrapping key
    encrypted_recovery_private_key = models.TextField()

    encryption_metadata = models.JSONField(
        default=dict,
    )

    recovery_version = models.PositiveSmallIntegerField(
        default=1,
    )

    is_active = models.BooleanField(
        default=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    rotated_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    disabled_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "messenger_recovery_bundles"

        indexes = [
            models.Index(
                fields=[
                    "user_id",
                    "is_active",
                ],
                name="recovery_user_active_idx",
            ),
        ]

        constraints = [
            models.CheckConstraint(
                condition=Q(
                    recovery_version__gte=1,
                ),
                name="recovery_version_gte_1",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        is_active=True,
                        disabled_at__isnull=True,
                    )
                    | Q(
                        is_active=False,
                        disabled_at__isnull=False,
                    )
                ),
                name="recovery_active_state_valid",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"RecoveryBundle("
            f"user={self.user_id}, "
            f"version={self.recovery_version}, "
            f"active={self.is_active}"
            f")"
        )
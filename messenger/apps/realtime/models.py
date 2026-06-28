import uuid

from django.db import models
from django.utils import timezone

from apps.e2ee_devices.models import Device
from apps.rooms.models import EXTERNAL_USER_ID_MAX_LENGTH


class RealtimeTicket(models.Model):
    """
    Short-lived one-use WebSocket authentication ticket.

    The raw ticket is returned to the client once and is never stored.
    Only ticket_hash is stored in the database.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    ticket_hash = models.CharField(
        max_length=64,
        unique=True,
    )

    user_id = models.CharField(
        max_length=EXTERNAL_USER_ID_MAX_LENGTH,
    )

    device = models.ForeignKey(
        Device,
        on_delete=models.CASCADE,
        related_name="realtime_tickets",
    )

    expires_at = models.DateTimeField()

    used_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
    )

    user_agent = models.TextField(
        blank=True,
        default="",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        db_table = "realtime_tickets"
        ordering = [
            "-created_at",
        ]
        indexes = [
            models.Index(
                fields=[
                    "user_id",
                    "created_at",
                ],
                name="rt_ticket_user_created_idx",
            ),
            models.Index(
                fields=[
                    "device",
                    "created_at",
                ],
                name="rt_ticket_device_created_idx",
            ),
            models.Index(
                fields=[
                    "expires_at",
                ],
                name="rt_ticket_expires_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"Realtime ticket for {self.user_id} / {self.device_id}"

    @property
    def is_used(self) -> bool:
        return self.used_at is not None

    @property
    def is_expired(self) -> bool:
        return self.expires_at <= timezone.now()
    

class RealtimeOutboxEvent(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        DELIVERED = "delivered", "Delivered"
        FAILED = "failed", "Failed"
        DEAD = "dead", "Dead"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    event_type = models.CharField(
        max_length=64,
    )
    target_group = models.CharField(
        max_length=255,
    )
    payload = models.JSONField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    attempts = models.PositiveIntegerField(
        default=0,
    )
    next_attempt_at = models.DateTimeField(
        default=timezone.now,
    )
    last_attempt_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    delivered_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    last_error = models.TextField(
        blank=True,
        default="",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        db_table = "realtime_outbox_events"
        ordering = [
            "created_at",
        ]
        indexes = [
            models.Index(
                fields=[
                    "status",
                    "next_attempt_at",
                ],
                name="rt_outbox_status_next_idx",
            ),
            models.Index(
                fields=[
                    "event_type",
                    "created_at",
                ],
                name="rt_outbox_type_created_idx",
            ),
            models.Index(
                fields=[
                    "target_group",
                    "created_at",
                ],
                name="rt_outbox_group_created_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.event_type} -> {self.target_group} ({self.status})"
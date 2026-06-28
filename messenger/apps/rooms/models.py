import hashlib
import json
import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


EXTERNAL_USER_ID_MAX_LENGTH = 128


class Room(models.Model):
    """
    Represents either a one-to-one room or a group room.

    Users belong to the separate identity service, so this service stores
    the user identifier received from a verified JWT instead of creating
    a ForeignKey to Django's built-in User model.
    """

    class RoomType(models.TextChoices):
        DIRECT = "direct", "Direct"
        GROUP = "group", "Group"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    room_type = models.CharField(
        max_length=10,
        choices=RoomType.choices,
    )

    # Used for group rooms. A direct room normally derives its display name
    # from the other participant's profile.
    name = models.CharField(
        max_length=120,
        blank=True,
        default="",
    )

    created_by_user_id = models.CharField(
        max_length=EXTERNAL_USER_ID_MAX_LENGTH,
    )

    # For direct rooms, this contains a SHA-256 hash created from the two
    # sorted external user IDs.
    #
    # unique=True guarantees that the same two users cannot have multiple
    # direct rooms, including when simultaneous requests occur.
    #
    # Group rooms store NULL here.
    direct_pair_key = models.CharField(
        max_length=64,
        unique=True,
        null=True,
        blank=True,
        editable=False,
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

    class Meta:
        db_table = "messenger_rooms"

        ordering = [
            "-updated_at",
        ]

        indexes = [
            models.Index(
                fields=[
                    "room_type",
                    "-updated_at",
                ],
                name="room_type_updated_idx",
            ),
            models.Index(
                fields=[
                    "created_by_user_id",
                ],
                name="room_creator_idx",
            ),
        ]

        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(
                        room_type="direct",
                        direct_pair_key__isnull=False,
                    )
                    | Q(
                        room_type="group",
                        direct_pair_key__isnull=True,
                    )
                ),
                name="room_pair_key_by_type",
            ),
        ]

    def __str__(self) -> str:
        if self.room_type == self.RoomType.GROUP:
            return self.name or f"Group {self.id}"

        return f"Direct room {self.id}"

    def clean(self) -> None:
        super().clean()

        self.created_by_user_id = self.created_by_user_id.strip()
        self.name = self.name.strip()

        errors = {}

        if not self.created_by_user_id:
            errors["created_by_user_id"] = (
                "The room creator user ID is required."
            )

        if self.room_type == self.RoomType.DIRECT:
            if not self.direct_pair_key:
                errors["direct_pair_key"] = (
                    "A direct room must have a direct pair key."
                )

        elif self.room_type == self.RoomType.GROUP:
            if self.direct_pair_key is not None:
                errors["direct_pair_key"] = (
                    "A group room cannot have a direct pair key."
                )

            if not self.name:
                errors["name"] = (
                    "A group room must have a name."
                )

        if errors:
            raise ValidationError(errors)

    @staticmethod
    def build_direct_pair_key(
        first_user_id: str,
        second_user_id: str,
    ) -> str:
        """
        Build the same pair key regardless of participant order.

        Example:
            build_direct_pair_key("user-a", "user-b")
            build_direct_pair_key("user-b", "user-a")

        Both calls return the same value.
        """

        normalized_first = str(first_user_id).strip()
        normalized_second = str(second_user_id).strip()

        if not normalized_first or not normalized_second:
            raise ValueError(
                "Both user IDs are required to create a direct-room key."
            )

        if normalized_first == normalized_second:
            raise ValueError(
                "A direct room requires two different users."
            )

        ordered_user_ids = sorted(
            [
                normalized_first,
                normalized_second,
            ]
        )

        serialized_pair = json.dumps(
            ordered_user_ids,
            separators=(",", ":"),
            ensure_ascii=False,
        )

        return hashlib.sha256(
            serialized_pair.encode("utf-8")
        ).hexdigest()


class RoomMember(models.Model):
    """
    Connects an external identity-service user to a room.

    A user can appear only once in a room. If a user leaves and later
    rejoins, the existing membership row will be reactivated rather than
    inserting a duplicate row.
    """

    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        ADMIN = "admin", "Admin"
        MEMBER = "member", "Member"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    room = models.ForeignKey(
        Room,
        on_delete=models.CASCADE,
        related_name="members",
    )

    user_id = models.CharField(
        max_length=EXTERNAL_USER_ID_MAX_LENGTH,
    )

    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.MEMBER,
    )

    added_by_user_id = models.CharField(
        max_length=EXTERNAL_USER_ID_MAX_LENGTH,
        blank=True,
        default="",
    )

    is_active = models.BooleanField(
        default=True,
    )

    joined_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    left_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    removed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    banned_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    removed_by_user_id = models.CharField(
        max_length=EXTERNAL_USER_ID_MAX_LENGTH,
        null=True,
        blank=True,
    )

    membership_version = models.PositiveIntegerField(
        default=1,
    )

    class Meta:
        db_table = "messenger_room_members"

        ordering = [
            "joined_at",
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "room",
                    "user_id",
                ],
                name="unique_room_user",
            ),
        ]

        indexes = [
            models.Index(
                fields=[
                    "room",
                    "is_active",
                ],
                name="member_room_active_idx",
            ),
            models.Index(
                fields=[
                    "user_id",
                    "is_active",
                ],
                name="member_user_active_idx",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"{self.user_id} in {self.room_id} "
            f"as {self.get_role_display()}"
        )

    def clean(self) -> None:
        super().clean()

        self.user_id = self.user_id.strip()
        self.added_by_user_id = self.added_by_user_id.strip()

        errors = {}

        if not self.user_id:
            errors["user_id"] = (
                "The external user ID is required."
            )

        if self.is_active and self.left_at is not None:
            errors["left_at"] = (
                "An active membership cannot have a left-at time."
            )

        if not self.is_active and self.left_at is None:
            errors["left_at"] = (
                "An inactive membership must have a left-at time."
            )

        if errors:
            raise ValidationError(errors)
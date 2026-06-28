from app.auth.models import utc_now
from app.extensions import db


class Contact(db.Model):
    __tablename__ = "contacts"
    __table_args__ = (
        db.UniqueConstraint(
            "owner_id",
            "contact_user_id",
            name="uq_contacts_owner_contact_user",
        ),
        db.CheckConstraint(
            "owner_id <> contact_user_id",
            name="ck_contacts_not_self",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    contact_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    saved_name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    owner = db.relationship(
        "User",
        foreign_keys=[owner_id],
        back_populates="contacts",
    )
    contact_user = db.relationship(
        "User",
        foreign_keys=[contact_user_id],
        back_populates="contact_entries",
    )


class ContactDeliveryPolicy(db.Model):
    """
    Identity-owned delivery policy for one owner -> target relationship.

    Keep this separate from contacts so deleting a saved contact does not
    delete a block rule.
    """

    __tablename__ = "contact_delivery_policies"
    __table_args__ = (
        db.UniqueConstraint(
            "owner_id",
            "target_user_id",
            name="uq_contact_delivery_policy_owner_target",
        ),
        db.CheckConstraint(
            "owner_id <> target_user_id",
            name="ck_contact_delivery_policy_not_self",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)

    # The user who owns the rule.
    # Example: A blocked B => owner_id = A.
    owner_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # The user affected by the rule.
    # Example: A blocked B => target_user_id = B.
    target_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    is_blocked = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
    )

    blocked_at = db.Column(
        db.DateTime(timezone=True),
        nullable=True,
    )

    ghost_until = db.Column(
        db.DateTime(timezone=True),
        nullable=True,
    )

    ghost_permanent = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
    )

    ghost_duration_option = db.Column(
        db.String(20),
        nullable=True,
    )
    policy_version = db.Column(
        db.Integer,
        nullable=False,
        default=1,
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    owner = db.relationship(
        "User",
        foreign_keys=[owner_id],
        back_populates="owned_delivery_policies",
    )

    target_user = db.relationship(
        "User",
        foreign_keys=[target_user_id],
        back_populates="targeted_delivery_policies",
    )
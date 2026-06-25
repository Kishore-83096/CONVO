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

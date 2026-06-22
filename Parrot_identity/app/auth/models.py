from datetime import datetime, timezone

from werkzeug.security import (
    check_password_hash,
    generate_password_hash,
)

from app.extensions import db


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    username = db.Column(
        db.String(30),
        nullable=False,
        unique=True,
        index=True,
    )
    email = db.Column(
        db.String(255),
        nullable=False,
        unique=True,
        index=True,
    )
    contact_number = db.Column(
        db.BigInteger,
        nullable=False,
        unique=True,
        index=True,
    )
    password_hash = db.Column(db.String(255), nullable=False)
    is_active = db.Column(
        db.Boolean,
        nullable=False,
        default=True,
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

    sessions = db.relationship(
        "AuthSession",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    profile_basic = db.relationship(
        "ProfileBasic",
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
    )
    profile_address = db.relationship(
        "ProfileAddress",
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
    )
    profile_picture = db.relationship(
        "ProfilePicture",
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
    )
    profile_events = db.relationship(
        "ProfileEvent",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    contacts = db.relationship(
        "Contact",
        foreign_keys="Contact.owner_id",
        back_populates="owner",
        cascade="all, delete-orphan",
    )
    contact_entries = db.relationship(
        "Contact",
        foreign_keys="Contact.contact_user_id",
        back_populates="contact_user",
        cascade="all, delete-orphan",
    )

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class AuthSession(db.Model):
    __tablename__ = "auth_sessions"

    id = db.Column(db.Integer, primary_key=True)
    jti = db.Column(
        db.String(36),
        nullable=False,
        unique=True,
        index=True,
    )
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    expires_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
    )
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    user = db.relationship("User", back_populates="sessions")

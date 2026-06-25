from app.auth.models import utc_now
from app.extensions import db


class ProfileBasic(db.Model):
    __tablename__ = "profile_basics"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    bio = db.Column(db.String(500))
    date_of_birth = db.Column(db.Date)
    gender = db.Column(db.String(50))
    occupation = db.Column(db.String(100))
    website = db.Column(db.String(255))
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

    user = db.relationship("User", back_populates="profile_basic")


class ProfileAddress(db.Model):
    __tablename__ = "profile_addresses"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    address_line_1 = db.Column(db.String(150), nullable=False)
    address_line_2 = db.Column(db.String(150))
    city = db.Column(db.String(100), nullable=False)
    state = db.Column(db.String(100))
    postal_code = db.Column(db.String(20))
    country = db.Column(db.String(100), nullable=False)
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

    user = db.relationship("User", back_populates="profile_address")


class ProfilePicture(db.Model):
    __tablename__ = "profile_pictures"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    public_id = db.Column(db.String(255), nullable=False, unique=True)
    version = db.Column(db.BigInteger)
    image_format = db.Column(db.String(20))
    width = db.Column(db.Integer)
    height = db.Column(db.Integer)
    file_size = db.Column(db.Integer)
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

    user = db.relationship("User", back_populates="profile_picture")


class ProfileEvent(db.Model):
    __tablename__ = "profile_events"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_name = db.Column(db.String(80), nullable=False)
    event_date = db.Column(db.Date, nullable=False)
    description = db.Column(db.String(300))
    recurring = db.Column(db.Boolean, nullable=False, default=True)
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

    user = db.relationship("User", back_populates="profile_events")

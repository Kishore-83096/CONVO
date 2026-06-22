from datetime import datetime, timezone
from secrets import randbelow

from flask_jwt_extended import create_access_token, decode_token
from sqlalchemy import delete, or_, select
from sqlalchemy.exc import IntegrityError

from app.auth.models import AuthSession, User
from app.extensions import db
from app.shared.exceptions import ApiError


CONTACT_NUMBER_MINIMUM = 1_000_000_000
CONTACT_NUMBER_RANGE = 9_000_000_000
CONTACT_NUMBER_ATTEMPTS = 20


def user_details(user: User, *, include_username: bool = False) -> dict:
    details = {
        "full_name": user.full_name,
        "email": user.email,
        "contact_number": user.contact_number,
    }

    if include_username:
        details["username"] = user.username

    return details


def username_or_email_exists(username: str, email: str) -> bool:
    statement = select(User.id).where(
        or_(User.username == username, User.email == email)
    )
    return db.session.scalar(statement) is not None


def generate_unique_contact_number() -> int:
    for _ in range(CONTACT_NUMBER_ATTEMPTS):
        candidate = CONTACT_NUMBER_MINIMUM + randbelow(
            CONTACT_NUMBER_RANGE
        )
        statement = select(User.id).where(
            User.contact_number == candidate
        )

        if db.session.scalar(statement) is None:
            return candidate

    raise ApiError(
        "Unable to generate a contact number. Try again.",
        status_code=503,
    )


def register_user(payload: dict) -> User:
    username = payload["username"]
    email = f"{username}@parrot.com"

    if username_or_email_exists(username, email):
        raise ApiError(
            "Username is already registered.",
            status_code=409,
            errors={"username": ["Choose a different username."]},
        )

    for _ in range(CONTACT_NUMBER_ATTEMPTS):
        user = User(
            full_name=payload["full_name"],
            username=username,
            email=email,
            contact_number=generate_unique_contact_number(),
        )
        user.set_password(payload["password"])
        db.session.add(user)

        try:
            db.session.commit()
            return user
        except IntegrityError:
            db.session.rollback()

            if username_or_email_exists(username, email):
                raise ApiError(
                    "Username is already registered.",
                    status_code=409,
                    errors={
                        "username": ["Choose a different username."]
                    },
                )

    raise ApiError(
        "Unable to create the account. Try again.",
        status_code=503,
    )


def normalize_login_identifier(method: str, identifier) -> str | int:
    value = str(identifier).strip().lower()

    if method == "username":
        value = value.removeprefix("@")
        if not value:
            raise ApiError(
                "Invalid credentials. Try again.",
                status_code=401,
            )
        return value

    if method == "email":
        if not value:
            raise ApiError(
                "Invalid credentials. Try again.",
                status_code=401,
            )
        return value

    if not value.isdigit() or len(value) != 10:
        raise ApiError(
            "Invalid credentials. Try again.",
            status_code=401,
        )

    return int(value)


def find_user(method: str, identifier) -> User | None:
    normalized_identifier = normalize_login_identifier(
        method,
        identifier,
    )
    columns = {
        "email": User.email,
        "contact_number": User.contact_number,
        "username": User.username,
    }
    statement = select(User).where(
        columns[method] == normalized_identifier
    )
    return db.session.scalar(statement)


def login_user(payload: dict) -> tuple[User, str, datetime]:
    user = find_user(payload["method"], payload["identifier"])

    if (
        user is None
        or not user.is_active
        or not user.check_password(payload["password"])
    ):
        raise ApiError(
            "Invalid credentials. Try again.",
            status_code=401,
        )

    access_token = create_access_token(identity=str(user.id))
    decoded_token = decode_token(access_token)
    expires_at = datetime.fromtimestamp(
        decoded_token["exp"],
        tz=timezone.utc,
    )
    session = AuthSession(
        jti=decoded_token["jti"],
        user_id=user.id,
        expires_at=expires_at,
    )
    db.session.execute(
        delete(AuthSession).where(
            AuthSession.user_id == user.id,
            AuthSession.expires_at <= datetime.now(timezone.utc),
        )
    )
    db.session.add(session)
    db.session.commit()

    return user, access_token, expires_at


def logout_session(jti: str) -> None:
    statement = select(AuthSession).where(AuthSession.jti == jti)
    session = db.session.scalar(statement)

    if session is None:
        raise ApiError(
            "Session is no longer active.",
            status_code=401,
        )

    db.session.delete(session)
    db.session.commit()

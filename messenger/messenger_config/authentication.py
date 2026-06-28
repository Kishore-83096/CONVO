from dataclasses import dataclass
from typing import Any, Mapping

import jwt
from django.conf import settings
from rest_framework.authentication import (
    BaseAuthentication,
    get_authorization_header,
)
from rest_framework.exceptions import AuthenticationFailed


@dataclass(frozen=True, slots=True)
class AuthenticatedIdentity:
    """
    Represents a user authenticated by the separate identity service.

    This is not a Django database User model. The identity service remains
    the source of truth for accounts, profiles, login and contacts.
    """

    user_id: str
    claims: Mapping[str, Any]

    @property
    def id(self) -> str:
        return self.user_id

    @property
    def pk(self) -> str:
        return self.user_id

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def is_anonymous(self) -> bool:
        return False

    def __str__(self) -> str:
        return self.user_id


class IdentityJWTAuthentication(BaseAuthentication):
    """
    Verify access JWTs issued by the identity service.

    The allowed JWT algorithm comes only from server configuration.
    It is never accepted from the untrusted token header.
    """

    keyword = "Bearer"
    realm = "messenger-api"

    def authenticate(
        self,
        request,
    ) -> tuple[AuthenticatedIdentity, dict[str, Any]] | None:
        authorization_parts = get_authorization_header(
            request
        ).split()

        if not authorization_parts:
            return None

        if authorization_parts[0].lower() != self.keyword.lower().encode():
            return None

        if len(authorization_parts) != 2:
            raise AuthenticationFailed(
                "Authorization header must use: "
                "Bearer <access-token>."
            )

        try:
            encoded_token = authorization_parts[1].decode("ascii")
        except UnicodeDecodeError as error:
            raise AuthenticationFailed(
                "The access token contains invalid characters."
            ) from error

        required_claims = list(
            dict.fromkeys(
                [
                    "exp",
                    settings.JWT_IDENTITY_CLAIM,
                    settings.JWT_TOKEN_TYPE_CLAIM,
                ]
            )
        )

        decode_options = {
            "require": required_claims,
            "verify_aud": settings.JWT_AUDIENCE is not None,
            "verify_iss": settings.JWT_ISSUER is not None,
        }

        try:
            claims = jwt.decode(
                encoded_token,
                key=settings.JWT_VERIFYING_KEY,
                algorithms=[
                    settings.JWT_ALGORITHM,
                ],
                audience=settings.JWT_AUDIENCE,
                issuer=settings.JWT_ISSUER,
                leeway=settings.JWT_LEEWAY_SECONDS,
                options=decode_options,
            )

        except jwt.ExpiredSignatureError as error:
            raise AuthenticationFailed(
                "The access token has expired."
            ) from error

        except jwt.ImmatureSignatureError as error:
            raise AuthenticationFailed(
                "The access token is not active yet."
            ) from error

        except jwt.InvalidAudienceError as error:
            raise AuthenticationFailed(
                "The access token has an invalid audience."
            ) from error

        except jwt.InvalidIssuerError as error:
            raise AuthenticationFailed(
                "The access token has an invalid issuer."
            ) from error

        except jwt.MissingRequiredClaimError as error:
            raise AuthenticationFailed(
                f"The access token is missing the "
                f"'{error.claim}' claim."
            ) from error

        except jwt.InvalidTokenError as error:
            raise AuthenticationFailed(
                "The access token is invalid."
            ) from error

        token_type = claims.get(
            settings.JWT_TOKEN_TYPE_CLAIM
        )

        if token_type != settings.JWT_ACCESS_TOKEN_TYPE:
            raise AuthenticationFailed(
                "Only access tokens can be used with this API."
            )

        raw_user_id = claims.get(
            settings.JWT_IDENTITY_CLAIM
        )

        user_id = str(raw_user_id).strip()

        if not user_id:
            raise AuthenticationFailed(
                "The access token does not contain a valid user ID."
            )

        identity = AuthenticatedIdentity(
            user_id=user_id,
            claims=claims,
        )

        return identity, claims

    def authenticate_header(self, request) -> str:
        return f'{self.keyword} realm="{self.realm}"'
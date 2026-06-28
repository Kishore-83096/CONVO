from django.conf import settings
from rest_framework.permissions import AllowAny
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthView(APIView):
    """
    Public service health check.
    """

    authentication_classes = []
    permission_classes = [
        AllowAny,
    ]

    def get(self, request) -> Response:
        return Response(
            {
                "message": "Messenger service is running.",
                "service": "messenger-service",
                "environment": settings.APP_ENV,
            }
        )


class CurrentIdentityView(APIView):
    """
    Temporary endpoint for verifying JWT integration.

    This endpoint exposes only limited non-secret token information.
    """

    permission_classes = [
        IsAuthenticated,
    ]

    def get(self, request) -> Response:
        claims = request.auth or {}

        return Response(
            {
                "authenticated": True,
                "user_id": request.user.user_id,
                "token_type": claims.get(
                    settings.JWT_TOKEN_TYPE_CLAIM
                ),
                "expires_at": claims.get("exp"),
            }
        )

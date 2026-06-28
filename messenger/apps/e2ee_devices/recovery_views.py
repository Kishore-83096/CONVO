from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .recovery_serializers import (
    RecoveryBundleDownloadSerializer,
    RecoverySetupResultSerializer,
    RecoverySetupSerializer,
)
from .recovery_services import (
    RecoveryAlreadyConfiguredError,
    RecoveryBundleUnavailableError,
    get_active_recovery_bundle,
    get_recovery_status,
    setup_recovery_bundle,
)


def get_authenticated_user_id(request) -> str:
    """
    Resolve the external Identity-service user ID without trusting
    request data supplied by the client.
    """

    for attribute_name in (
        "id",
        "pk",
        "user_id",
    ):
        value = getattr(
            request.user,
            attribute_name,
            None,
        )
        if value is not None:
            return str(value)

    if isinstance(request.auth, dict):
        value = request.auth.get("sub")
        if value is not None:
            return str(value)

    raise RuntimeError(
        "Authenticated identity does not expose a user ID."
    )


class RecoverySetupView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def post(self, request):
        serializer = RecoverySetupSerializer(
            data=request.data,
        )

        if not serializer.is_valid():
            return Response(
                {
                    "success": False,
                    "message": "Validation failed.",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        user_id = get_authenticated_user_id(request)

        try:
            result = setup_recovery_bundle(
                user_id=user_id,
                **serializer.validated_data,
            )
        except RecoveryAlreadyConfiguredError as error:
            return Response(
                {
                    "success": False,
                    "message": str(error),
                },
                status=status.HTTP_409_CONFLICT,
            )

        response_status = (
            status.HTTP_201_CREATED
            if result.created
            else status.HTTP_200_OK
        )

        response_message = (
            "Encrypted recovery configured successfully."
            if result.created
            else "Encrypted recovery re-enabled successfully."
        )

        return Response(
            {
                "success": True,
                "message": response_message,
                "data": RecoverySetupResultSerializer(
                    result.bundle
                ).data,
            },
            status=response_status,
        )


class RecoveryStatusView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def get(self, request):
        user_id = get_authenticated_user_id(request)
        recovery_status = get_recovery_status(
            user_id=user_id,
        )

        return Response(
            {
                "success": True,
                "message": (
                    "Encrypted recovery status retrieved "
                    "successfully."
                ),
                "data": recovery_status,
            },
            status=status.HTTP_200_OK,
        )


class RecoveryBundleView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def get(self, request):
        user_id = get_authenticated_user_id(request)

        try:
            bundle = get_active_recovery_bundle(
                user_id=user_id,
            )
        except RecoveryBundleUnavailableError as error:
            return Response(
                {
                    "success": False,
                    "message": str(error),
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {
                "success": True,
                "message": (
                    "Encrypted recovery bundle retrieved "
                    "successfully."
                ),
                "data": RecoveryBundleDownloadSerializer(
                    bundle
                ).data,
            },
            status=status.HTTP_200_OK,
        )

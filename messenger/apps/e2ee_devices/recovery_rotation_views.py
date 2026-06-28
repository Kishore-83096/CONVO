from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .recovery_rotation_serializers import (
    RecoveryRotateSerializer,
)
from .recovery_rotation_services import (
    RecoveryRotationConflictError,
    RecoveryRotationUnavailableError,
    RecoveryRotationValidationError,
    disable_recovery,
    rotate_recovery_bundle,
)
from .recovery_views import get_authenticated_user_id


class RecoveryRotateView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def post(self, request):
        serializer = RecoveryRotateSerializer(
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
            result = rotate_recovery_bundle(
                user_id=user_id,
                **serializer.validated_data,
            )
        except RecoveryRotationUnavailableError as error:
            return Response(
                {
                    "success": False,
                    "message": str(error),
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        except RecoveryRotationValidationError as error:
            return Response(
                {
                    "success": False,
                    "message": str(error),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except RecoveryRotationConflictError as error:
            return Response(
                {
                    "success": False,
                    "message": str(error),
                },
                status=status.HTTP_409_CONFLICT,
            )

        response_status = (
            status.HTTP_200_OK
        )

        response_message = (
            "Encrypted recovery rotated successfully."
            if result.rotation_applied
            else "Existing recovery rotation returned."
        )

        return Response(
            {
                "success": True,
                "message": response_message,
                "data": {
                    "recovery_version": (
                        result.bundle.recovery_version
                    ),
                    "rotated_envelope_count": (
                        result.rotated_envelope_count
                    ),
                    "rotation_applied": (
                        result.rotation_applied
                    ),
                    "rotated_at": (
                        result.bundle.rotated_at
                    ),
                },
            },
            status=response_status,
        )


class RecoveryDisableView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def delete(self, request):
        user_id = get_authenticated_user_id(request)
        result = disable_recovery(
            user_id=user_id,
        )

        return Response(
            {
                "success": True,
                "message": (
                    "Encrypted recovery disabled "
                    "successfully."
                ),
                "data": {
                    "bundle_deleted": (
                        result.bundle_deleted
                    ),
                    "deleted_recovery_envelope_count": (
                        result
                        .deleted_recovery_envelope_count
                    ),
                },
            },
            status=status.HTTP_200_OK,
        )

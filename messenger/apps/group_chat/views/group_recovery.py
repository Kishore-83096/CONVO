from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..serializers.group_recovery import (
    GroupRecoveryRecipientsResponseSerializer,
)
from ..services.group_recovery import (
    GroupRecoveryNotFoundError,
    GroupRecoveryPermissionError,
    GroupRecoveryValidationError,
    list_group_recovery_recipients,
)


def _service_error_response(error, response_status):
    return Response(
        {
            "success": False,
            "message": str(error),
        },
        status=response_status,
    )


class GroupRecoveryRecipientsView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def get(self, request, group_id) -> Response:
        try:
            result = list_group_recovery_recipients(
                group_id=group_id,
                authenticated_user_id=str(request.user.user_id),
            )
        except GroupRecoveryValidationError as error:
            return _service_error_response(
                error,
                status.HTTP_400_BAD_REQUEST,
            )
        except GroupRecoveryPermissionError as error:
            return _service_error_response(
                error,
                status.HTTP_403_FORBIDDEN,
            )
        except GroupRecoveryNotFoundError as error:
            return _service_error_response(
                error,
                status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {
                "success": True,
                "message": (
                    "Group recovery recipients retrieved successfully."
                ),
                "data": GroupRecoveryRecipientsResponseSerializer(
                    result,
                ).data,
            },
            status=status.HTTP_200_OK,
        )
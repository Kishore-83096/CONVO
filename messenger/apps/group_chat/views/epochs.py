from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..serializers.epochs import (
    GroupEncryptionEpochSerializer,
    RotateGroupEpochSerializer,
)
from ..services.epochs import (
    GroupEpochConflictError,
    GroupEpochNotFoundError,
    GroupEpochPermissionError,
    GroupEpochValidationError,
    get_current_group_epoch,
    list_group_epochs,
    rotate_group_epoch,
)


def _validation_error_response(errors):
    return Response(
        {
            "success": False,
            "message": "Validation failed.",
            "errors": errors,
        },
        status=status.HTTP_400_BAD_REQUEST,
    )


def _service_error_response(error, response_status):
    return Response(
        {
            "success": False,
            "message": str(error),
        },
        status=response_status,
    )


class CurrentGroupEpochView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def get(self, request, group_id) -> Response:
        try:
            epoch = get_current_group_epoch(
                authenticated_user_id=str(request.user.user_id),
                group_id=group_id,
            )
        except GroupEpochValidationError as error:
            return _service_error_response(
                error,
                status.HTTP_400_BAD_REQUEST,
            )
        except GroupEpochNotFoundError as error:
            return _service_error_response(
                error,
                status.HTTP_404_NOT_FOUND,
            )

        serializer = GroupEncryptionEpochSerializer(epoch)

        return Response(
            {
                "success": True,
                "message": "Current group epoch retrieved successfully.",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class GroupEpochListView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def get(self, request, group_id) -> Response:
        try:
            epochs = list_group_epochs(
                authenticated_user_id=str(request.user.user_id),
                group_id=group_id,
            )
        except GroupEpochValidationError as error:
            return _service_error_response(
                error,
                status.HTTP_400_BAD_REQUEST,
            )
        except GroupEpochNotFoundError as error:
            return _service_error_response(
                error,
                status.HTTP_404_NOT_FOUND,
            )

        serializer = GroupEncryptionEpochSerializer(
            epochs,
            many=True,
        )

        return Response(
            {
                "success": True,
                "message": "Group epochs retrieved successfully.",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class GroupEpochRotateView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def post(self, request, group_id) -> Response:
        serializer = RotateGroupEpochSerializer(
            data=request.data,
        )

        if not serializer.is_valid():
            return _validation_error_response(serializer.errors)

        try:
            epoch = rotate_group_epoch(
                authenticated_user_id=str(request.user.user_id),
                group_id=group_id,
                reason=serializer.validated_data["reason"],
            )
        except GroupEpochValidationError as error:
            return _service_error_response(
                error,
                status.HTTP_400_BAD_REQUEST,
            )
        except GroupEpochPermissionError as error:
            return _service_error_response(
                error,
                status.HTTP_403_FORBIDDEN,
            )
        except GroupEpochNotFoundError as error:
            return _service_error_response(
                error,
                status.HTTP_404_NOT_FOUND,
            )
        except GroupEpochConflictError as error:
            return _service_error_response(
                error,
                status.HTTP_409_CONFLICT,
            )

        serializer = GroupEncryptionEpochSerializer(epoch)

        return Response(
            {
                "success": True,
                "message": "Group epoch rotated successfully.",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )
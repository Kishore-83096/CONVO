from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .group_history_serializers import (
    GroupHistoryItemSerializer,
    GroupHistoryQuerySerializer,
)
from .group_history_services import (
    GroupHistoryNotFoundError,
    GroupHistoryPermissionError,
    GroupHistoryValidationError,
    list_group_encrypted_history,
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


class GroupHistoryView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def get(self, request, group_id) -> Response:
        serializer = GroupHistoryQuerySerializer(
            data=request.query_params,
        )

        if not serializer.is_valid():
            return _validation_error_response(serializer.errors)

        data = serializer.validated_data

        try:
            page = list_group_encrypted_history(
                authenticated_user_id=str(request.user.user_id),
                group_id=group_id,
                device_id=data["device_id"],
                page_size=data.get("page_size", 50),
                cursor=data.get("cursor"),
            )
        except GroupHistoryValidationError as error:
            return _service_error_response(
                error,
                status.HTTP_400_BAD_REQUEST,
            )
        except GroupHistoryPermissionError as error:
            return _service_error_response(
                error,
                status.HTTP_403_FORBIDDEN,
            )
        except GroupHistoryNotFoundError as error:
            return _service_error_response(
                error,
                status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {
                "success": True,
                "message": "Group encrypted history retrieved successfully.",
                "data": {
                    "items": GroupHistoryItemSerializer(
                        page.items,
                        many=True,
                    ).data,
                    "next_cursor": page.next_cursor,
                    "page_size": page.page_size,
                },
            },
            status=status.HTTP_200_OK,
        )
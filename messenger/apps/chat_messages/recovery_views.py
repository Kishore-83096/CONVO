from rest_framework import status
from rest_framework.pagination import CursorPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .recovery_serializers import (
    RecoveryHistoryMessageSerializer,
    RecoveryRewrapSerializer,
)
from .recovery_services import (
    RecoveryAccessError,
    RecoveryDeviceAccessError,
    RecoveryEnvelopeAccessError,
    RecoveryRewrapConflictError,
    get_recovery_history_queryset,
    rewrap_recovery_messages_for_device,
)


def get_authenticated_user_id(request) -> str:
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


class RecoveryHistoryPagination(CursorPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 100
    ordering = (
        "-created_at",
        "-id",
    )


class RecoveryHistoryView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]
    pagination_class = RecoveryHistoryPagination

    def get(self, request):
        user_id = get_authenticated_user_id(request)

        try:
            queryset = get_recovery_history_queryset(
                user_id=user_id,
            )
        except RecoveryAccessError as error:
            return Response(
                {
                    "success": False,
                    "message": str(error),
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(
            queryset,
            request,
            view=self,
        )

        serializer = RecoveryHistoryMessageSerializer(
            page,
            many=True,
        )

        return Response(
            {
                "success": True,
                "message": (
                    "Encrypted recovery history retrieved "
                    "successfully."
                ),
                "data": {
                    "next": paginator.get_next_link(),
                    "previous": paginator.get_previous_link(),
                    "messages": serializer.data,
                },
            },
            status=status.HTTP_200_OK,
        )


class RecoveryRewrapView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def post(self, request):
        serializer = RecoveryRewrapSerializer(
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
            result = rewrap_recovery_messages_for_device(
                user_id=user_id,
                **serializer.validated_data,
            )
        except RecoveryAccessError as error:
            return Response(
                {
                    "success": False,
                    "message": str(error),
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        except (
            RecoveryDeviceAccessError,
            RecoveryEnvelopeAccessError,
        ) as error:
            return Response(
                {
                    "success": False,
                    "message": str(error),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except RecoveryRewrapConflictError as error:
            return Response(
                {
                    "success": False,
                    "message": str(error),
                },
                status=status.HTTP_409_CONFLICT,
            )

        response_status = (
            status.HTTP_201_CREATED
            if result.created_count > 0
            else status.HTTP_200_OK
        )

        return Response(
            {
                "success": True,
                "message": (
                    "Recovered message keys were wrapped for "
                    "the device successfully."
                ),
                "data": {
                    "device_id": str(result.device.id),
                    "created_count": result.created_count,
                    "existing_count": result.existing_count,
                    "total_count": result.total_count,
                },
            },
            status=response_status,
        )

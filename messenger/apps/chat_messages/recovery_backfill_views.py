from rest_framework import status
from rest_framework.pagination import CursorPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .recovery_backfill_serializers import (
    RecoveryBackfillCandidateQuerySerializer,
    RecoveryBackfillCandidateSerializer,
    RecoveryBackfillSerializer,
)
from .recovery_backfill_services import (
    RecoveryBackfillAccessError,
    RecoveryBackfillConflictError,
    RecoveryBackfillDeviceError,
    RecoveryBackfillUnavailableError,
    backfill_recovery_envelopes,
    get_recovery_backfill_candidates,
)
from .recovery_views import get_authenticated_user_id


def validation_error_response(errors):
    return Response(
        {
            "success": False,
            "message": "Validation failed.",
            "errors": errors,
        },
        status=status.HTTP_400_BAD_REQUEST,
    )


class RecoveryBackfillCursorPagination(CursorPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 100
    ordering = (
        "-created_at",
        "-id",
    )


class RecoveryBackfillCandidateView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def get(self, request):
        query_serializer = (
            RecoveryBackfillCandidateQuerySerializer(
                data=request.query_params,
            )
        )

        if not query_serializer.is_valid():
            return validation_error_response(
                query_serializer.errors,
            )

        user_id = get_authenticated_user_id(request)

        try:
            result = get_recovery_backfill_candidates(
                user_id=user_id,
                device_id=(
                    query_serializer.validated_data[
                        "device_id"
                    ]
                ),
            )
        except RecoveryBackfillUnavailableError as error:
            return Response(
                {
                    "success": False,
                    "message": str(error),
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        except RecoveryBackfillDeviceError:
            return Response(
                {
                    "success": False,
                    "message": (
                        "Recovery backfill is unavailable "
                        "for this device."
                    ),
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        paginator = RecoveryBackfillCursorPagination()
        page = paginator.paginate_queryset(
            result.messages,
            request,
            view=self,
        )

        serializer = RecoveryBackfillCandidateSerializer(
            page,
            many=True,
        )

        return Response(
            {
                "success": True,
                "message": (
                    "Recovery backfill candidates retrieved "
                    "successfully."
                ),
                "data": {
                    "device_id": str(result.device.id),
                    "recovery_key_version": (
                        result.bundle.recovery_version
                    ),
                    "next": paginator.get_next_link(),
                    "previous": (
                        paginator.get_previous_link()
                    ),
                    "messages": serializer.data,
                },
            },
            status=status.HTTP_200_OK,
        )


class RecoveryBackfillView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def post(self, request):
        serializer = RecoveryBackfillSerializer(
            data=request.data,
        )

        if not serializer.is_valid():
            return validation_error_response(
                serializer.errors,
            )

        user_id = get_authenticated_user_id(request)

        try:
            result = backfill_recovery_envelopes(
                user_id=user_id,
                **serializer.validated_data,
            )
        except RecoveryBackfillUnavailableError as error:
            return Response(
                {
                    "success": False,
                    "message": str(error),
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        except (
            RecoveryBackfillDeviceError,
            RecoveryBackfillAccessError,
        ):
            return Response(
                {
                    "success": False,
                    "message": (
                        "Recovery backfill is unavailable "
                        "for one or more messages."
                    ),
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        except RecoveryBackfillConflictError as error:
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
                    "Recovery envelopes backfilled "
                    "successfully."
                ),
                "data": {
                    "device_id": str(result.device.id),
                    "recovery_key_version": (
                        result.bundle.recovery_version
                    ),
                    "created_count": (
                        result.created_count
                    ),
                    "existing_count": (
                        result.existing_count
                    ),
                    "total_count": result.total_count,
                },
            },
            status=response_status,
        )

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import (
    PresenceBatchSerializer,
    RealtimeTicketCreateSerializer,
)
from .services import (
    RealtimeTicketDeviceNotFoundError,
    RealtimeTicketDeviceOwnershipError,
    RealtimeTicketInactiveDeviceError,
    RealtimeTicketServiceError,
    create_realtime_ticket,
    get_presence_snapshot_for_viewer,
)
from asgiref.sync import async_to_sync
from django.conf import settings

def validation_error_response(errors):
    return Response(
        {
            "success": False,
            "message": "Validation failed.",
            "errors": errors,
        },
        status=status.HTTP_400_BAD_REQUEST,
    )


def get_client_ip(request) -> str | None:
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")

    if forwarded_for:
        return forwarded_for.split(",")[0].strip() or None

    return request.META.get("REMOTE_ADDR")


class RealtimeTicketCreateView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def post(self, request) -> Response:
        serializer = RealtimeTicketCreateSerializer(
            data=request.data,
        )

        if not serializer.is_valid():
            return validation_error_response(
                serializer.errors,
            )

        try:
            result = create_realtime_ticket(
                authenticated_user_id=request.user.user_id,
                device_id=serializer.validated_data["device_id"],
                ip_address=get_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            )

        except RealtimeTicketDeviceNotFoundError as error:
            return Response(
                {
                    "success": False,
                    "message": str(error),
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        except (
            RealtimeTicketDeviceOwnershipError,
            RealtimeTicketInactiveDeviceError,
        ) as error:
            return Response(
                {
                    "success": False,
                    "message": str(error),
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        except RealtimeTicketServiceError as error:
            return Response(
                {
                    "success": False,
                    "message": str(error),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        ticket_record = result.ticket_record

        return Response(
            {
                "success": True,
                "message": "Realtime ticket created successfully.",
                "data": {
                    "ticket": result.ticket,
                    "expires_at": ticket_record.expires_at.isoformat(),
                    "device_id": str(ticket_record.device_id),
                    "heartbeat_seconds": settings.REALTIME_HEARTBEAT_SECONDS,
                },
            },
            status=status.HTTP_201_CREATED,
        )



class PresenceBatchView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def post(self, request) -> Response:
        serializer = PresenceBatchSerializer(
            data=request.data,
        )

        if not serializer.is_valid():
            return validation_error_response(
                serializer.errors,
            )

        viewer_user_id = request.user.user_id
        items = []

        for subject_user_id in serializer.validated_data["user_ids"]:
            snapshot = async_to_sync(get_presence_snapshot_for_viewer)(
                viewer_user_id=viewer_user_id,
                subject_user_id=subject_user_id,
            )

            items.append(snapshot)

        return Response(
            {
                "success": True,
                "message": "Presence batch fetched successfully.",
                "data": {
                    "items": items,
                },
            },
            status=status.HTTP_200_OK,
        )
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.realtime.publishers import (
    schedule_message_delivered_receipts_publish,
    schedule_message_read_receipts_publish,
)
from .receipt_serializers import (
    DeliveredReceiptRequestSerializer,
    MessageReceiptSummarySerializer,
    ReadReceiptRequestSerializer,
)
from .receipt_services import (
    ReceiptConflictError,
    ReceiptNotFoundError,
    ReceiptPermissionError,
    ReceiptValidationError,
    get_message_receipt_summary,
    mark_group_read_through,
    mark_messages_delivered,
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


class DeliveredReceiptView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def post(self, request) -> Response:
        serializer = DeliveredReceiptRequestSerializer(
            data=request.data,
        )

        if not serializer.is_valid():
            return _validation_error_response(serializer.errors)

        data = serializer.validated_data

        try:
            result = mark_messages_delivered(
                authenticated_user_id=str(request.user.user_id),
                device_id=data["device_id"],
                message_ids=data["message_ids"],
            )
        except ReceiptValidationError as error:
            return _service_error_response(
                error,
                status.HTTP_400_BAD_REQUEST,
            )
        except ReceiptPermissionError as error:
            return _service_error_response(
                error,
                status.HTTP_403_FORBIDDEN,
            )
        except ReceiptNotFoundError as error:
            return _service_error_response(
                error,
                status.HTTP_404_NOT_FOUND,
            )
        except ReceiptConflictError as error:
            return _service_error_response(
                error,
                status.HTTP_409_CONFLICT,
            )
        
        if result.updated_count > 0:
            schedule_message_delivered_receipts_publish(
                receipt_ids=result.changed_receipt_ids,
            )
        return Response(
            {
                "success": True,
                "message": "Delivered receipts stored successfully.",
                "data": {
                    "updated_count": result.updated_count,
                    "receipt_ids": result.receipt_ids,
                },
            },
            status=status.HTTP_200_OK,
        )


class ReadReceiptView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def post(self, request) -> Response:
        serializer = ReadReceiptRequestSerializer(
            data=request.data,
        )

        if not serializer.is_valid():
            return _validation_error_response(serializer.errors)

        data = serializer.validated_data

        try:
            result = mark_group_read_through(
                authenticated_user_id=str(request.user.user_id),
                device_id=data["device_id"],
                group_id=data["group_id"],
                read_through_message_id=data["read_through_message_id"],
            )
        except ReceiptValidationError as error:
            return _service_error_response(
                error,
                status.HTTP_400_BAD_REQUEST,
            )
        except ReceiptPermissionError as error:
            return _service_error_response(
                error,
                status.HTTP_403_FORBIDDEN,
            )
        except ReceiptNotFoundError as error:
            return _service_error_response(
                error,
                status.HTTP_404_NOT_FOUND,
            )
        except ReceiptConflictError as error:
            return _service_error_response(
                error,
                status.HTTP_409_CONFLICT,
            )
        

        if result.updated_count > 0:
            schedule_message_read_receipts_publish(
                receipt_ids=result.changed_receipt_ids,
            )
        return Response(
            {
                "success": True,
                "message": "Read receipts stored successfully.",
                "data": {
                    "updated_count": result.updated_count,
                    "receipt_ids": result.receipt_ids,
                },
            },
            status=status.HTTP_200_OK,
        )


class MessageReceiptSummaryView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def get(self, request, message_id) -> Response:
        try:
            result = get_message_receipt_summary(
                authenticated_user_id=str(request.user.user_id),
                message_id=message_id,
            )
        except ReceiptValidationError as error:
            return _service_error_response(
                error,
                status.HTTP_400_BAD_REQUEST,
            )
        except ReceiptPermissionError as error:
            return _service_error_response(
                error,
                status.HTTP_403_FORBIDDEN,
            )
        except ReceiptNotFoundError as error:
            return _service_error_response(
                error,
                status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {
                "success": True,
                "message": "Message receipts retrieved successfully.",
                "data": MessageReceiptSummarySerializer(result).data,
            },
            status=status.HTTP_200_OK,
        )
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .group_serializers import (
    GroupMessageEncryptionSerializer,
    GroupMessageSendSerializer,
)
from .group_services import (
    GroupMessageConflictError,
    GroupMessageNotFoundError,
    GroupMessagePermissionError,
    GroupMessageValidationError,
    send_encrypted_group_message,
)
from apps.realtime.publishers import (
    schedule_group_message_stored_publish,
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


class GroupMessageSendView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def post(self, request) -> Response:
        serializer = GroupMessageSendSerializer(
            data=request.data,
        )

        if not serializer.is_valid():
            return _validation_error_response(serializer.errors)

        data = serializer.validated_data

        try:
            result = send_encrypted_group_message(
                authenticated_user_id=str(request.user.user_id),
                group_id=data["group_id"],
                sender_device_id=data["sender_device_id"],
                client_message_id=data["client_message_id"],
                epoch_number=data["epoch_number"],
                sender_key_id=data["sender_key_id"],
                chain_iteration=data["chain_iteration"],
                message_type=data["message_type"],
                encrypted_payload=data["encrypted_payload"],
                encryption_metadata=data["encryption_metadata"],
                signature=data["signature"],
                reply_to_message_id=data.get("reply_to_message_id"),
                client_sent_at=data.get("client_sent_at"),
                recovery_envelopes=data.get("recovery_envelopes", []),
                attachment_ids=data.get("attachment_ids", []),
            )
        except GroupMessageValidationError as error:
            return _service_error_response(
                error,
                status.HTTP_400_BAD_REQUEST,
            )
        except GroupMessagePermissionError as error:
            return _service_error_response(
                error,
                status.HTTP_403_FORBIDDEN,
            )
        except GroupMessageNotFoundError as error:
            return _service_error_response(
                error,
                status.HTTP_404_NOT_FOUND,
            )
        except GroupMessageConflictError as error:
            return _service_error_response(
                error,
                status.HTTP_409_CONFLICT,
            )
        
        if result.message_created:
            schedule_group_message_stored_publish(
                message_id=result.encryption.message_id,
                sender_device_id=data["sender_device_id"],
            )

        return Response(
            {
                "success": True,
                "message": (
                    "Group message sent successfully."
                    if result.message_created
                    else "Group message already exists."
                ),
                "data": {
                    "message_created": result.message_created,
                    "message": GroupMessageEncryptionSerializer(
                        result.encryption,
                    ).data,
                },
            },
            status=(
                status.HTTP_201_CREATED
                if result.message_created
                else status.HTTP_200_OK
            ),
        )
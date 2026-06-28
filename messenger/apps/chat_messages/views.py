from rest_framework import status
from rest_framework.pagination import CursorPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.rooms.models import Room, RoomMember
from messenger_config.identity_client import (
    IdentityClientError,
    SavedContactForbiddenError,
    resolve_saved_contact_recipient,
)

from .recovery_send_services import (
    RecoveryEnvelopeConflictError,
    RecoveryEnvelopeValidationError,
    send_direct_message_with_recovery,
)
from .serializers import (
    EncryptedHistoryQuerySerializer,
    EncryptedMessageHistoryItemSerializer,
    RoomListItemSerializer,
    SendDirectMessageSerializer,
)
from .services import (
    DirectMessageValidationError,
    DirectRoomUnavailableError,
    IdempotencyConflictError,
    MessageHistoryAccessError,
    get_encrypted_message_history,
    list_user_rooms,
)


def validation_error_response(errors):
    return Response(
        {
            "success": False,
            "message": "Validation failed.",
            "errors": errors,
        },
        status=status.HTTP_400_BAD_REQUEST,
    )


def resolve_existing_direct_room_recipient(
    *,
    authenticated_user_id: str,
    room_id,
) -> str:
    room = Room.objects.filter(
        id=room_id,
        room_type=Room.RoomType.DIRECT,
        is_active=True,
    ).first()

    if room is None:
        raise DirectRoomUnavailableError(
            "Direct room is unavailable."
        )

    is_member = RoomMember.objects.filter(
        room=room,
        user_id=authenticated_user_id,
        is_active=True,
    ).exists()

    if not is_member:
        raise DirectRoomUnavailableError(
            "Direct room is unavailable."
        )

    recipient_member = (
        RoomMember.objects.filter(
            room=room,
            is_active=True,
        )
        .exclude(user_id=authenticated_user_id)
        .first()
    )

    if recipient_member is None:
        raise DirectRoomUnavailableError(
            "Direct room recipient is unavailable."
        )

    return str(recipient_member.user_id)


class SendDirectMessageView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def post(self, request) -> Response:
        serializer = SendDirectMessageSerializer(
            data=request.data,
        )

        if not serializer.is_valid():
            return validation_error_response(
                serializer.errors,
            )

        authenticated_user_id = str(
            request.user.user_id,
        )

        validated_data = dict(serializer.validated_data)

        recipient_contact_id = validated_data.pop(
            "recipient_contact_id",
            None,
        )

        room_id = validated_data.pop(
            "room_id",
            None,
        )

        authorization_header = request.META.get(
            "HTTP_AUTHORIZATION",
            "",
        )

        try:
            if room_id is not None:
                recipient_user_id = resolve_existing_direct_room_recipient(
                    authenticated_user_id=authenticated_user_id,
                    room_id=room_id,
                )
            else:
                resolved_recipient = resolve_saved_contact_recipient(
                    contact_id=recipient_contact_id,
                    authorization_header=authorization_header,
                )
                recipient_user_id = resolved_recipient.contact_user_id

            result = send_direct_message_with_recovery(
                sender_user_id=authenticated_user_id,
                recipient_user_id=recipient_user_id,
                **validated_data,
            )

        except SavedContactForbiddenError as error:
            return Response(
                {
                    "success": False,
                    "message": (
                        str(error)
                        or "You must save this contact before messaging."
                    ),
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        except IdentityClientError as error:
            return Response(
                {
                    "success": False,
                    "message": str(error),
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        except RecoveryEnvelopeValidationError as error:
            return Response(
                {
                    "success": False,
                    "message": str(error),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        except RecoveryEnvelopeConflictError as error:
            return Response(
                {
                    "success": False,
                    "message": str(error),
                },
                status=status.HTTP_409_CONFLICT,
            )

        except IdempotencyConflictError as error:
            return Response(
                {
                    "success": False,
                    "message": str(error),
                },
                status=status.HTTP_409_CONFLICT,
            )

        except DirectRoomUnavailableError as error:
            return Response(
                {
                    "success": False,
                    "message": str(error),
                },
                status=status.HTTP_409_CONFLICT,
            )

        except DirectMessageValidationError as error:
            return Response(
                {
                    "success": False,
                    "message": str(error),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        response_status = (
            status.HTTP_201_CREATED
            if result.message_created
            else status.HTTP_200_OK
        )

        response_message = (
            "Encrypted direct message stored successfully."
            if result.message_created
            else "Existing encrypted message returned."
        )

        return Response(
            {
                "success": True,
                "message": response_message,
                "data": {
                    "room_id": str(result.room.id),
                    "room_type": result.room.room_type,
                    "room_created": result.room_created,
                    "message_id": str(result.message.id),
                    "client_message_id": str(
                        result.message.client_message_id,
                    ),
                    "message_created": result.message_created,
                    "envelope_count": result.envelope_count,
                    "recovery_envelope_count": (
                        result.recovery_envelope_count
                    ),
                    "recipient_delivery_blocked": (
                        result.recipient_delivery_blocked
                    ),
                    "recipient_contact_id": recipient_contact_id,
                    "request_room_id": (
                        str(room_id)
                        if room_id is not None
                        else None
                    ),
                    "created_at": result.message.created_at,
                },
            },
            status=response_status,
        )


class EncryptedMessageCursorPagination(CursorPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 100
    ordering = "-created_at"


class RoomListView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def get(self, request) -> Response:
        rooms = list_user_rooms(
            authenticated_user_id=str(
                request.user.user_id,
            ),
        )

        serializer = RoomListItemSerializer(
            rooms,
            many=True,
        )

        return Response(
            {
                "success": True,
                "message": "Rooms retrieved successfully.",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class EncryptedMessageHistoryView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def get(self, request, room_id) -> Response:
        query_serializer = EncryptedHistoryQuerySerializer(
            data=request.query_params,
        )

        if not query_serializer.is_valid():
            return validation_error_response(
                query_serializer.errors,
            )

        try:
            history = get_encrypted_message_history(
                authenticated_user_id=str(
                    request.user.user_id,
                ),
                room_id=room_id,
                device_id=query_serializer.validated_data[
                    "device_id"
                ],
            )

        except MessageHistoryAccessError:
            return Response(
                {
                    "success": False,
                    "message": (
                        "Encrypted message history is unavailable "
                        "for this room and device."
                    ),
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        paginator = EncryptedMessageCursorPagination()

        page = paginator.paginate_queryset(
            history.messages,
            request,
            view=self,
        )

        serializer = EncryptedMessageHistoryItemSerializer(
            page,
            many=True,
        )

        return Response(
            {
                "success": True,
                "message": (
                    "Encrypted message history retrieved "
                    "successfully."
                ),
                "data": {
                    "room_id": str(history.room.id),
                    "room_type": history.room.room_type,
                    "device_id": str(history.device.id),
                    "next": paginator.get_next_link(),
                    "previous": paginator.get_previous_link(),
                    "messages": serializer.data,
                },
            },
            status=status.HTTP_200_OK,
        )
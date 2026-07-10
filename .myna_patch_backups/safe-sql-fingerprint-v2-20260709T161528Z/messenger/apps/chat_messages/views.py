import logging
import time

from django.db.utils import DatabaseError, OperationalError
from rest_framework import status
from rest_framework.pagination import CursorPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from messenger_config.benchmark_timing import (
    record_drf_authentication_entry,
    record_drf_authentication_exit,
    record_drf_content_negotiation_entry,
    record_drf_content_negotiation_exit,
    record_drf_dispatch_entry,
    record_drf_initial_entry,
    record_drf_initial_exit,
    record_drf_initialize_request_entry,
    record_drf_initialize_request_exit,
    record_drf_permission_entry,
    record_drf_permission_exit,
    record_drf_throttle_entry,
    record_drf_throttle_exit,
    record_drf_finalize_response_entry,
    record_drf_finalize_response_exit,
    record_drf_versioning_entry,
    record_drf_versioning_exit,
    record_direct_send_view_entry,
    record_direct_send_view_exit,
)
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
    direct_send_profile_enabled,
    IdempotencyConflictError,
    MessageHistoryAccessError,
    profile_checkpoint,
    profile_database_queries,
    profile_database_stage,
    resolve_existing_direct_room_recipient,
    SavedContactRequiredError,
    get_encrypted_message_history,
    list_user_rooms,
)

logger = logging.getLogger(__name__)


def validation_error_response(errors):
    return Response(
        {
            "success": False,
            "message": "Validation failed.",
            "errors": errors,
        },
        status=status.HTTP_400_BAD_REQUEST,
    )


class DirectSendPreViewTimingMixin:
    def dispatch(self, request, *args, **kwargs):
        record_drf_dispatch_entry()
        return super().dispatch(request, *args, **kwargs)

    def initialize_request(self, request, *args, **kwargs):
        record_drf_initialize_request_entry()
        try:
            return super().initialize_request(request, *args, **kwargs)
        finally:
            record_drf_initialize_request_exit()

    def initial(self, request, *args, **kwargs):
        record_drf_initial_entry()
        try:
            return super().initial(request, *args, **kwargs)
        finally:
            record_drf_initial_exit()

    def perform_content_negotiation(self, request, force=False):
        record_drf_content_negotiation_entry()
        try:
            return super().perform_content_negotiation(request, force=force)
        finally:
            record_drf_content_negotiation_exit()

    def determine_version(self, request, *args, **kwargs):
        record_drf_versioning_entry()
        try:
            return super().determine_version(request, *args, **kwargs)
        finally:
            record_drf_versioning_exit()

    def perform_authentication(self, request):
        record_drf_authentication_entry()
        try:
            return super().perform_authentication(request)
        finally:
            record_drf_authentication_exit()

    def check_permissions(self, request):
        record_drf_permission_entry()
        try:
            return super().check_permissions(request)
        finally:
            record_drf_permission_exit()

    def check_throttles(self, request):
        record_drf_throttle_entry()
        try:
            return super().check_throttles(request)
        finally:
            record_drf_throttle_exit()


    def finalize_response(self, request, response, *args, **kwargs):
        record_drf_finalize_response_entry()
        try:
            return super().finalize_response(
                request,
                response,
                *args,
                **kwargs,
            )
        finally:
            record_drf_finalize_response_exit()


class SendDirectMessageView(DirectSendPreViewTimingMixin, APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def post(self, request) -> Response:
        view_entry_ns = record_direct_send_view_entry()
        view_timings_ms = (
            {}
            if direct_send_profile_enabled()
            else None
        )
        phase_started_at = time.perf_counter()
        if view_timings_ms is not None:
            try:
                auth_jwt_ms = request.META.get(
                    "MYNA_PROFILE_AUTH_JWT_MS",
                )
                if auth_jwt_ms is not None:
                    view_timings_ms["auth_jwt_ms"] = float(auth_jwt_ms)
            except (TypeError, ValueError):
                pass

        serializer = SendDirectMessageSerializer(
            data=request.data,
        )

        if not serializer.is_valid():
            record_direct_send_view_exit()
            return validation_error_response(
                serializer.errors,
            )
        profile_checkpoint(
            view_timings_ms,
            "view_serializer_validation",
            phase_started_at,
        )

        phase_started_at = time.perf_counter()
        authenticated_user_id = str(
            request.user.user_id,
        )
        profile_checkpoint(
            view_timings_ms,
            "view_authenticated_user",
            phase_started_at,
        )

        phase_started_at = time.perf_counter()
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
        profile_checkpoint(
            view_timings_ms,
            "view_payload_prepare",
            phase_started_at,
        )

        try:
            sender_contact_validated_by_identity = False
            identity_contact_id = None
            existing_room = None

            with profile_database_queries(view_timings_ms):
                phase_started_at = time.perf_counter()

                with profile_database_stage("recipient_resolution"):
                    if room_id is not None:
                        existing_room, recipient_user_id = (
                            resolve_existing_direct_room_recipient(
                                authenticated_user_id=authenticated_user_id,
                                room_id=room_id,
                            )
                        )

                    else:
                        resolved_recipient = (
                            resolve_saved_contact_recipient(
                                contact_id=recipient_contact_id,
                                authorization_header=authorization_header,
                            )
                        )

                        recipient_user_id = (
                            resolved_recipient.contact_user_id
                        )
                        sender_contact_validated_by_identity = True
                        identity_contact_id = (
                            resolved_recipient.contact_id
                        )

                profile_checkpoint(
                    view_timings_ms,
                    "view_recipient_resolution",
                    phase_started_at,
                )

                phase_started_at = time.perf_counter()

                with profile_database_stage("service_call"):
                    result = send_direct_message_with_recovery(
                        sender_user_id=authenticated_user_id,
                        recipient_user_id=recipient_user_id,
                        sender_contact_validated_by_identity=(
                            sender_contact_validated_by_identity
                        ),
                        identity_contact_id=identity_contact_id,
                        existing_room=existing_room,
                        require_saved_contact=(
                            existing_room is not None
                        ),
                        profile_timings_ms=view_timings_ms,
                        **validated_data,
                    )

                profile_checkpoint(
                    view_timings_ms,
                    "view_service_call",
                    phase_started_at,
                )

            if (
                result.profile_timings_ms is not None
                and result.profile_timings_ms is not view_timings_ms
            ):
                result.profile_timings_ms.update(
                    view_timings_ms or {}
                )
            if (
                result.profile_timings_ms is not None
                and result.profile_timings_ms is not view_timings_ms
            ):
                result.profile_timings_ms.update(view_timings_ms or {})

        except (
            SavedContactForbiddenError,
            SavedContactRequiredError,
        ) as error:
            record_direct_send_view_exit()
            return Response(
                {
                    "success": False,
                    "message": (
                        str(error)
                        or "Save this contact before sending a message."
                    ),
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        except IdentityClientError as error:
            record_direct_send_view_exit()
            return Response(
                {
                    "success": False,
                    "message": str(error),
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        except RecoveryEnvelopeValidationError as error:
            record_direct_send_view_exit()
            return Response(
                {
                    "success": False,
                    "message": str(error),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        except RecoveryEnvelopeConflictError as error:
            record_direct_send_view_exit()
            return Response(
                {
                    "success": False,
                    "message": str(error),
                },
                status=status.HTTP_409_CONFLICT,
            )

        except IdempotencyConflictError as error:
            record_direct_send_view_exit()
            return Response(
                {
                    "success": False,
                    "message": str(error),
                },
                status=status.HTTP_409_CONFLICT,
            )

        except DirectRoomUnavailableError as error:
            record_direct_send_view_exit()
            return Response(
                {
                    "success": False,
                    "message": str(error),
                },
                status=status.HTTP_409_CONFLICT,
            )

        except DirectMessageValidationError as error:
            record_direct_send_view_exit()
            return Response(
                {
                    "success": False,
                    "message": str(error),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        except (OperationalError, DatabaseError):
            logger.exception(
                "Messenger database unavailable during direct message send.",
                extra={
                    "authenticated_user_id": getattr(request.user, "user_id", None),
                },
            )
            record_direct_send_view_exit()
            return Response(
                {
                    "success": False,
                    "message": "Messenger database is temporarily unavailable.",
                    "errors": {
                        "code": "database_temporarily_unavailable",
                    },
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
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

        phase_started_at = time.perf_counter()
        response_data = {
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
            "realtime_outbox_event_count": (
                result.realtime_outbox_event_count
            ),
            "recipient_contact_id": recipient_contact_id,
            "request_room_id": (
                str(room_id)
                if room_id is not None
                else None
            ),
            "created_at": result.message.created_at,
        }

        if result.profile_timings_ms is not None:
            profile_checkpoint(
                result.profile_timings_ms,
                "view_response_build",
                phase_started_at,
            )
            view_exit_ns = record_direct_send_view_exit()
            result.profile_timings_ms["view_total"] = round(
                (view_exit_ns - view_entry_ns) / 1_000_000,
                2,
            )
            response_data["server_timing_ms"] = (
                result.profile_timings_ms
            )
        else:
            record_direct_send_view_exit()

        return Response(
            {
                "success": True,
                "message": response_message,
                "data": response_data,
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

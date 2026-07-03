import secrets

from django.conf import settings
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .policy_serializers import (
    ContactDeliveryPolicySyncSerializer,
    DirectContactStateSyncSerializer,
)
from .policy_services import (
    ContactPolicyValidationError,
    sync_direct_contact_state_if_room_exists,
    upsert_contact_delivery_policy,
)

class ContactDeliveryPolicySyncView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request) -> Response:
        configured_secret = settings.CONTACT_POLICY_SYNC_SECRET
        provided_secret = request.headers.get(
            "X-Myna-Internal-Secret",
            "",
        )

        if (
            not configured_secret
            or not secrets.compare_digest(
                configured_secret,
                provided_secret,
            )
        ):
            return Response(
                {
                    "success": False,
                    "message": "Internal policy sync is unauthorized.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = ContactDeliveryPolicySyncSerializer(
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

        try:
            result = upsert_contact_delivery_policy(
                **serializer.validated_data,
            )
        except ContactPolicyValidationError as error:
            return Response(
                {
                    "success": False,
                    "message": str(error),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "success": True,
                "message": "Contact delivery policy synced.",
                "data": {
                    "policy_id": str(result.policy.id),

                    "owner_user_id": result.policy.owner_user_id,
                    "target_user_id": result.policy.target_user_id,

                    "policy_owner_user_id": result.policy.owner_user_id,
                    "restricted_user_id": result.policy.target_user_id,

                    "is_blocked": result.policy.is_blocked,
                    "ghost_until": (
                        result.policy.ghost_until.isoformat()
                        if result.policy.ghost_until
                        else None
                    ),
                    "ghost_permanent": result.policy.ghost_permanent,
                    "ghost_duration_option": (
                        result.policy.ghost_duration_option
                    ),

                    "policy_version": result.policy.policy_version,
                    "source_updated_at": (
                        result.policy.source_updated_at.isoformat()
                        if result.policy.source_updated_at
                        else None
                    ),
                    "synced_at": (
                        result.policy.synced_at.isoformat()
                        if result.policy.synced_at
                        else None
                    ),

                    "created": result.created,
                    "updated": result.updated,
                    "ignored_stale_update": (
                        result.ignored_stale_update
                    ),
                },
            },
            status=status.HTTP_200_OK,
        )
    

class DirectContactStateSyncView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request) -> Response:
        configured_secret = settings.CONTACT_POLICY_SYNC_SECRET
        provided_secret = request.headers.get(
            "X-Myna-Internal-Secret",
            "",
        )

        if (
            not configured_secret
            or not secrets.compare_digest(
                configured_secret,
                provided_secret,
            )
        ):
            return Response(
                {
                    "success": False,
                    "message": "Internal contact-state sync is unauthorized.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = DirectContactStateSyncSerializer(
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

        try:
            result = sync_direct_contact_state_if_room_exists(
                **serializer.validated_data,
            )
        except ContactPolicyValidationError as error:
            return Response(
                {
                    "success": False,
                    "message": str(error),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if result.ignored_no_room:
            return Response(
                {
                    "success": True,
                    "message": (
                        "No direct room exists. Contact state sync ignored."
                    ),
                    "data": {
                        "contact_state_id": None,
                        "room_id": None,
                        "created": False,
                        "updated": False,
                        "ignored_no_room": True,
                        "ignored_stale_update": False,
                    },
                },
                status=status.HTTP_200_OK,
            )

        contact_state = result.contact_state

        return Response(
            {
                "success": True,
                "message": "Direct contact state synced.",
                "data": {
                    "contact_state_id": str(contact_state.id),
                    "room_id": str(contact_state.room_id),
                    "owner_user_id": contact_state.owner_user_id,
                    "contact_user_id": contact_state.contact_user_id,
                    "identity_contact_id": (
                        contact_state.identity_contact_id
                    ),
                    "is_saved": contact_state.is_saved,
                    "source_updated_at": (
                        contact_state.source_updated_at.isoformat()
                        if contact_state.source_updated_at
                        else None
                    ),
                    "synced_at": (
                        contact_state.synced_at.isoformat()
                        if contact_state.synced_at
                        else None
                    ),
                    "created": result.created,
                    "updated": result.updated,
                    "ignored_no_room": result.ignored_no_room,
                    "ignored_stale_update": (
                        result.ignored_stale_update
                    ),
                },
            },
            status=status.HTTP_200_OK,
        )
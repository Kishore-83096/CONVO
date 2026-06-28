from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import RecoveryBundle
from .recovery_public_key_serializers import (
    RecoveryPublicKeyResolveSerializer,
)


class RecoveryPublicKeyResolveView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def post(self, request):
        serializer = RecoveryPublicKeyResolveSerializer(
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

        requested_user_ids = (
            serializer.validated_data["user_ids"]
        )

        bundles = (
            RecoveryBundle.objects.filter(
                user_id__in=requested_user_ids,
                is_active=True,
                disabled_at__isnull=True,
            )
            .only(
                "user_id",
                "recovery_public_key",
                "recovery_version",
                "updated_at",
            )
            .order_by("user_id")
        )

        public_keys = [
            {
                "user_id": bundle.user_id,
                "recovery_public_key": (
                    bundle.recovery_public_key
                ),
                "recovery_version": (
                    bundle.recovery_version
                ),
                "updated_at": bundle.updated_at,
            }
            for bundle in bundles
        ]

        return Response(
            {
                "success": True,
                "message": (
                    "Recovery public keys resolved "
                    "successfully."
                ),
                "data": {
                    "public_keys": public_keys,
                },
            },
            status=status.HTTP_200_OK,
        )

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .recovery_coverage_services import (
    RecoveryCoverageUnavailableError,
    get_recovery_coverage,
)
from .recovery_views import get_authenticated_user_id


class RecoveryCoverageView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def get(self, request):
        user_id = get_authenticated_user_id(request)

        try:
            result = get_recovery_coverage(
                user_id=user_id,
            )
        except RecoveryCoverageUnavailableError as error:
            return Response(
                {
                    "success": False,
                    "message": str(error),
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        return Response(
            {
                "success": True,
                "message": (
                    "Recovery coverage retrieved "
                    "successfully."
                ),
                "data": {
                    "recovery_version": (
                        result.bundle.recovery_version
                    ),
                    "total_eligible_messages": (
                        result.total_eligible_messages
                    ),
                    "current_version_covered_messages": (
                        result
                        .current_version_covered_messages
                    ),
                    "missing_recovery_envelopes": (
                        result.missing_recovery_envelopes
                    ),
                    "stale_recovery_envelopes": (
                        result.stale_recovery_envelopes
                    ),
                    "coverage_percent": (
                        result.coverage_percent
                    ),
                    "is_complete": result.is_complete,
                    "active_devices": [
                        {
                            "device_id": str(device.id),
                            "device_name": (
                                device.device_name
                            ),
                            "platform": device.platform,
                            "backfill_candidate_count": (
                                device
                                .backfill_candidate_count
                            ),
                        }
                        for device in (
                            result.active_devices
                        )
                    ],
                },
            },
            status=status.HTTP_200_OK,
        )

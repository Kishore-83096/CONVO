from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import (
    DeviceRegistrationSerializer,
    OneTimePreKeyUploadSerializer,
    PreKeyBundleClaimSerializer,
)
from .services import (
    DeviceIdentityConflictError,
    DeviceNotFoundError,
    DeviceOwnershipError,
    E2EEDeviceValidationError,
    NoActiveRecipientDevicesError,
    PreKeyConflictError,
    claim_recipient_prekey_bundles,
    register_device,
    upload_one_time_prekeys,
)
from messenger_config.identity_client import (
    IdentityClientError,
    SavedContactForbiddenError,
    resolve_saved_contact_recipient,
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


class DeviceRegistrationView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def post(self, request) -> Response:
        serializer = DeviceRegistrationSerializer(
            data=request.data
        )

        if not serializer.is_valid():
            return validation_error_response(
                serializer.errors
            )

        try:
            result = register_device(
                authenticated_user_id=(
                    request.user.user_id
                ),
                validated_data=serializer.validated_data,
            )

        except DeviceOwnershipError as error:
            return Response(
                {
                    "success": False,
                    "message": str(error),
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        except (
            DeviceIdentityConflictError,
            PreKeyConflictError,
        ) as error:
            return Response(
                {
                    "success": False,
                    "message": str(error),
                },
                status=status.HTTP_409_CONFLICT,
            )

        except E2EEDeviceValidationError as error:
            return Response(
                {
                    "success": False,
                    "message": str(error),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        response_status = (
            status.HTTP_201_CREATED
            if result.device_created
            else status.HTTP_200_OK
        )

        return Response(
            {
                "success": True,
                "message": (
                    "Device registered successfully."
                    if result.device_created
                    else "Device registration updated."
                ),
                "data": {
                    "device_id": str(result.device.id),
                    "user_id": result.device.user_id,
                    "device_created": (
                        result.device_created
                    ),
                    "prekeys_created": (
                        result.prekeys_created
                    ),
                    "prekeys_unchanged": (
                        result.prekeys_unchanged
                    ),
                },
            },
            status=response_status,
        )


class OneTimePreKeyUploadView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def post(
        self,
        request,
        device_id,
    ) -> Response:
        serializer = OneTimePreKeyUploadSerializer(
            data=request.data
        )

        if not serializer.is_valid():
            return validation_error_response(
                serializer.errors
            )

        try:
            result = upload_one_time_prekeys(
                authenticated_user_id=(
                    request.user.user_id
                ),
                device_id=device_id,
                prekeys=serializer.validated_data[
                    "one_time_prekeys"
                ],
            )

        except DeviceNotFoundError as error:
            return Response(
                {
                    "success": False,
                    "message": str(error),
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        except DeviceOwnershipError as error:
            return Response(
                {
                    "success": False,
                    "message": str(error),
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        except PreKeyConflictError as error:
            return Response(
                {
                    "success": False,
                    "message": str(error),
                },
                status=status.HTTP_409_CONFLICT,
            )

        except E2EEDeviceValidationError as error:
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
                "message": (
                    "One-time prekeys uploaded successfully."
                ),
                "data": {
                    "device_id": str(result.device.id),
                    "prekeys_created": (
                        result.prekeys_created
                    ),
                    "prekeys_unchanged": (
                        result.prekeys_unchanged
                    ),
                },
            },
            status=status.HTTP_200_OK,
        )


class PreKeyBundleClaimView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def post(self, request) -> Response:
        serializer = PreKeyBundleClaimSerializer(
            data=request.data
        )

        if not serializer.is_valid():
            return validation_error_response(
                serializer.errors
            )

        recipient_contact_id = serializer.validated_data[
            "recipient_contact_id"
        ]

        authorization_header = request.META.get(
            "HTTP_AUTHORIZATION",
                "",
        )

        try:
            resolved_recipient = resolve_saved_contact_recipient(
                contact_id=recipient_contact_id,
                authorization_header=authorization_header,
            )

            bundles = claim_recipient_prekey_bundles(
                authenticated_user_id=request.user.user_id,
                recipient_user_id=resolved_recipient.contact_user_id,
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
        except NoActiveRecipientDevicesError as error:
            return Response(
                {
                    "success": False,
                    "message": str(error),
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        except E2EEDeviceValidationError as error:
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
                "message": (
                    "Recipient prekey bundles claimed."
                ),
                "data": {
                    "recipient_contact_id": recipient_contact_id,
                    "recipient_user_id": resolved_recipient.contact_user_id,
                    "device_count": len(bundles),
                    "devices": bundles,
                },
            },
            status=status.HTTP_200_OK,
        )
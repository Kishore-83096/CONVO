from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..serializers.sender_keys import (
    AcknowledgeSenderKeyDistributionsSerializer,
    GroupDeviceRosterItemSerializer,
    GroupSenderKeyDistributionSerializer,
    GroupSenderKeySerializer,
    RegisterGroupSenderKeySerializer,
    StoreSenderKeyDistributionsSerializer,
)
from ..services.distributions import (
    GroupSenderKeyDistributionConflictError,
    GroupSenderKeyDistributionNotFoundError,
    GroupSenderKeyDistributionPermissionError,
    GroupSenderKeyDistributionValidationError,
    acknowledge_sender_key_distributions,
    get_pending_sender_key_distributions,
    list_group_device_roster,
    list_sender_key_distribution_inbox,
    store_sender_key_distributions,
)
from ..services.sender_keys import (
    GroupSenderKeyConflictError,
    GroupSenderKeyNotFoundError,
    GroupSenderKeyPermissionError,
    GroupSenderKeyValidationError,
    get_my_group_sender_key,
    register_group_sender_key,
    revoke_group_sender_key,
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


class GroupSenderKeyRegisterView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def post(self, request, group_id) -> Response:
        serializer = RegisterGroupSenderKeySerializer(
            data=request.data,
        )

        if not serializer.is_valid():
            return _validation_error_response(serializer.errors)

        data = serializer.validated_data

        try:
            result = register_group_sender_key(
                authenticated_user_id=str(request.user.user_id),
                group_id=group_id,
                sender_device_id=data["sender_device_id"],
                epoch_number=data["epoch_number"],
                sender_key_id=data["sender_key_id"],
                signing_public_key=data["signing_public_key"],
                key_algorithm=data["key_algorithm"],
                signing_algorithm=data["signing_algorithm"],
                key_version=data["key_version"],
            )
        except GroupSenderKeyValidationError as error:
            return _service_error_response(
                error,
                status.HTTP_400_BAD_REQUEST,
            )
        except GroupSenderKeyPermissionError as error:
            return _service_error_response(
                error,
                status.HTTP_403_FORBIDDEN,
            )
        except GroupSenderKeyNotFoundError as error:
            return _service_error_response(
                error,
                status.HTTP_404_NOT_FOUND,
            )
        except GroupSenderKeyConflictError as error:
            return _service_error_response(
                error,
                status.HTTP_409_CONFLICT,
            )

        response_status = (
            status.HTTP_201_CREATED
            if result.created
            else status.HTTP_200_OK
        )

        return Response(
            {
                "success": True,
                "message": (
                    "Group sender key registered successfully."
                    if result.created
                    else "Group sender key registration already exists."
                ),
                "data": GroupSenderKeySerializer(
                    result.sender_key
                ).data,
            },
            status=response_status,
        )


class MyGroupSenderKeyView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def get(self, request, group_id) -> Response:
        device_id = request.query_params.get("device_id")

        if not device_id:
            return _validation_error_response(
                {
                    "device_id": [
                        "This query parameter is required."
                    ]
                }
            )

        try:
            sender_key = get_my_group_sender_key(
                authenticated_user_id=str(request.user.user_id),
                group_id=group_id,
                sender_device_id=device_id,
            )
        except GroupSenderKeyValidationError as error:
            return _service_error_response(
                error,
                status.HTTP_400_BAD_REQUEST,
            )
        except GroupSenderKeyPermissionError as error:
            return _service_error_response(
                error,
                status.HTTP_403_FORBIDDEN,
            )
        except GroupSenderKeyNotFoundError as error:
            return _service_error_response(
                error,
                status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {
                "success": True,
                "message": "Group sender key lookup completed.",
                "data": (
                    GroupSenderKeySerializer(sender_key).data
                    if sender_key is not None
                    else None
                ),
            },
            status=status.HTTP_200_OK,
        )


class GroupSenderKeyRevokeView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def delete(self, request, group_id, sender_key_id) -> Response:
        try:
            sender_key = revoke_group_sender_key(
                authenticated_user_id=str(request.user.user_id),
                group_id=group_id,
                sender_key_id=sender_key_id,
            )
        except GroupSenderKeyValidationError as error:
            return _service_error_response(
                error,
                status.HTTP_400_BAD_REQUEST,
            )
        except GroupSenderKeyPermissionError as error:
            return _service_error_response(
                error,
                status.HTTP_403_FORBIDDEN,
            )
        except GroupSenderKeyNotFoundError as error:
            return _service_error_response(
                error,
                status.HTTP_404_NOT_FOUND,
            )
        except GroupSenderKeyConflictError as error:
            return _service_error_response(
                error,
                status.HTTP_409_CONFLICT,
            )

        return Response(
            {
                "success": True,
                "message": "Group sender key revoked successfully.",
                "data": GroupSenderKeySerializer(sender_key).data,
            },
            status=status.HTTP_200_OK,
        )


class GroupDeviceRosterView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def get(self, request, group_id) -> Response:
        epoch_number = request.query_params.get("epoch_number")

        if not epoch_number:
            return _validation_error_response(
                {
                    "epoch_number": [
                        "This query parameter is required."
                    ]
                }
            )

        try:
            roster = list_group_device_roster(
                authenticated_user_id=str(request.user.user_id),
                group_id=group_id,
                epoch_number=int(epoch_number),
            )
        except ValueError as error:
            return _service_error_response(
                error,
                status.HTTP_400_BAD_REQUEST,
            )
        except GroupSenderKeyDistributionValidationError as error:
            return _service_error_response(
                error,
                status.HTTP_400_BAD_REQUEST,
            )
        except GroupSenderKeyDistributionNotFoundError as error:
            return _service_error_response(
                error,
                status.HTTP_404_NOT_FOUND,
            )
        except GroupSenderKeyDistributionConflictError as error:
            return _service_error_response(
                error,
                status.HTTP_409_CONFLICT,
            )

        return Response(
            {
                "success": True,
                "message": "Group device roster retrieved successfully.",
                "data": GroupDeviceRosterItemSerializer(
                    roster,
                    many=True,
                ).data,
            },
            status=status.HTTP_200_OK,
        )


class GroupSenderKeyDistributionStoreView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def post(self, request, group_id, sender_key_id) -> Response:
        serializer = StoreSenderKeyDistributionsSerializer(
            data=request.data,
        )

        if not serializer.is_valid():
            return _validation_error_response(serializer.errors)

        data = serializer.validated_data

        try:
            result = store_sender_key_distributions(
                authenticated_user_id=str(request.user.user_id),
                group_id=group_id,
                sender_key_id=sender_key_id,
                epoch_number=data["epoch_number"],
                distributions=data["distributions"],
            )
        except GroupSenderKeyDistributionValidationError as error:
            return _service_error_response(
                error,
                status.HTTP_400_BAD_REQUEST,
            )
        except GroupSenderKeyDistributionPermissionError as error:
            return _service_error_response(
                error,
                status.HTTP_403_FORBIDDEN,
            )
        except GroupSenderKeyDistributionNotFoundError as error:
            return _service_error_response(
                error,
                status.HTTP_404_NOT_FOUND,
            )
        except GroupSenderKeyDistributionConflictError as error:
            return _service_error_response(
                error,
                status.HTTP_409_CONFLICT,
            )

        return Response(
            {
                "success": True,
                "message": "Group sender-key distributions stored.",
                "data": {
                    "created_count": result.created_count,
                    "existing_count": result.existing_count,
                    "missing_required_device_ids": (
                        result.missing_required_device_ids
                    ),
                    "is_send_ready": (
                        len(result.missing_required_device_ids) == 0
                    ),
                    "distributions": (
                        GroupSenderKeyDistributionSerializer(
                            result.stored_distributions,
                            many=True,
                        ).data
                    ),
                },
            },
            status=status.HTTP_201_CREATED,
        )


class GroupSenderKeyPendingView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def get(self, request, group_id, sender_key_id) -> Response:
        try:
            result = get_pending_sender_key_distributions(
                authenticated_user_id=str(request.user.user_id),
                group_id=group_id,
                sender_key_id=sender_key_id,
            )
        except GroupSenderKeyDistributionValidationError as error:
            return _service_error_response(
                error,
                status.HTTP_400_BAD_REQUEST,
            )
        except GroupSenderKeyDistributionPermissionError as error:
            return _service_error_response(
                error,
                status.HTTP_403_FORBIDDEN,
            )
        except GroupSenderKeyDistributionNotFoundError as error:
            return _service_error_response(
                error,
                status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {
                "success": True,
                "message": "Group sender-key distribution coverage retrieved.",
                "data": {
                    "sender_key_id": str(result.sender_key.sender_key_id),
                    "epoch_number": result.sender_key.epoch.epoch_number,
                    "required_device_count": result.required_device_count,
                    "covered_device_count": result.covered_device_count,
                    "pending_device_count": len(result.pending_devices),
                    "is_send_ready": result.is_send_ready,
                    "pending_devices": GroupDeviceRosterItemSerializer(
                        result.pending_devices,
                        many=True,
                    ).data,
                },
            },
            status=status.HTTP_200_OK,
        )


class GroupSenderKeyDistributionInboxView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def get(self, request, group_id) -> Response:
        device_id = request.query_params.get("device_id")

        if not device_id:
            return _validation_error_response(
                {
                    "device_id": [
                        "This query parameter is required."
                    ]
                }
            )

        try:
            distributions = list_sender_key_distribution_inbox(
                authenticated_user_id=str(request.user.user_id),
                group_id=group_id,
                device_id=device_id,
            )
        except GroupSenderKeyDistributionValidationError as error:
            return _service_error_response(
                error,
                status.HTTP_400_BAD_REQUEST,
            )
        except GroupSenderKeyDistributionPermissionError as error:
            return _service_error_response(
                error,
                status.HTTP_403_FORBIDDEN,
            )
        except GroupSenderKeyDistributionNotFoundError as error:
            return _service_error_response(
                error,
                status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {
                "success": True,
                "message": "Sender-key distribution inbox retrieved.",
                "data": GroupSenderKeyDistributionSerializer(
                    distributions,
                    many=True,
                ).data,
            },
            status=status.HTTP_200_OK,
        )


class GroupSenderKeyDistributionAcknowledgeView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def post(self, request, group_id) -> Response:
        serializer = AcknowledgeSenderKeyDistributionsSerializer(
            data=request.data,
        )

        if not serializer.is_valid():
            return _validation_error_response(serializer.errors)

        try:
            distributions = acknowledge_sender_key_distributions(
                authenticated_user_id=str(request.user.user_id),
                group_id=group_id,
                device_id=serializer.validated_data["device_id"],
                distribution_ids=serializer.validated_data[
                    "distribution_ids"
                ],
            )
        except GroupSenderKeyDistributionValidationError as error:
            return _service_error_response(
                error,
                status.HTTP_400_BAD_REQUEST,
            )
        except GroupSenderKeyDistributionPermissionError as error:
            return _service_error_response(
                error,
                status.HTTP_403_FORBIDDEN,
            )
        except GroupSenderKeyDistributionNotFoundError as error:
            return _service_error_response(
                error,
                status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {
                "success": True,
                "message": "Sender-key distributions acknowledged.",
                "data": GroupSenderKeyDistributionSerializer(
                    distributions,
                    many=True,
                ).data,
            },
            status=status.HTTP_200_OK,
        )
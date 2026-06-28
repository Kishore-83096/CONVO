from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..serializers.groups import (
    GroupCreateSerializer,
    GroupListItemSerializer,
    GroupProfileSerializer,
    GroupUpdateSerializer,
)
from ..services.groups import (
    GroupChatValidationError,
    GroupConflictError,
    GroupNotFoundError,
    GroupPermissionError,
    create_group,
    get_group_detail,
    list_groups_for_user,
    update_group,
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


def _authorization_header(request) -> str:
    return request.META.get(
        "HTTP_AUTHORIZATION",
        "",
    )


def _service_error_response(error, response_status):
    return Response(
        {
            "success": False,
            "message": str(error),
        },
        status=response_status,
    )


class GroupListCreateView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def get(self, request) -> Response:
        groups = list_groups_for_user(
            authenticated_user_id=str(request.user.user_id),
        )

        serializer = GroupListItemSerializer(
            groups,
            many=True,
        )

        return Response(
            {
                "success": True,
                "message": "Groups retrieved successfully.",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request) -> Response:
        serializer = GroupCreateSerializer(
            data=request.data,
        )

        if not serializer.is_valid():
            return validation_error_response(serializer.errors)

        try:
            result = create_group(
                authenticated_user_id=str(request.user.user_id),
                authorization_header=_authorization_header(request),
                **serializer.validated_data,
            )
        except GroupChatValidationError as error:
            return _service_error_response(
                error,
                status.HTTP_400_BAD_REQUEST,
            )
        except GroupConflictError as error:
            return _service_error_response(
                error,
                status.HTTP_409_CONFLICT,
            )

        serializer = GroupProfileSerializer(result)

        return Response(
            {
                "success": True,
                "message": "Group created successfully.",
                "data": serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )


class GroupDetailUpdateView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def get(self, request, group_id) -> Response:
        try:
            group = get_group_detail(
                authenticated_user_id=str(request.user.user_id),
                group_id=group_id,
            )
        except GroupNotFoundError as error:
            return _service_error_response(
                error,
                status.HTTP_404_NOT_FOUND,
            )

        serializer = GroupProfileSerializer(group)

        return Response(
            {
                "success": True,
                "message": "Group retrieved successfully.",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    def patch(self, request, group_id) -> Response:
        serializer = GroupUpdateSerializer(
            data=request.data,
            partial=True,
        )

        if not serializer.is_valid():
            return validation_error_response(serializer.errors)

        try:
            result = update_group(
                authenticated_user_id=str(request.user.user_id),
                group_id=group_id,
                validated_data=serializer.validated_data,
            )
        except GroupChatValidationError as error:
            return _service_error_response(
                error,
                status.HTTP_400_BAD_REQUEST,
            )
        except GroupPermissionError as error:
            return _service_error_response(
                error,
                status.HTTP_403_FORBIDDEN,
            )
        except GroupNotFoundError as error:
            return _service_error_response(
                error,
                status.HTTP_404_NOT_FOUND,
            )
        except GroupConflictError as error:
            return _service_error_response(
                error,
                status.HTTP_409_CONFLICT,
            )

        serializer = GroupProfileSerializer(result)

        return Response(
            {
                "success": True,
                "message": "Group updated successfully.",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )
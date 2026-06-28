from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..serializers.memberships import (
    AddGroupMembersSerializer,
    ChangeGroupMemberRoleSerializer,
    GroupMemberSerializer,
    TransferOwnershipSerializer,
)
from ..services.memberships import (
    GroupMembershipConflictError,
    GroupMembershipNotFoundError,
    GroupMembershipPermissionError,
    GroupMembershipValidationError,
    add_group_members,
    ban_group_member,
    change_group_member_role,
    leave_group,
    list_group_members,
    remove_group_member,
    transfer_ownership,
    unban_group_member,
)


def _authorization_header(request) -> str:
    return request.META.get(
        "HTTP_AUTHORIZATION",
        "",
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


class GroupMemberListCreateView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def get(self, request, group_id) -> Response:
        try:
            members = list_group_members(
                authenticated_user_id=str(request.user.user_id),
                group_id=group_id,
            )
        except GroupMembershipNotFoundError as error:
            return _service_error_response(
                error,
                status.HTTP_404_NOT_FOUND,
            )
        except GroupMembershipValidationError as error:
            return _service_error_response(
                error,
                status.HTTP_400_BAD_REQUEST,
            )

        serializer = GroupMemberSerializer(
            members,
            many=True,
        )

        return Response(
            {
                "success": True,
                "message": "Group members retrieved successfully.",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request, group_id) -> Response:
        serializer = AddGroupMembersSerializer(
            data=request.data,
        )

        if not serializer.is_valid():
            return _validation_error_response(serializer.errors)

        try:
            members = add_group_members(
                authenticated_user_id=str(request.user.user_id),
                group_id=group_id,
                member_user_ids=serializer.validated_data["member_user_ids"],
                authorization_header=_authorization_header(request),
            )
        except GroupMembershipValidationError as error:
            return _service_error_response(
                error,
                status.HTTP_400_BAD_REQUEST,
            )
        except GroupMembershipPermissionError as error:
            return _service_error_response(
                error,
                status.HTTP_403_FORBIDDEN,
            )
        except GroupMembershipNotFoundError as error:
            return _service_error_response(
                error,
                status.HTTP_404_NOT_FOUND,
            )
        except GroupMembershipConflictError as error:
            return _service_error_response(
                error,
                status.HTTP_409_CONFLICT,
            )

        serializer = GroupMemberSerializer(
            members,
            many=True,
        )

        return Response(
            {
                "success": True,
                "message": "Group members added successfully.",
                "data": serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )


class GroupMemberRemoveView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def delete(self, request, group_id, user_id) -> Response:
        try:
            member = remove_group_member(
                authenticated_user_id=str(request.user.user_id),
                group_id=group_id,
                target_user_id=user_id,
            )
        except GroupMembershipValidationError as error:
            return _service_error_response(
                error,
                status.HTTP_400_BAD_REQUEST,
            )
        except GroupMembershipPermissionError as error:
            return _service_error_response(
                error,
                status.HTTP_403_FORBIDDEN,
            )
        except GroupMembershipNotFoundError as error:
            return _service_error_response(
                error,
                status.HTTP_404_NOT_FOUND,
            )
        except GroupMembershipConflictError as error:
            return _service_error_response(
                error,
                status.HTTP_409_CONFLICT,
            )

        serializer = GroupMemberSerializer(member)

        return Response(
            {
                "success": True,
                "message": "Group member removed successfully.",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class GroupMemberRoleView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def patch(self, request, group_id, user_id) -> Response:
        serializer = ChangeGroupMemberRoleSerializer(
            data=request.data,
        )

        if not serializer.is_valid():
            return _validation_error_response(serializer.errors)

        try:
            member = change_group_member_role(
                authenticated_user_id=str(request.user.user_id),
                group_id=group_id,
                target_user_id=user_id,
                role=serializer.validated_data["role"],
            )
        except GroupMembershipValidationError as error:
            return _service_error_response(
                error,
                status.HTTP_400_BAD_REQUEST,
            )
        except GroupMembershipPermissionError as error:
            return _service_error_response(
                error,
                status.HTTP_403_FORBIDDEN,
            )
        except GroupMembershipNotFoundError as error:
            return _service_error_response(
                error,
                status.HTTP_404_NOT_FOUND,
            )

        serializer = GroupMemberSerializer(member)

        return Response(
            {
                "success": True,
                "message": "Group member role updated successfully.",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class GroupLeaveView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def post(self, request, group_id) -> Response:
        try:
            member = leave_group(
                authenticated_user_id=str(request.user.user_id),
                group_id=group_id,
            )
        except GroupMembershipValidationError as error:
            return _service_error_response(
                error,
                status.HTTP_400_BAD_REQUEST,
            )
        except GroupMembershipPermissionError as error:
            return _service_error_response(
                error,
                status.HTTP_403_FORBIDDEN,
            )
        except GroupMembershipNotFoundError as error:
            return _service_error_response(
                error,
                status.HTTP_404_NOT_FOUND,
            )

        serializer = GroupMemberSerializer(member)

        return Response(
            {
                "success": True,
                "message": "Left group successfully.",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class GroupOwnershipTransferView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def post(self, request, group_id) -> Response:
        serializer = TransferOwnershipSerializer(
            data=request.data,
        )

        if not serializer.is_valid():
            return _validation_error_response(serializer.errors)

        try:
            result = transfer_ownership(
                authenticated_user_id=str(request.user.user_id),
                group_id=group_id,
                new_owner_user_id=serializer.validated_data[
                    "new_owner_user_id"
                ],
            )
        except GroupMembershipValidationError as error:
            return _service_error_response(
                error,
                status.HTTP_400_BAD_REQUEST,
            )
        except GroupMembershipPermissionError as error:
            return _service_error_response(
                error,
                status.HTTP_403_FORBIDDEN,
            )
        except GroupMembershipNotFoundError as error:
            return _service_error_response(
                error,
                status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {
                "success": True,
                "message": "Group ownership transferred successfully.",
                "data": {
                    "old_owner": GroupMemberSerializer(
                        result["old_owner"]
                    ).data,
                    "new_owner": GroupMemberSerializer(
                        result["new_owner"]
                    ).data,
                },
            },
            status=status.HTTP_200_OK,
        )


class GroupMemberBanView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def post(self, request, group_id, user_id) -> Response:
        try:
            member = ban_group_member(
                authenticated_user_id=str(request.user.user_id),
                group_id=group_id,
                target_user_id=user_id,
            )
        except GroupMembershipValidationError as error:
            return _service_error_response(
                error,
                status.HTTP_400_BAD_REQUEST,
            )
        except GroupMembershipPermissionError as error:
            return _service_error_response(
                error,
                status.HTTP_403_FORBIDDEN,
            )
        except GroupMembershipNotFoundError as error:
            return _service_error_response(
                error,
                status.HTTP_404_NOT_FOUND,
            )
        except GroupMembershipConflictError as error:
            return _service_error_response(
                error,
                status.HTTP_409_CONFLICT,
            )

        serializer = GroupMemberSerializer(member)

        return Response(
            {
                "success": True,
                "message": "Group member banned successfully.",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class GroupMemberUnbanView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def post(self, request, group_id, user_id) -> Response:
        try:
            member = unban_group_member(
                authenticated_user_id=str(request.user.user_id),
                group_id=group_id,
                target_user_id=user_id,
            )
        except GroupMembershipValidationError as error:
            return _service_error_response(
                error,
                status.HTTP_400_BAD_REQUEST,
            )
        except GroupMembershipPermissionError as error:
            return _service_error_response(
                error,
                status.HTTP_403_FORBIDDEN,
            )
        except GroupMembershipNotFoundError as error:
            return _service_error_response(
                error,
                status.HTTP_404_NOT_FOUND,
            )

        serializer = GroupMemberSerializer(member)

        return Response(
            {
                "success": True,
                "message": "Group member unbanned successfully.",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )
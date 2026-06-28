from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .attachment_serializers import (
    EncryptedAttachmentCompleteSerializer,
    EncryptedAttachmentDeleteSerializer,
    EncryptedAttachmentInitiateSerializer,
    EncryptedAttachmentSerializer,
)
from .attachment_services import (
    AttachmentConflictError,
    AttachmentNotFoundError,
    AttachmentPermissionError,
    AttachmentValidationError,
    complete_encrypted_attachment,
    delete_encrypted_attachment,
    get_encrypted_attachment_download,
    initiate_encrypted_attachment,
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


class EncryptedAttachmentInitiateView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def post(self, request) -> Response:
        serializer = EncryptedAttachmentInitiateSerializer(
            data=request.data,
        )

        if not serializer.is_valid():
            return _validation_error_response(serializer.errors)

        data = serializer.validated_data

        try:
            attachment = initiate_encrypted_attachment(
                authenticated_user_id=str(request.user.user_id),
                device_id=data["device_id"],
                storage_provider=data.get("storage_provider", "cloudinary"),
                storage_key=data.get("storage_key", ""),
                media_category=data.get("media_category", "file"),
                expires_at=data.get("expires_at"),
            )
        except AttachmentValidationError as error:
            return _service_error_response(
                error,
                status.HTTP_400_BAD_REQUEST,
            )
        except AttachmentPermissionError as error:
            return _service_error_response(
                error,
                status.HTTP_403_FORBIDDEN,
            )
        except AttachmentNotFoundError as error:
            return _service_error_response(
                error,
                status.HTTP_404_NOT_FOUND,
            )
        except AttachmentConflictError as error:
            return _service_error_response(
                error,
                status.HTTP_409_CONFLICT,
            )

        return Response(
            {
                "success": True,
                "message": "Encrypted attachment initiated successfully.",
                "data": EncryptedAttachmentSerializer(attachment).data,
            },
            status=status.HTTP_201_CREATED,
        )


class EncryptedAttachmentCompleteView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def post(self, request, attachment_id) -> Response:
        serializer = EncryptedAttachmentCompleteSerializer(
            data=request.data,
        )

        if not serializer.is_valid():
            return _validation_error_response(serializer.errors)

        data = serializer.validated_data

        try:
            attachment = complete_encrypted_attachment(
                authenticated_user_id=str(request.user.user_id),
                attachment_id=attachment_id,
                device_id=data["device_id"],
                ciphertext_sha256=data["ciphertext_sha256"],
                ciphertext_size=data["ciphertext_size"],
            )
        except AttachmentValidationError as error:
            return _service_error_response(
                error,
                status.HTTP_400_BAD_REQUEST,
            )
        except AttachmentPermissionError as error:
            return _service_error_response(
                error,
                status.HTTP_403_FORBIDDEN,
            )
        except AttachmentNotFoundError as error:
            return _service_error_response(
                error,
                status.HTTP_404_NOT_FOUND,
            )
        except AttachmentConflictError as error:
            return _service_error_response(
                error,
                status.HTTP_409_CONFLICT,
            )

        return Response(
            {
                "success": True,
                "message": "Encrypted attachment completed successfully.",
                "data": EncryptedAttachmentSerializer(attachment).data,
            },
            status=status.HTTP_200_OK,
        )


class EncryptedAttachmentDownloadView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def get(self, request, attachment_id) -> Response:
        serializer = EncryptedAttachmentDeleteSerializer(
            data=request.query_params,
        )

        if not serializer.is_valid():
            return _validation_error_response(serializer.errors)

        data = serializer.validated_data

        try:
            result = get_encrypted_attachment_download(
                authenticated_user_id=str(request.user.user_id),
                attachment_id=attachment_id,
                device_id=data["device_id"],
            )
        except AttachmentValidationError as error:
            return _service_error_response(
                error,
                status.HTTP_400_BAD_REQUEST,
            )
        except AttachmentPermissionError as error:
            return _service_error_response(
                error,
                status.HTTP_403_FORBIDDEN,
            )
        except AttachmentNotFoundError as error:
            return _service_error_response(
                error,
                status.HTTP_404_NOT_FOUND,
            )
        except AttachmentConflictError as error:
            return _service_error_response(
                error,
                status.HTTP_409_CONFLICT,
            )

        return Response(
            {
                "success": True,
                "message": "Encrypted attachment download metadata retrieved.",
                "data": EncryptedAttachmentSerializer(
                    result.attachment,
                ).data,
            },
            status=status.HTTP_200_OK,
        )


class EncryptedAttachmentDeleteView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def delete(self, request, attachment_id) -> Response:
        serializer = EncryptedAttachmentDeleteSerializer(
            data=request.data or request.query_params,
        )

        if not serializer.is_valid():
            return _validation_error_response(serializer.errors)

        data = serializer.validated_data

        try:
            attachment = delete_encrypted_attachment(
                authenticated_user_id=str(request.user.user_id),
                attachment_id=attachment_id,
                device_id=data["device_id"],
            )
        except AttachmentValidationError as error:
            return _service_error_response(
                error,
                status.HTTP_400_BAD_REQUEST,
            )
        except AttachmentPermissionError as error:
            return _service_error_response(
                error,
                status.HTTP_403_FORBIDDEN,
            )
        except AttachmentNotFoundError as error:
            return _service_error_response(
                error,
                status.HTTP_404_NOT_FOUND,
            )
        except AttachmentConflictError as error:
            return _service_error_response(
                error,
                status.HTTP_409_CONFLICT,
            )

        return Response(
            {
                "success": True,
                "message": "Encrypted attachment deleted successfully.",
                "data": EncryptedAttachmentSerializer(attachment).data,
            },
            status=status.HTTP_200_OK,
        )
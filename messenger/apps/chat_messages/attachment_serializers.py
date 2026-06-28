from rest_framework import serializers


class EncryptedAttachmentInitiateSerializer(serializers.Serializer):
    device_id = serializers.UUIDField()
    storage_provider = serializers.ChoiceField(
        choices=[
            "cloudinary",
            "s3",
            "local",
        ],
        required=False,
        default="cloudinary",
    )
    storage_key = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=512,
        trim_whitespace=True,
    )
    media_category = serializers.ChoiceField(
        choices=[
            "image",
            "video",
            "audio",
            "file",
        ],
        required=False,
        default="file",
    )
    expires_at = serializers.DateTimeField(
        required=False,
        allow_null=True,
    )


class EncryptedAttachmentCompleteSerializer(serializers.Serializer):
    device_id = serializers.UUIDField()
    ciphertext_sha256 = serializers.CharField(
        max_length=64,
        min_length=64,
        trim_whitespace=True,
    )
    ciphertext_size = serializers.IntegerField(min_value=1)

    def validate_ciphertext_sha256(self, value):
        normalized = value.strip().lower()

        if any(character not in "0123456789abcdef" for character in normalized):
            raise serializers.ValidationError(
                "ciphertext_sha256 must be a hex SHA-256 digest."
            )

        return normalized


class EncryptedAttachmentDeleteSerializer(serializers.Serializer):
    device_id = serializers.UUIDField()


class EncryptedAttachmentSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    uploader_user_id = serializers.CharField(read_only=True)
    uploader_device_id = serializers.SerializerMethodField()
    storage_provider = serializers.CharField(read_only=True)
    storage_key = serializers.CharField(read_only=True)
    ciphertext_sha256 = serializers.CharField(read_only=True)
    ciphertext_size = serializers.IntegerField(read_only=True)
    media_category = serializers.CharField(read_only=True)
    upload_status = serializers.CharField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    completed_at = serializers.DateTimeField(read_only=True)
    expires_at = serializers.DateTimeField(read_only=True)

    def get_uploader_device_id(self, instance):
        return instance.uploader_device_id
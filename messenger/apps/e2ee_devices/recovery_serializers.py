import json

from rest_framework import serializers

from .models import RecoveryBundle


SUPPORTED_BUNDLE_ALGORITHMS = {
    "xchacha20poly1305-ietf",
}

SUPPORTED_UNLOCK_METHODS = {
    "recovery_key",
    "webauthn_prf",
    "recovery_key_and_webauthn_prf",
}


class RecoverySetupSerializer(serializers.Serializer):
    recovery_public_key = serializers.CharField(
        max_length=4096,
        trim_whitespace=False,
    )
    encrypted_recovery_private_key = serializers.CharField(
        max_length=65535,
        trim_whitespace=False,
    )
    encryption_metadata = serializers.JSONField()

    def validate_recovery_public_key(self, value: str) -> str:
        if not value.strip():
            raise serializers.ValidationError(
                "Recovery public key cannot be empty."
            )
        return value

    def validate_encrypted_recovery_private_key(
        self,
        value: str,
    ) -> str:
        if not value.strip():
            raise serializers.ValidationError(
                "Encrypted recovery private key cannot be empty."
            )
        return value

    def validate_encryption_metadata(self, value: dict) -> dict:
        if not isinstance(value, dict):
            raise serializers.ValidationError(
                "Encryption metadata must be a JSON object."
            )

        encoded_metadata = json.dumps(
            value,
            separators=(",", ":"),
            sort_keys=True,
        )

        if len(encoded_metadata.encode("utf-8")) > 8192:
            raise serializers.ValidationError(
                "Encryption metadata is too large."
            )

        required_fields = {
            "algorithm",
            "nonce",
            "unlock_method",
        }
        missing_fields = sorted(
            required_fields.difference(value.keys())
        )

        if missing_fields:
            raise serializers.ValidationError(
                "Missing required metadata fields: "
                + ", ".join(missing_fields)
                + "."
            )

        algorithm = value.get("algorithm")
        if algorithm not in SUPPORTED_BUNDLE_ALGORITHMS:
            raise serializers.ValidationError(
                "Unsupported recovery bundle algorithm."
            )

        nonce = value.get("nonce")
        if not isinstance(nonce, str) or not nonce.strip():
            raise serializers.ValidationError(
                "A non-empty nonce is required."
            )

        unlock_method = value.get("unlock_method")
        if unlock_method not in SUPPORTED_UNLOCK_METHODS:
            raise serializers.ValidationError(
                "Unsupported recovery unlock method."
            )

        return value


class RecoverySetupResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecoveryBundle
        fields = (
            "recovery_version",
            "is_active",
            "created_at",
            "updated_at",
            "rotated_at",
        )


class RecoveryBundleDownloadSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecoveryBundle
        fields = (
            "recovery_public_key",
            "encrypted_recovery_private_key",
            "encryption_metadata",
            "recovery_version",
            "is_active",
            "created_at",
            "updated_at",
            "rotated_at",
        )

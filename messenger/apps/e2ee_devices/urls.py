from django.urls import path

from .views import (
    DeviceRegistrationView,
    OneTimePreKeyUploadView,
    PreKeyBundleClaimView,
)
from .recovery_views import (
    RecoveryBundleView,
    RecoverySetupView,
    RecoveryStatusView,
)
from .recovery_public_key_views import (
    RecoveryPublicKeyResolveView,
)
from .recovery_rotation_views import (
    RecoveryDisableView,
    RecoveryRotateView,
)


app_name = "e2ee_devices"


urlpatterns = [
    path(
        "devices/register/",
        DeviceRegistrationView.as_view(),
        name="device-register",
    ),
    path(
        "devices/<uuid:device_id>/prekeys/",
        OneTimePreKeyUploadView.as_view(),
        name="prekey-upload",
    ),
    path(
        "prekey-bundles/claim/",
        PreKeyBundleClaimView.as_view(),
        name="prekey-bundle-claim",
    ),
        
    path(
        "recovery/setup/",
        RecoverySetupView.as_view(),
        name="recovery-setup",
    ),
    path(
        "recovery/status/",
        RecoveryStatusView.as_view(),
        name="recovery-status",
    ),
    path(
        "recovery/bundle/",
        RecoveryBundleView.as_view(),
        name="recovery-bundle",
    ),
    path(
        "recovery/public-keys/resolve/",
        RecoveryPublicKeyResolveView.as_view(),
        name="recovery-public-key-resolve",
    ),
    path(
        "recovery/rotate/",
        RecoveryRotateView.as_view(),
        name="recovery-rotate",
    ),
    path(
        "recovery/",
        RecoveryDisableView.as_view(),
        name="recovery-disable",
    ),
]

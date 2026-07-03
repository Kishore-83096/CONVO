from django.apps import AppConfig


class E2EEDevicesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.e2ee_devices"

    def ready(self) -> None:
        from . import signals  # noqa: F401
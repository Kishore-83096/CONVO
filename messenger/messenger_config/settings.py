import os
from pathlib import Path
from urllib.parse import unquote, urlparse

import cloudinary
import environ
from django.core.exceptions import ImproperlyConfigured


# =============================================================================
# Base directory
# =============================================================================

BASE_DIR = Path(__file__).resolve().parent.parent


# =============================================================================
# Environment selection
# =============================================================================
#
# Local:
#   APP_ENV is not required in PowerShell.
#   Django defaults to .env.local.
#
# Production:
#   The operating system or hosting platform must set:
#   APP_ENV=production
#
# The APP_ENV value determines which file Django loads:
#   .env.local
#   .env.production
# =============================================================================

SUPPORTED_ENVIRONMENTS = {"local", "production"}

SELECTED_ENVIRONMENT = os.getenv(
    "APP_ENV",
    "local",
).strip().lower()
ENVIRONMENT_WAS_SELECTED = "APP_ENV" in os.environ

if SELECTED_ENVIRONMENT not in SUPPORTED_ENVIRONMENTS:
    raise ImproperlyConfigured(
        f"Unsupported APP_ENV value: '{SELECTED_ENVIRONMENT}'. "
        f"Supported values are: {', '.join(sorted(SUPPORTED_ENVIRONMENTS))}."
    )

ENV_FILE = BASE_DIR / f".env.{SELECTED_ENVIRONMENT}"

if not ENV_FILE.exists() and not ENVIRONMENT_WAS_SELECTED:
    raise ImproperlyConfigured(
        f"Environment file was not found: {ENV_FILE}"
    )

env = environ.Env()

# Existing operating-system environment variables take priority over
# values stored in the selected .env file.
if ENV_FILE.exists():
    environ.Env.read_env(
        env_file=str(ENV_FILE),
        overwrite=False,
    )

APP_ENV = env(
    "APP_ENV",
    default=SELECTED_ENVIRONMENT,
).strip().lower()

if APP_ENV not in SUPPORTED_ENVIRONMENTS:
    raise ImproperlyConfigured(
        f"The selected environment file contains an invalid APP_ENV "
        f"value: '{APP_ENV}'."
    )

if APP_ENV != SELECTED_ENVIRONMENT:
    raise ImproperlyConfigured(
        f"Environment mismatch: the operating system selected "
        f"'{SELECTED_ENVIRONMENT}', but {ENV_FILE.name} declares "
        f"APP_ENV='{APP_ENV}'."
    )


# =============================================================================
# Core Django settings
# =============================================================================

SECRET_KEY = env("DJANGO_SECRET_KEY")

DEBUG = env.bool(
    "DJANGO_DEBUG",
    default=False,
)

ALLOWED_HOSTS = env.list(
    "DJANGO_ALLOWED_HOSTS",
    default=[],
)

if env.bool("MESSENGER_DOCKER", default=False):
    ALLOWED_HOSTS = list(
        dict.fromkeys(
            [
                *ALLOWED_HOSTS,
                "127.0.0.1",
                "localhost",
            ]
        )
    )

CSRF_TRUSTED_ORIGINS = env.list(
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    default=[],
)


# =============================================================================
# Connected services
# =============================================================================

IDENTITY_SERVICE_BASE_URL = env(
    "IDENTITY_SERVICE_BASE_URL"
).strip().rstrip("/")

FRONTEND_ORIGINS = env.list(
    "FRONTEND_ORIGINS",
    default=[],
)



CONTACT_POLICY_SYNC_SECRET = env(
    "CONTACT_POLICY_SYNC_SECRET",
    default="",
).strip()

# =============================================================================
# Realtime / Redis configuration
# =============================================================================

REDIS_URL = env(
    "REDIS_URL",
    default="redis://127.0.0.1:6379/0",
).strip()

REALTIME_TICKET_TTL_SECONDS = env.int(
    "REALTIME_TICKET_TTL_SECONDS",
    default=60,
)

REALTIME_PRESENCE_TTL_SECONDS = env.int(
    "REALTIME_PRESENCE_TTL_SECONDS",
    default=45,
)

REALTIME_HEARTBEAT_SECONDS = env.int(
    "REALTIME_HEARTBEAT_SECONDS",
    default=20,
)

# =============================================================================
# File storage
# =============================================================================

CLOUDINARY_URL = env(
    "CLOUDINARY_URL",
    default="",
).strip()

CLOUDINARY_FOLDER = env(
    "CLOUDINARY_FOLDER",
    default=f"parrotv2/{APP_ENV}/attachments",
).strip().strip("/")

if not CLOUDINARY_FOLDER:
    raise ImproperlyConfigured("CLOUDINARY_FOLDER must not be empty.")


# =============================================================================
# Secure encrypted attachment upload settings
# =============================================================================

ATTACHMENT_UPLOAD_SIGNATURE_TTL_SECONDS = env.int(
    "ATTACHMENT_UPLOAD_SIGNATURE_TTL_SECONDS",
    default=900,
)

ATTACHMENT_UPLOAD_MAX_TTL_SECONDS = env.int(
    "ATTACHMENT_UPLOAD_MAX_TTL_SECONDS",
    default=900,
)

ATTACHMENT_MIN_TTL_SECONDS = env.int(
    "ATTACHMENT_MIN_TTL_SECONDS",
    default=60,
)

ATTACHMENT_MAX_CIPHERTEXT_BYTES = env.int(
    "ATTACHMENT_MAX_CIPHERTEXT_BYTES",
    default=50 * 1024 * 1024,
)

ATTACHMENT_CLOUDINARY_RESOURCE_TYPE = env(
    "ATTACHMENT_CLOUDINARY_RESOURCE_TYPE",
    default="raw",
).strip()

ATTACHMENT_VERIFY_CLOUDINARY_ON_COMPLETE = env.bool(
    "ATTACHMENT_VERIFY_CLOUDINARY_ON_COMPLETE",
    default=False,
)

ATTACHMENT_DOWNLOAD_URL_TTL_SECONDS = env.int(
    "ATTACHMENT_DOWNLOAD_URL_TTL_SECONDS",
    default=300,
)

ATTACHMENT_DOWNLOAD_URL_MAX_TTL_SECONDS = env.int(
    "ATTACHMENT_DOWNLOAD_URL_MAX_TTL_SECONDS",
    default=900,
)

if ATTACHMENT_DOWNLOAD_URL_TTL_SECONDS < 1:
    raise ImproperlyConfigured(
        "ATTACHMENT_DOWNLOAD_URL_TTL_SECONDS must be greater than 0."
    )

if ATTACHMENT_DOWNLOAD_URL_MAX_TTL_SECONDS > 900:
    raise ImproperlyConfigured(
        "ATTACHMENT_DOWNLOAD_URL_MAX_TTL_SECONDS must not exceed 900 seconds."
    )

if ATTACHMENT_DOWNLOAD_URL_TTL_SECONDS > ATTACHMENT_DOWNLOAD_URL_MAX_TTL_SECONDS:
    raise ImproperlyConfigured(
        "ATTACHMENT_DOWNLOAD_URL_TTL_SECONDS must not exceed "
        "ATTACHMENT_DOWNLOAD_URL_MAX_TTL_SECONDS."
    )


ATTACHMENT_CLEANUP_DELETE_CLOUDINARY = env.bool(
    "ATTACHMENT_CLEANUP_DELETE_CLOUDINARY",
    default=False,
)

ATTACHMENT_UNATTACHED_GRACE_HOURS = env.int(
    "ATTACHMENT_UNATTACHED_GRACE_HOURS",
    default=24,
)

if ATTACHMENT_UNATTACHED_GRACE_HOURS < 1:
    raise ImproperlyConfigured(
        "ATTACHMENT_UNATTACHED_GRACE_HOURS must be at least 1 hour."
    )





if ATTACHMENT_CLOUDINARY_RESOURCE_TYPE != "raw":
    raise ImproperlyConfigured(
        "ATTACHMENT_CLOUDINARY_RESOURCE_TYPE must be 'raw'. "
        "Encrypted attachment bytes must not be uploaded as image/video/audio."
    )

if ATTACHMENT_MIN_TTL_SECONDS < 1:
    raise ImproperlyConfigured(
        "ATTACHMENT_MIN_TTL_SECONDS must be at least 1 second."
    )

if ATTACHMENT_UPLOAD_MAX_TTL_SECONDS > 900:
    raise ImproperlyConfigured(
        "ATTACHMENT_UPLOAD_MAX_TTL_SECONDS must not exceed 900 seconds."
    )

if ATTACHMENT_UPLOAD_SIGNATURE_TTL_SECONDS > ATTACHMENT_UPLOAD_MAX_TTL_SECONDS:
    raise ImproperlyConfigured(
        "ATTACHMENT_UPLOAD_SIGNATURE_TTL_SECONDS must not exceed "
        "ATTACHMENT_UPLOAD_MAX_TTL_SECONDS."
    )

if ATTACHMENT_MIN_TTL_SECONDS > ATTACHMENT_UPLOAD_MAX_TTL_SECONDS:
    raise ImproperlyConfigured(
        "ATTACHMENT_MIN_TTL_SECONDS must not exceed "
        "ATTACHMENT_UPLOAD_MAX_TTL_SECONDS."
    )

if ATTACHMENT_MAX_CIPHERTEXT_BYTES < 1:
    raise ImproperlyConfigured(
        "ATTACHMENT_MAX_CIPHERTEXT_BYTES must be greater than 0."
    )

if APP_ENV == "production" and not CLOUDINARY_URL:
    raise ImproperlyConfigured(
        "CLOUDINARY_URL is required in production for secure attachment uploads."
    )


if CLOUDINARY_URL:
    parsed_cloudinary_url = urlparse(CLOUDINARY_URL)

    if (
        parsed_cloudinary_url.scheme != "cloudinary"
        or not parsed_cloudinary_url.hostname
        or not parsed_cloudinary_url.username
        or not parsed_cloudinary_url.password
    ):
        raise ImproperlyConfigured(
            "CLOUDINARY_URL must use the format "
            "cloudinary://API_KEY:API_SECRET@CLOUD_NAME"
        )

    cloudinary.config(
        cloud_name=parsed_cloudinary_url.hostname,
        api_key=unquote(parsed_cloudinary_url.username),
        api_secret=unquote(parsed_cloudinary_url.password),
        secure=True,
    )
# =============================================================================
# Identity-service JWT verification
# =============================================================================

JWT_ALGORITHM = env(
    "JWT_ALGORITHM",
    default="HS256",
).strip()

JWT_VERIFYING_KEY = env(
    "JWT_VERIFYING_KEY",
)

JWT_IDENTITY_CLAIM = env(
    "JWT_IDENTITY_CLAIM",
    default="sub",
).strip()

JWT_TOKEN_TYPE_CLAIM = env(
    "JWT_TOKEN_TYPE_CLAIM",
    default="type",
).strip()

JWT_ACCESS_TOKEN_TYPE = env(
    "JWT_ACCESS_TOKEN_TYPE",
    default="access",
).strip()

JWT_ISSUER = (
    env(
        "JWT_ISSUER",
        default="",
    ).strip()
    or None
)

JWT_AUDIENCE = (
    env(
        "JWT_AUDIENCE",
        default="",
    ).strip()
    or None
)

JWT_LEEWAY_SECONDS = env.int(
    "JWT_LEEWAY_SECONDS",
    default=5,
)

# =============================================================================
# Installed applications
# =============================================================================

INSTALLED_APPS = [
    # ASGI server integration
    "daphne",

    # Django applications
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Third-party applications
    "channels",
    "rest_framework",

        # Messenger applications
    "apps.rooms.apps.RoomsConfig",
    "apps.chat_messages.apps.ChatMessagesConfig",
    "apps.e2ee_devices.apps.E2EEDevicesConfig",
    "apps.group_chat.apps.GroupChatConfig",
    "apps.realtime.apps.RealtimeConfig",

]

# =============================================================================
# Middleware
# =============================================================================

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "messenger_config.cors.FrontendCorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


# =============================================================================
# URL and application configuration
# =============================================================================

ROOT_URLCONF = "messenger_config.urls"

WSGI_APPLICATION = "messenger_config.wsgi.application"
ASGI_APPLICATION = "messenger_config.asgi.application"

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [
                REDIS_URL,
            ],
        },
    },
}

# =============================================================================
# Templates
# =============================================================================

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]


# =============================================================================
# Database
# =============================================================================

DATABASES = {
    "default": env.db(
        "DATABASE_URL",
    ),
}

DATABASES["default"]["CONN_MAX_AGE"] = env.int(
    "DB_CONN_MAX_AGE",
    default=0,
)

DATABASES["default"]["CONN_HEALTH_CHECKS"] = True


# MySQL-specific configuration.
if DATABASES["default"]["ENGINE"] == "django.db.backends.mysql":
    mysql_options = DATABASES["default"].setdefault(
        "OPTIONS",
        {},
    )

    mysql_options.setdefault(
        "charset",
        "utf8mb4",
    )

    mysql_options.setdefault(
        "init_command",
        "SET sql_mode='STRICT_TRANS_TABLES'",
    )


# =============================================================================
# Password validation
# =============================================================================
#
# The messenger service will not act as the primary identity service.
# These validators remain because Django's admin and built-in authentication
# applications are currently installed.
# =============================================================================

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "MinimumLengthValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "CommonPasswordValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "NumericPasswordValidator"
        ),
    },
]


# =============================================================================
# Internationalization
# =============================================================================

LANGUAGE_CODE = "en-us"

TIME_ZONE = env(
    "DJANGO_TIME_ZONE",
    default="UTC",
)

USE_I18N = True

USE_TZ = True


# =============================================================================
# Static files
# =============================================================================

STATIC_URL = "static/"


# =============================================================================
# Default model primary key
# =============================================================================

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# =============================================================================
# Django REST Framework
# =============================================================================
#
# JWT verification will be added later through a custom authentication class.
# For now, no authentication class is configured prematurely.
# =============================================================================

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        (
            "messenger_config.authentication."
            "IdentityJWTAuthentication"
        ),
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
        "rest_framework.parsers.FormParser",
    ],
    "EXCEPTION_HANDLER": (
        "rest_framework.views.exception_handler"
    ),
}


# =============================================================================
# Cookie and transport security
# =============================================================================

SECURE_SSL_REDIRECT = env.bool(
    "DJANGO_SECURE_SSL_REDIRECT",
    default=False,
)

SESSION_COOKIE_SECURE = env.bool(
    "DJANGO_SESSION_COOKIE_SECURE",
    default=False,
)

CSRF_COOKIE_SECURE = env.bool(
    "DJANGO_CSRF_COOKIE_SECURE",
    default=False,
)

SECURE_HSTS_SECONDS = env.int(
    "DJANGO_HSTS_SECONDS",
    default=0,
)

SECURE_HSTS_INCLUDE_SUBDOMAINS = (
    APP_ENV == "production"
    and SECURE_HSTS_SECONDS > 0
)

SECURE_HSTS_PRELOAD = (
    APP_ENV == "production"
    and SECURE_HSTS_SECONDS > 0
)

SECURE_CONTENT_TYPE_NOSNIFF = True

SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

SESSION_COOKIE_HTTPONLY = True

SESSION_COOKIE_SAMESITE = "Lax"

CSRF_COOKIE_SAMESITE = "Lax"

X_FRAME_OPTIONS = "DENY"


# Render and similar reverse proxies terminate HTTPS before forwarding
# traffic to Django.
if APP_ENV == "production":
    SECURE_PROXY_SSL_HEADER = (
        "HTTP_X_FORWARDED_PROTO",
        "https",
    )


# =============================================================================
# Logging
# =============================================================================

LOG_LEVEL = env(
    "LOG_LEVEL",
    default="INFO",
).strip().upper()

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": (
                "{levelname} {asctime} "
                "{name} {message}"
            ),
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
        },
    },
    "root": {
        "handlers": [
            "console",
        ],
        "level": LOG_LEVEL,
    },
    "loggers": {
        "django": {
            "handlers": [
                "console",
            ],
            "level": LOG_LEVEL,
            "propagate": False,
        },
    },
}

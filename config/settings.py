"""Django settings for blue_notes project.

Generated for Senior Backend Take-Home Assessment.
"""

from pathlib import Path

import environ

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Initialize environ
env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1", "0.0.0.0", "web"]),
)

# Read environment variables from .env.local if present
env_file = BASE_DIR / ".env.local"
if env_file.exists():
    environ.Env.read_env(env_file)
else:
    environ.Env.read_env()

# Quick-start development settings - unsuitable for production
SECRET_KEY = env("SECRET_KEY", default="django-insecure-default-change-me-in-production")

DEBUG = env("DEBUG")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["*"])

# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    # Third-party apps
    "rest_framework",
    "rest_framework.authtoken",
    "corsheaders",
    "drf_spectacular",
    "django_filters",
    # Local domain apps
    "apps.core",
    "apps.users",
    "apps.teams",
    "apps.notes",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# Database
# Default connects to PostgreSQL using DATABASE_URL
DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default="postgres://blue_notes_user:blue_notes_password@postgres:5432/blue_notes_db",
    )
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Django REST Framework Settings
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.FormParser",
        "rest_framework.parsers.MultiPartParser",
    ],
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.StandardResultsSetPagination",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "apps.core.exception_handler.custom_exception_handler",
    "DATETIME_FORMAT": "%Y-%m-%dT%H:%M:%SZ",
}

# OpenAPI documentation settings via drf-spectacular
SPECTACULAR_SETTINGS = {
    "TITLE": "Blue Notes API",
    "DESCRIPTION": (
        "REST API for multi-tenant team note-taking service. "
        "Supports user auth, team workspaces, personal & team notes, "
        "Optimistic Concurrency Control (OCC), revision history, soft-delete, "
        "and PostgreSQL full-text search."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SWAGGER_UI_SETTINGS": {
        "deepLinking": True,
        "persistAuthorization": True,
        "displayOperationId": False,
        "defaultModelsExpandDepth": 2,
        "defaultModelExpandDepth": 2,
        "filter": True,
        "docExpansion": "list",
        "showExtensions": True,
        "showCommonExtensions": True,
    },
    "TAGS": [
        {
            "name": "Authentication",
            "description": "User registration, authentication token acquisition, and profile management.",
        },
        {
            "name": "Teams",
            "description": "Workspace multi-tenancy, member rosters, and RBAC role assignments.",
        },
        {
            "name": "Notes",
            "description": "Personal and team note capture, OCC edits, revisions, soft-delete, and search.",
        },
        {
            "name": "Tags",
            "description": "Categorical tags for organizing and filtering notes.",
        },
        {
            "name": "Health",
            "description": "System liveness and health status checks.",
        },
    ],
}

# CORS configuration (permissive for local dev)
CORS_ALLOW_ALL_ORIGINS = DEBUG

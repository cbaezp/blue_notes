"""URL configuration for blue_notes project."""

from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from drf_spectacular.utils import extend_schema
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)


@extend_schema(
    tags=["Health"],
    summary="Health check",
    description="Returns service availability and status.",
    responses={
        200: {
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "service": {"type": "string"},
            },
        }
    },
)
def health_check(request):
    """Basic health check endpoint returning service status."""
    return JsonResponse({"status": "ok", "service": "blue_notes"})


urlpatterns = [
    # Admin
    path("admin/", admin.site.urls),
    # Health Check
    path("health/", health_check, name="health_check"),
    # OpenAPI 3.0 Documentation
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    # API v1 Versioned Endpoints
    path("api/v1/auth/", include("apps.users.urls", namespace="users")),
    path("api/v1/teams/", include("apps.teams.urls", namespace="teams")),
    path("api/v1/notes/", include("apps.notes.urls", namespace="notes")),
]

"""URL configuration for blue_notes project."""

from django.contrib import admin
from django.http import JsonResponse
from django.urls import path


def health_check(request):
    """Basic health check endpoint returning service status."""
    return JsonResponse({"status": "ok", "service": "blue_notes"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health_check, name="health_check"),
]

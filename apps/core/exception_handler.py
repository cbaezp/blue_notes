"""Standardized DRF custom exception handler."""

from typing import Any

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler


def custom_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    """Provide a consistent, typed JSON structure for all API errors."""
    if isinstance(exc, Http404):
        exc = exceptions.NotFound(*(exc.args))
    elif isinstance(exc, DjangoPermissionDenied):
        exc = exceptions.PermissionDenied(*(exc.args))

    response = exception_handler(exc, context)

    if response is not None:
        error_code = getattr(exc, "default_code", "error")
        detail_data = response.data

        if isinstance(detail_data, dict):
            message = detail_data.get("detail", "An error occurred.")
            details = {k: v for k, v in detail_data.items() if k != "detail"}
        elif isinstance(detail_data, list):
            message = "Validation failed."
            details = {"errors": detail_data}
        else:
            message = str(detail_data)
            details = {}

        response.data = {
            "error": {
                "code": error_code,
                "message": message,
                "status_code": response.status_code,
                "details": details if details else None,
            }
        }
    else:
        # Unhandled 500 error format
        response = Response(
            {
                "error": {
                    "code": "internal_server_error",
                    "message": "An unexpected error occurred on the server.",
                    "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                    "details": None,
                }
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return response

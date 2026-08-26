"""Custom application exceptions for domain and business logic."""

from rest_framework import status
from rest_framework.exceptions import APIException


class ConflictError(APIException):
    """Raised when an optimistic concurrency control collision occurs."""

    status_code = status.HTTP_409_CONFLICT
    default_detail = "Conflict: The resource was modified by another request."
    default_code = "conflict"


class ValidationError(APIException):
    """Raised when a business rule or invariant validation fails."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Invalid input or business rule violation."
    default_code = "validation_error"


class PermissionDeniedError(APIException):
    """Raised when an operation violates domain authorization rules."""

    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "You do not have permission to perform this action."
    default_code = "permission_denied"


class NotFoundError(APIException):
    """Raised when a domain entity is not found or not accessible."""

    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "Resource not found."
    default_code = "not_found"

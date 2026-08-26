"""Base abstract models for the application."""

import uuid

from django.db import models
from django.utils import timezone


class TimeStampedModel(models.Model):
    """Abstract model providing self-updating created_at and updated_at fields."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UUIDPrimaryKeyModel(models.Model):
    """Abstract model providing a UUID primary key for globally unique IDs."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class SoftDeleteQuerySet(models.QuerySet):
    """Custom queryset providing active (non-deleted) filtering and soft delete operations."""

    def active(self):
        return self.filter(deleted_at__isnull=True)

    def deleted(self):
        return self.filter(deleted_at__isnull=False)

    def soft_delete(self):
        return self.update(deleted_at=timezone.now())

    def restore(self):
        return self.update(deleted_at=None)


class SoftDeleteModel(models.Model):
    """Abstract model supporting soft-deletion."""

    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)
    all_objects = models.Manager()
    objects = SoftDeleteQuerySet.as_manager()

    class Meta:
        abstract = True

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def soft_delete(self) -> None:
        self.deleted_at = timezone.now()
        self.save(
            update_fields=["deleted_at", "updated_at"]
            if hasattr(self, "updated_at")
            else ["deleted_at"]
        )

    def restore(self) -> None:
        self.deleted_at = None
        self.save(
            update_fields=["deleted_at", "updated_at"]
            if hasattr(self, "updated_at")
            else ["deleted_at"]
        )

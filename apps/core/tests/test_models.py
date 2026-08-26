"""Unit tests for Core base models, SoftDelete, and QuerySets."""

import pytest

from apps.notes.models import Note
from tests.factories import UserFactory


@pytest.mark.django_db
class TestCoreModels:
    """Tests for abstract models, soft-delete mechanisms, and querysets."""

    def test_soft_delete_queryset_active_and_deleted_filters(self):
        """Verify SoftDeleteQuerySet filters active vs deleted records."""
        user = UserFactory()
        Note.objects.create(author=user, title="Active Note")
        note_2 = Note.objects.create(author=user, title="To Delete Note")

        assert Note.objects.active().count() == 2
        assert Note.objects.deleted().count() == 0

        note_2.soft_delete()

        assert Note.objects.active().count() == 1
        assert Note.objects.deleted().count() == 1
        assert note_2.is_deleted is True

        note_2.restore()

        assert Note.objects.active().count() == 2
        assert Note.objects.deleted().count() == 0
        assert note_2.is_deleted is False

    def test_bulk_soft_delete_and_restore(self):
        """Verify bulk soft delete and restore on querysets."""
        user = UserFactory()
        Note.objects.create(author=user, title="N1")
        Note.objects.create(author=user, title="N2")

        Note.objects.filter(author=user).soft_delete()
        assert Note.objects.active().count() == 0
        assert Note.all_objects.filter(author=user, deleted_at__isnull=False).count() == 2

        Note.objects.deleted().filter(author=user).restore()
        assert Note.objects.active().count() == 2

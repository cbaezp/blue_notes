"""Unit tests for note services and Optimistic Concurrency Control."""

import pytest

from apps.core.exceptions import ConflictError
from apps.notes.models import NoteVersion
from apps.notes.services import note_create, note_revert, note_update
from tests.factories import TeamFactory, UserFactory


@pytest.mark.django_db
class TestNoteServices:
    """Unit tests for note mutations and concurrency handling."""

    def test_note_create_creates_initial_version(self):
        """Verify note_create creates note and version 1 snapshot."""
        user = UserFactory()
        note = note_create(author=user, title="Hello World", body="Initial body")

        assert note.version == 1
        assert note.is_personal is True

        version_1 = NoteVersion.objects.filter(note=note, version_number=1).first()
        assert version_1 is not None
        assert version_1.title == "Hello World"
        assert version_1.edited_by == user

    def test_note_update_occ_conflict_raises_error(self):
        """Verify updating with mismatched version raises ConflictError."""
        user = UserFactory()
        team = TeamFactory(created_by=user)
        note = note_create(author=user, title="v1", body="Content", team=team)

        # Increment to version 2
        note_update(note=note, expected_version=1, user=user, title="v2")

        # Trying to update with stale version 1 must raise ConflictError
        with pytest.raises(ConflictError):
            note_update(note=note, expected_version=1, user=user, title="stale v2")

    def test_note_revert_restores_prior_content(self):
        """Verify note_revert creates a new version restoring historical content."""
        user = UserFactory()
        team = TeamFactory(created_by=user)
        note = note_create(author=user, title="Initial Title", body="Initial Body", team=team)

        # Update to version 2
        note_update(
            note=note, expected_version=1, user=user, title="Updated Title", body="Updated Body"
        )

        # Revert back to version 1
        reverted = note_revert(note=note, version_number=1, user=user)
        assert reverted.version == 3
        assert reverted.title == "Initial Title"
        assert reverted.body == "Initial Body"

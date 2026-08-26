"""Edge case tests for Notes API, Pagination, and Error Handling."""

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.notes.models import Note
from apps.notes.services import note_create
from tests.factories import TeamFactory, UserFactory


@pytest.mark.django_db
class TestNoteEdgeCases:
    """Test suite for edge cases, pagination, error structures, and validation."""

    def setup_method(self):
        self.client = APIClient()
        self.user = UserFactory()
        self.other_user = UserFactory()
        self.team = TeamFactory(created_by=self.user)
        self.foreign_team = TeamFactory(created_by=self.other_user)

    def test_pagination_structure(self):
        """Verify list endpoint returns standard pagination envelope."""
        for i in range(5):
            note_create(author=self.user, title=f"Note {i}", body="Body")

        self.client.force_authenticate(user=self.user)
        url = reverse("notes:notes-list")
        response = self.client.get(url, {"page": 1, "page_size": 2})

        assert response.status_code == status.HTTP_200_OK
        assert "count" in response.data
        assert "next" in response.data
        assert "previous" in response.data
        assert "results" in response.data
        assert response.data["count"] == 5
        assert len(response.data["results"]) == 2

    def test_pinned_notes_filter(self):
        """Verify ?is_pinned=true only returns pinned notes."""
        note_create(author=self.user, title="Pinned Note", is_pinned=True)
        note_create(author=self.user, title="Normal Note", is_pinned=False)

        self.client.force_authenticate(user=self.user)
        url = reverse("notes:notes-list")
        response = self.client.get(url, {"is_pinned": "true"})

        assert response.status_code == status.HTTP_200_OK
        results = response.data["results"]
        assert len(results) == 1
        assert results[0]["title"] == "Pinned Note"

    def test_update_missing_expected_version_fails(self):
        """Verify update without expected_version returns 400 Bad Request."""
        note = note_create(author=self.user, title="Initial", body="Body")
        self.client.force_authenticate(user=self.user)

        url = reverse("notes:notes-detail", kwargs={"pk": note.id})
        payload = {"title": "Updated"}  # Missing expected_version
        response = self.client.put(url, payload, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "expected_version" in response.data["error"]["details"]

    def test_hard_delete_permanently_removes_note(self):
        """Verify DELETE with ?hard=true permanently purges record."""
        note = note_create(author=self.user, title="Purge Me", body="Body")
        self.client.force_authenticate(user=self.user)

        url = reverse("notes:notes-detail", kwargs={"pk": note.id})
        response = self.client.delete(f"{url}?hard=true")

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Note.all_objects.filter(id=note.id).exists()

    def test_revert_to_nonexistent_version_fails(self):
        """Verify reverting to an invalid version returns 400 Bad Request."""
        note = note_create(author=self.user, title="Initial", body="Body")
        self.client.force_authenticate(user=self.user)

        url = reverse("notes:notes-revert", kwargs={"pk": note.id})
        response = self.client.post(url, {"version_number": 999}, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "does not exist" in response.data["error"]["message"]

    def test_share_already_shared_note_fails(self):
        """Verify attempting to share an existing team note returns 400 Bad Request."""
        team_note = note_create(author=self.user, title="Team Note", team=self.team)
        self.client.force_authenticate(user=self.user)

        url = reverse("notes:notes-share-to-team", kwargs={"pk": team_note.id})
        response = self.client.post(url, {"team_id": str(self.team.id)}, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "already assigned to a team" in response.data["error"]["message"]

    def test_share_to_foreign_team_forbidden(self):
        """Verify sharing note to a team where user is not a member returns 403 Forbidden."""
        personal_note = note_create(author=self.user, title="My Note")
        self.client.force_authenticate(user=self.user)

        url = reverse("notes:notes-share-to-team", kwargs={"pk": personal_note.id})
        response = self.client.post(url, {"team_id": str(self.foreign_team.id)}, format="json")

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "not a member" in response.data["error"]["message"]

    def test_custom_exception_handler_json_structure(self):
        """Verify 404 error returns standard RFC-style error structure."""
        self.client.force_authenticate(user=self.user)
        url = reverse("notes:notes-detail", kwargs={"pk": "00000000-0000-0000-0000-000000000000"})
        response = self.client.get(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "error" in response.data
        assert response.data["error"]["status_code"] == 404
        assert response.data["error"]["code"] == "not_found"
        assert "message" in response.data["error"]

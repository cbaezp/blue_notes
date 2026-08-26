"""Integration tests for Notes REST endpoints, lifecycle, OCC, and sharing."""

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.notes.models import NoteVisibility
from apps.notes.services import note_create
from apps.teams.models import TeamRole
from tests.factories import TeamFactory, TeamMembershipFactory, UserFactory


@pytest.mark.django_db
class TestNotesAPI:
    """Test suite for note operations, permissions, OCC, and lifecycle."""

    def setup_method(self):
        self.client = APIClient()
        self.user_a = UserFactory(username="alice")
        self.user_b = UserFactory(username="bob")
        self.user_c = UserFactory(username="charlie")  # Viewer

        self.team = TeamFactory(name="Engineering", created_by=self.user_a)
        TeamMembershipFactory(team=self.team, user=self.user_b, role=TeamRole.MEMBER)
        TeamMembershipFactory(team=self.team, user=self.user_c, role=TeamRole.VIEWER)

    def test_create_and_retrieve_personal_note(self):
        """Verify personal note is created with team=null and only visible to author."""
        self.client.force_authenticate(user=self.user_a)

        url = reverse("notes:notes-list")
        payload = {
            "title": "My Private Scratchpad",
            "body": "Secret personal ideas",
            "team_id": None,
        }
        response = self.client.post(url, payload, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["title"] == "My Private Scratchpad"
        assert response.data["is_personal"] is True
        assert response.data["version"] == 1
        note_id = response.data["id"]

        # Alice can retrieve it
        detail_url = reverse("notes:notes-detail", kwargs={"pk": note_id})
        detail_resp = self.client.get(detail_url)
        assert detail_resp.status_code == status.HTTP_200_OK

        # Bob (other user) cannot view Alice's personal note
        self.client.force_authenticate(user=self.user_b)
        forbidden_resp = self.client.get(detail_url)
        assert forbidden_resp.status_code == status.HTTP_404_NOT_FOUND

    def test_create_and_retrieve_team_note(self):
        """Verify team note is shared among team members."""
        self.client.force_authenticate(user=self.user_a)

        url = reverse("notes:notes-list")
        payload = {
            "title": "Q3 Architecture Roadmap",
            "body": "Design notes for microservices",
            "team_id": str(self.team.id),
            "visibility": NoteVisibility.TEAM,
        }
        response = self.client.post(url, payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        note_id = response.data["id"]

        # Bob (team member) can retrieve the team note
        self.client.force_authenticate(user=self.user_b)
        detail_url = reverse("notes:notes-detail", kwargs={"pk": note_id})
        resp = self.client.get(detail_url)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["title"] == "Q3 Architecture Roadmap"

    def test_viewer_cannot_create_or_edit_team_note(self):
        """Verify viewer has read-only access to team notes."""
        self.client.force_authenticate(user=self.user_c)

        url = reverse("notes:notes-list")
        payload = {
            "title": "Viewer Note",
            "body": "Should fail",
            "team_id": str(self.team.id),
        }
        response = self.client.post(url, payload, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_optimistic_concurrency_control_success(self):
        """Verify updating with expected_version succeeds and increments version."""
        note = note_create(author=self.user_a, title="Initial", body="Body v1", team=self.team)
        self.client.force_authenticate(user=self.user_a)

        url = reverse("notes:notes-detail", kwargs={"pk": note.id})
        payload = {
            "title": "Updated Title",
            "body": "Body v2",
            "expected_version": 1,
            "change_summary": "Revised architecture",
        }
        response = self.client.put(url, payload, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["version"] == 2
        assert response.data["title"] == "Updated Title"

    def test_optimistic_concurrency_control_conflict_409(self):
        """Verify updating with stale expected_version triggers 409 Conflict."""
        note = note_create(author=self.user_a, title="Initial", body="Body v1", team=self.team)
        self.client.force_authenticate(user=self.user_a)

        # Simulate concurrent edit: User A edits to v2 first
        url = reverse("notes:notes-detail", kwargs={"pk": note.id})
        self.client.put(url, {"title": "Alice edit", "expected_version": 1}, format="json")

        # User B attempts to edit still thinking note is at version 1
        self.client.force_authenticate(user=self.user_b)
        response = self.client.put(
            url, {"title": "Bob stale edit", "expected_version": 1}, format="json"
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        assert "Conflict" in response.data["error"]["message"]

    def test_soft_delete_and_restore_lifecycle(self):
        """Verify soft-delete moves note to trash and restore recovers it."""
        note = note_create(author=self.user_a, title="Delete Me", body="Temporary", team=self.team)
        self.client.force_authenticate(user=self.user_a)

        detail_url = reverse("notes:notes-detail", kwargs={"pk": note.id})
        list_url = reverse("notes:notes-list")
        trash_url = reverse("notes:notes-trash")
        restore_url = reverse("notes:notes-restore", kwargs={"pk": note.id})

        # 1. Delete note
        delete_resp = self.client.delete(detail_url)
        assert delete_resp.status_code == status.HTTP_204_NO_CONTENT

        # 2. Verify excluded from active list
        active_resp = self.client.get(list_url)
        active_ids = [n["id"] for n in active_resp.data["results"]]
        assert str(note.id) not in active_ids

        # 3. Verify present in trash
        trash_resp = self.client.get(trash_url)
        trash_ids = [n["id"] for n in trash_resp.data["results"]]
        assert str(note.id) in trash_ids

        # 4. Restore note
        restore_resp = self.client.post(restore_url)
        assert restore_resp.status_code == status.HTTP_200_OK

        # 5. Verify back in active list
        active_resp = self.client.get(list_url)
        active_ids = [n["id"] for n in active_resp.data["results"]]
        assert str(note.id) in active_ids

    def test_revision_history_and_revert(self):
        """Verify revision snapshots are recorded and revert restores historical content."""
        note = note_create(
            author=self.user_a, title="Draft Title", body="Draft content", team=self.team
        )
        self.client.force_authenticate(user=self.user_a)

        detail_url = reverse("notes:notes-detail", kwargs={"pk": note.id})
        history_url = reverse("notes:notes-history", kwargs={"pk": note.id})
        revert_url = reverse("notes:notes-revert", kwargs={"pk": note.id})

        # Update note to version 2
        update_resp = self.client.put(
            detail_url,
            {"title": "Second Edition", "body": "New content", "expected_version": 1},
            format="json",
        )
        assert update_resp.status_code == status.HTTP_200_OK

        # Check history has 2 versions
        history_resp = self.client.get(history_url)
        assert history_resp.status_code == status.HTTP_200_OK
        assert len(history_resp.data) == 2
        assert history_resp.data[0]["version_number"] == 2
        assert history_resp.data[1]["version_number"] == 1

        # Revert back to version 1
        revert_resp = self.client.post(revert_url, {"version_number": 1}, format="json")
        assert revert_resp.status_code == status.HTTP_200_OK
        assert revert_resp.data["title"] == "Draft Title"
        assert revert_resp.data["body"] == "Draft content"
        assert revert_resp.data["version"] == 3

    def test_share_personal_note_to_team(self):
        """Verify personal note can be promoted to a team note."""
        personal_note = note_create(
            author=self.user_a, title="Personal Draft", body="Will share soon"
        )
        self.client.force_authenticate(user=self.user_a)

        share_url = reverse("notes:notes-share-to-team", kwargs={"pk": personal_note.id})
        payload = {"team_id": str(self.team.id), "visibility": NoteVisibility.TEAM}
        response = self.client.post(share_url, payload, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["team"] == self.team.id
        assert response.data["is_personal"] is False

        # Bob (team member) can now see it
        self.client.force_authenticate(user=self.user_b)
        detail_url = reverse("notes:notes-detail", kwargs={"pk": personal_note.id})
        bob_resp = self.client.get(detail_url)
        assert bob_resp.status_code == status.HTTP_200_OK

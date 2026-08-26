"""Exhaustive permission matrix tests for Notes (Personal, Team, Visibility, and Roles)."""

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.notes.models import NoteVisibility
from apps.notes.services import note_create
from apps.teams.models import TeamRole
from tests.factories import TeamFactory, TeamMembershipFactory, UserFactory


@pytest.mark.django_db
class TestNotePermissionsMatrix:
    """Comprehensive tests for Note access control across all roles and visibilities."""

    def setup_method(self):
        self.client = APIClient()
        self.owner = UserFactory(username="team_owner")
        self.admin = UserFactory(username="team_admin")
        self.member_author = UserFactory(username="member_author")
        self.member_other = UserFactory(username="member_other")
        self.viewer = UserFactory(username="team_viewer")
        self.outsider = UserFactory(username="outsider")

        # Create Team workspace
        self.team = TeamFactory(name="Engineering", created_by=self.owner)
        TeamMembershipFactory(team=self.team, user=self.admin, role=TeamRole.ADMIN)
        TeamMembershipFactory(team=self.team, user=self.member_author, role=TeamRole.MEMBER)
        TeamMembershipFactory(team=self.team, user=self.member_other, role=TeamRole.MEMBER)
        TeamMembershipFactory(team=self.team, user=self.viewer, role=TeamRole.VIEWER)

        # 1. Personal Note by member_author (team=None)
        self.personal_note = note_create(
            author=self.member_author,
            title="Personal Secret Diary",
            body="Personal thoughts",
        )

        # 2. Shared Team Note by member_author (team=team, visibility=TEAM)
        self.team_shared_note = note_create(
            author=self.member_author,
            title="Team Architecture Spec",
            body="Public to team",
            team=self.team,
            visibility=NoteVisibility.TEAM,
        )

        # 3. Private Team Note by member_author (team=team, visibility=PRIVATE)
        self.team_private_note = note_create(
            author=self.member_author,
            title="Private Team Draft",
            body="Confidential draft within team",
            team=self.team,
            visibility=NoteVisibility.PRIVATE,
        )

    # -------------------------------------------------------------------------
    # Personal Note Permissions
    # -------------------------------------------------------------------------
    def test_personal_note_author_has_full_access(self):
        """Author can view, update, and soft-delete their personal note."""
        self.client.force_authenticate(user=self.member_author)
        url = reverse("notes:notes-detail", kwargs={"pk": self.personal_note.id})

        # Read
        get_resp = self.client.get(url)
        assert get_resp.status_code == status.HTTP_200_OK

        # Edit
        put_resp = self.client.put(
            url, {"title": "Updated Secret", "expected_version": 1}, format="json"
        )
        assert put_resp.status_code == status.HTTP_200_OK

    @pytest.mark.parametrize("user_attr", ["owner", "admin", "member_other", "viewer", "outsider"])
    def test_personal_note_hidden_from_all_other_users(self, user_attr):
        """No other user (even team admins) can access someone's personal note."""
        user = getattr(self, user_attr)
        self.client.force_authenticate(user=user)
        url = reverse("notes:notes-detail", kwargs={"pk": self.personal_note.id})

        get_resp = self.client.get(url)
        assert get_resp.status_code == status.HTTP_404_NOT_FOUND

        put_resp = self.client.put(url, {"title": "Hacked", "expected_version": 1}, format="json")
        assert put_resp.status_code == status.HTTP_404_NOT_FOUND

        del_resp = self.client.delete(url)
        assert del_resp.status_code == status.HTTP_404_NOT_FOUND

    # -------------------------------------------------------------------------
    # Team Shared Note Permissions
    # -------------------------------------------------------------------------
    @pytest.mark.parametrize(
        ("user_attr", "expected_status"),
        [
            ("owner", status.HTTP_200_OK),
            ("admin", status.HTTP_200_OK),
            ("member_author", status.HTTP_200_OK),
            ("member_other", status.HTTP_200_OK),
            ("viewer", status.HTTP_200_OK),
            ("outsider", status.HTTP_404_NOT_FOUND),
        ],
    )
    def test_team_shared_note_read_permissions(self, user_attr, expected_status):
        """All team members can read shared team notes; outsiders cannot."""
        user = getattr(self, user_attr)
        self.client.force_authenticate(user=user)
        url = reverse("notes:notes-detail", kwargs={"pk": self.team_shared_note.id})

        response = self.client.get(url)
        assert response.status_code == expected_status

    @pytest.mark.parametrize(
        ("user_attr", "expected_status"),
        [
            ("owner", status.HTTP_200_OK),
            ("admin", status.HTTP_200_OK),
            ("member_author", status.HTTP_200_OK),
            ("member_other", status.HTTP_200_OK),
            ("viewer", status.HTTP_403_FORBIDDEN),
            ("outsider", status.HTTP_404_NOT_FOUND),
        ],
    )
    def test_team_shared_note_edit_permissions(self, user_attr, expected_status):
        """Owner, Admin, and Members can edit shared notes; Viewers cannot."""
        user = getattr(self, user_attr)
        self.client.force_authenticate(user=user)
        url = reverse("notes:notes-detail", kwargs={"pk": self.team_shared_note.id})

        response = self.client.put(
            url, {"title": f"Edited by {user_attr}", "expected_version": 1}, format="json"
        )
        assert response.status_code == expected_status

    def test_member_cannot_delete_other_members_note(self):
        """A Member cannot delete a note authored by another member."""
        self.client.force_authenticate(user=self.member_other)
        url = reverse("notes:notes-detail", kwargs={"pk": self.team_shared_note.id})
        response = self.client.delete(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_admin_and_owner_can_delete_any_team_note(self):
        """Team Admins and Owners have moderation authority to delete any team note."""
        self.client.force_authenticate(user=self.admin)
        url = reverse("notes:notes-detail", kwargs={"pk": self.team_shared_note.id})
        response = self.client.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT

    # -------------------------------------------------------------------------
    # Team Private Note Permissions
    # -------------------------------------------------------------------------
    @pytest.mark.parametrize(
        ("user_attr", "expected_status"),
        [
            ("member_author", status.HTTP_200_OK),
            ("owner", status.HTTP_200_OK),
            ("admin", status.HTTP_200_OK),
            ("member_other", status.HTTP_404_NOT_FOUND),
            ("viewer", status.HTTP_404_NOT_FOUND),
            ("outsider", status.HTTP_404_NOT_FOUND),
        ],
    )
    def test_team_private_note_visibility(self, user_attr, expected_status):
        """Private notes inside a team are only visible to the author and team admins/owners."""
        user = getattr(self, user_attr)
        self.client.force_authenticate(user=user)
        url = reverse("notes:notes-detail", kwargs={"pk": self.team_private_note.id})

        response = self.client.get(url)
        assert response.status_code == expected_status

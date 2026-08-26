"""Comprehensive permission matrix tests for Team workspaces."""

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.teams.models import TeamRole
from tests.factories import TeamFactory, TeamMembershipFactory, UserFactory


@pytest.mark.django_db
class TestTeamPermissionsMatrix:
    """Exhaustive tests verifying RBAC boundaries for all Team roles."""

    def setup_method(self):
        self.client = APIClient()
        self.owner = UserFactory(username="team_owner")
        self.admin = UserFactory(username="team_admin")
        self.member = UserFactory(username="team_member")
        self.viewer = UserFactory(username="team_viewer")
        self.outsider = UserFactory(username="outsider")

        self.team = TeamFactory(name="Core Team", created_by=self.owner)
        TeamMembershipFactory(team=self.team, user=self.admin, role=TeamRole.ADMIN)
        TeamMembershipFactory(team=self.team, user=self.member, role=TeamRole.MEMBER)
        TeamMembershipFactory(team=self.team, user=self.viewer, role=TeamRole.VIEWER)

    # 1. Update Team Details (Owner & Admin: Allowed; Member & Viewer: Forbidden)
    @pytest.mark.parametrize(
        ("user_attr", "expected_status"),
        [
            ("owner", status.HTTP_200_OK),
            ("admin", status.HTTP_200_OK),
            ("member", status.HTTP_403_FORBIDDEN),
            ("viewer", status.HTTP_403_FORBIDDEN),
            ("outsider", status.HTTP_404_NOT_FOUND),
        ],
    )
    def test_update_team_permission(self, user_attr, expected_status):
        user = getattr(self, user_attr)
        self.client.force_authenticate(user=user)

        url = reverse("teams:teams-detail", kwargs={"pk": self.team.id})
        response = self.client.patch(url, {"name": "New Team Name"}, format="json")
        assert response.status_code == expected_status

    # 2. Delete Team Workspace (Owner: Allowed; Admin, Member, Viewer: Forbidden)
    @pytest.mark.parametrize(
        ("user_attr", "expected_status"),
        [
            ("admin", status.HTTP_403_FORBIDDEN),
            ("member", status.HTTP_403_FORBIDDEN),
            ("viewer", status.HTTP_403_FORBIDDEN),
            ("outsider", status.HTTP_404_NOT_FOUND),
        ],
    )
    def test_delete_team_non_owner_forbidden(self, user_attr, expected_status):
        user = getattr(self, user_attr)
        self.client.force_authenticate(user=user)

        url = reverse("teams:teams-detail", kwargs={"pk": self.team.id})
        response = self.client.delete(url)
        assert response.status_code == expected_status

    def test_delete_team_by_owner_success(self):
        self.client.force_authenticate(user=self.owner)
        url = reverse("teams:teams-detail", kwargs={"pk": self.team.id})
        response = self.client.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT

    # 3. Add Members Permission
    @pytest.mark.parametrize(
        ("user_attr", "expected_status"),
        [
            ("owner", status.HTTP_201_CREATED),
            ("admin", status.HTTP_201_CREATED),
            ("member", status.HTTP_403_FORBIDDEN),
            ("viewer", status.HTTP_403_FORBIDDEN),
        ],
    )
    def test_add_member_permissions(self, user_attr, expected_status):
        user = getattr(self, user_attr)
        self.client.force_authenticate(user=user)

        new_candidate = UserFactory()
        url = reverse("teams:teams-add-member", kwargs={"pk": self.team.id})
        response = self.client.post(
            url, {"user_id": new_candidate.id, "role": TeamRole.MEMBER}, format="json"
        )
        assert response.status_code == expected_status

    # 4. Member Self-Removal (Leave Team)
    def test_member_can_leave_team(self):
        self.client.force_authenticate(user=self.member)
        url = reverse(
            "teams:teams-remove-member", kwargs={"pk": self.team.id, "user_id": self.member.id}
        )
        response = self.client.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT

    # 5. Member cannot remove other members
    def test_member_cannot_remove_other_members(self):
        self.client.force_authenticate(user=self.member)
        url = reverse(
            "teams:teams-remove-member", kwargs={"pk": self.team.id, "user_id": self.viewer.id}
        )
        response = self.client.delete(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

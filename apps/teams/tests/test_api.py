"""Integration tests for Teams REST endpoints and RBAC."""

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.teams.models import TeamMembership, TeamRole
from tests.factories import TeamFactory, TeamMembershipFactory, UserFactory


@pytest.mark.django_db
class TestTeamsAPI:
    """Integration test suite for team workspace operations and permissions."""

    def setup_method(self):
        self.client = APIClient()
        self.owner = UserFactory()
        self.admin = UserFactory()
        self.member = UserFactory()
        self.viewer = UserFactory()
        self.outsider = UserFactory()

        # Create a team with owner
        self.team = TeamFactory(name="Engineering Team", created_by=self.owner)

        # Add other roles
        TeamMembershipFactory(team=self.team, user=self.admin, role=TeamRole.ADMIN)
        TeamMembershipFactory(team=self.team, user=self.member, role=TeamRole.MEMBER)
        TeamMembershipFactory(team=self.team, user=self.viewer, role=TeamRole.VIEWER)

    def test_create_team_automatically_assigns_owner(self):
        """Verify creating a team automatically creates OWNER membership for creator."""
        creator = UserFactory()
        self.client.force_authenticate(user=creator)

        url = reverse("teams:teams-list")
        payload = {"name": "Product Design", "description": "Design workspace"}
        response = self.client.post(url, payload, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["name"] == "Product Design"
        assert response.data["user_role"] == TeamRole.OWNER

        team_id = response.data["id"]
        membership = TeamMembership.objects.filter(team_id=team_id, user=creator).first()
        assert membership is not None
        assert membership.role == TeamRole.OWNER

    def test_list_teams_scoped_to_membership(self):
        """Verify user only sees teams they are an active member of."""
        other_team = TeamFactory(name="Secret Executive Team", created_by=self.outsider)

        self.client.force_authenticate(user=self.member)
        url = reverse("teams:teams-list")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        team_ids = [t["id"] for t in response.data["results"]]
        assert str(self.team.id) in team_ids
        assert str(other_team.id) not in team_ids

    def test_add_member_by_owner_success(self):
        """Verify owner can invite a new member to the team."""
        new_user = UserFactory()
        self.client.force_authenticate(user=self.owner)

        url = reverse("teams:teams-add-member", kwargs={"pk": self.team.id})
        payload = {"user_id": new_user.id, "role": TeamRole.MEMBER}
        response = self.client.post(url, payload, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["user"]["id"] == new_user.id
        assert response.data["role"] == TeamRole.MEMBER

    def test_add_member_by_viewer_forbidden(self):
        """Verify viewer cannot add members to the team."""
        new_user = UserFactory()
        self.client.force_authenticate(user=self.viewer)

        url = reverse("teams:teams-add-member", kwargs={"pk": self.team.id})
        payload = {"user_id": new_user.id, "role": TeamRole.MEMBER}
        response = self.client.post(url, payload, format="json")

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_update_member_role_by_admin(self):
        """Verify admin can change member's role to VIEWER."""
        self.client.force_authenticate(user=self.admin)

        url = reverse(
            "teams:teams-update-member-role", kwargs={"pk": self.team.id, "user_id": self.member.id}
        )
        payload = {"role": TeamRole.VIEWER}
        response = self.client.patch(url, payload, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["role"] == TeamRole.VIEWER

    def test_admin_cannot_promote_to_owner(self):
        """Verify admin cannot promote anyone to OWNER (only OWNER can)."""
        self.client.force_authenticate(user=self.admin)

        url = reverse(
            "teams:teams-update-member-role", kwargs={"pk": self.team.id, "user_id": self.member.id}
        )
        payload = {"role": TeamRole.OWNER}
        response = self.client.patch(url, payload, format="json")

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_list_team_members_action(self):
        """Verify GET /api/v1/teams/{id}/members/ lists all members with roles."""
        self.client.force_authenticate(user=self.member)
        url = reverse("teams:teams-members", kwargs={"pk": self.team.id})
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 4  # owner, admin, member, viewer
        roles = [m["role"] for m in response.data]
        assert TeamRole.OWNER in roles
        assert TeamRole.ADMIN in roles
        assert TeamRole.MEMBER in roles
        assert TeamRole.VIEWER in roles

    def test_add_nonexistent_user_fails(self):
        """Verify adding a non-existent user returns 400 Bad Request."""
        self.client.force_authenticate(user=self.owner)
        url = reverse("teams:teams-add-member", kwargs={"pk": self.team.id})
        payload = {"user_id": 999999, "role": TeamRole.MEMBER}
        response = self.client.post(url, payload, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_cannot_remove_sole_owner(self):
        """Verify system prevents removing the only owner in the team."""
        self.client.force_authenticate(user=self.owner)

        url = reverse(
            "teams:teams-remove-member", kwargs={"pk": self.team.id, "user_id": self.owner.id}
        )
        response = self.client.delete(url)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "sole team owner" in response.data["error"]["message"]

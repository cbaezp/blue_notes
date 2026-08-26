"""Unit tests for team domain services and business invariants."""

import pytest

from apps.core.exceptions import ValidationError
from apps.teams.models import TeamMembership, TeamRole
from apps.teams.services import (
    team_add_member,
    team_create,
    team_update_member_role,
)
from tests.factories import TeamFactory, TeamMembershipFactory, UserFactory


@pytest.mark.django_db
class TestTeamServices:
    """Unit tests for team services."""

    def test_team_create_assigns_owner(self):
        """Verify team_create service creates team and sets creator as OWNER."""
        creator = UserFactory()
        team = team_create(name="DevOps", description="Infrastructure", created_by=creator)

        assert team.name == "DevOps"
        membership = TeamMembership.objects.get(team=team, user=creator)
        assert membership.role == TeamRole.OWNER

    def test_team_add_duplicate_member_fails(self):
        """Verify adding an existing member raises ValidationError."""
        owner = UserFactory()
        existing_member = UserFactory()
        team = TeamFactory(created_by=owner)
        TeamMembershipFactory(team=team, user=existing_member)

        with pytest.raises(ValidationError, match="already a member"):
            team_add_member(
                team=team, user=existing_member, role=TeamRole.MEMBER, acting_user=owner
            )

    def test_team_demote_sole_owner_fails(self):
        """Verify demoting the sole owner raises ValidationError."""
        owner = UserFactory()
        team = TeamFactory(created_by=owner)

        with pytest.raises(ValidationError, match="sole team owner"):
            team_update_member_role(
                team=team, target_user=owner, new_role=TeamRole.ADMIN, acting_user=owner
            )

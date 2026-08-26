"""Selectors for fetching Team entities and memberships."""

from django.contrib.auth import get_user_model
from django.db.models import QuerySet

from apps.teams.models import Team, TeamMembership

User = get_user_model()


def get_teams_for_user(user: User) -> QuerySet[Team]:
    """Return all teams where user is an active member."""
    if not user.is_authenticated:
        return Team.objects.none()
    return Team.objects.filter(memberships__user=user).distinct()


def get_team_membership(team: Team, user: User) -> TeamMembership | None:
    """Retrieve membership object for a given user in a team."""
    if not user.is_authenticated:
        return None
    return TeamMembership.objects.filter(team=team, user=user).first()


def get_team_members(team: Team) -> QuerySet[TeamMembership]:
    """Retrieve all memberships for a given team, with user preloaded."""
    return TeamMembership.objects.filter(team=team).select_related("user")
